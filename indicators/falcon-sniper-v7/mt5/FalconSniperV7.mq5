//+------------------------------------------------------------------+
//|                                              FalconSniperV7.mq5  |
//|  Liquidity-sweep sniper entries held for a 300-pip target, run   |
//|  natively on the broker's own prices, with exact goal-optimal    |
//|  position sizing, broker-accurate costs and trade management.    |
//+------------------------------------------------------------------+
//
//  What it does, every time a bar of the signal timeframe closes:
//   1. Rebuilds the sweep engine (swings, structure, sweeps, triggers,
//      kill zones) over the broker's history for this symbol.
//   2. Replays every historical setup as a trade with the broker's current
//      spread, swap (long/short, triple-swap day) and the stop/target/
//      breakeven rules, and shows the results. This is the live
//      "does it still work on this symbol?" check.
//   3. If the bar just closed is a setup: computes the lot size (exact
//      dynamic-programming optimum for a balance goal, or fixed risk %),
//      checks spread, news (MT5 economic calendar), margin and stop
//      distance, then alerts, and places the trade in Auto mode or when
//      the on-chart EXECUTE button is clicked.
//   4. Manages open positions: stop to breakeven at +150 pips.
//
//  Logic mirrors the Python research engine in ../research (sweep
//  reversal, all-in to target, breakeven, no reversal exits).
//+------------------------------------------------------------------+
#property copyright   "Falcon Sniper V7"
#property version     "7.00"
#property description "Liquidity-sweep sniper for a 300-pip target: broker-accurate costs, exact goal-optimal sizing, breakeven management, news filter."

#include <Trade\Trade.mqh>

enum ENUM_FS_MODE
  {
   FS_MODE_SIGNALS = 0, // Signals + one-click EXECUTE button
   FS_MODE_AUTO    = 1  // Fully automatic
  };

enum ENUM_FS_TRIGGER
  {
   FS_TRIG_PIN_MSS = 0, // Pin bar + MSS (recommended)
   FS_TRIG_PIN     = 1, // Pin bar only
   FS_TRIG_ALL     = 2  // Pin bar + MSS + engulfing
  };

enum ENUM_FS_SIZING
  {
   FS_SIZE_CHALLENGE = 0, // Challenge: exact optimum to reach the goal
   FS_SIZE_FIXED     = 1  // Fixed risk % per trade
  };

//--- Signal engine
input group "Signal engine"
input ENUM_TIMEFRAMES InpTF          = PERIOD_H4;     // Signal timeframe
input int             InpSwingLeft   = 5;             // Swing strength, left bars
input int             InpSwingRight  = 3;             // Swing strength, right bars (confirmation delay)
input int             InpSweepWindow = 5;             // Sweep window (bars)
input bool            InpUsePD       = true;          // Previous-day high/low are liquidity
input ENUM_FS_TRIGGER InpTrigger     = FS_TRIG_PIN_MSS; // Entry trigger
input int             InpMssLen      = 3;             // MSS lookback (bars)
input bool            InpKillZones   = true;          // Kill zones (timeframes below H4 only)
input int             InpKZ1Start    = 2;             // London kill zone start (New York hour)
input int             InpKZ1End      = 5;             // London kill zone end (New York hour)
input int             InpKZ2Start    = 7;             // New York kill zone start (New York hour)
input int             InpKZ2End      = 10;            // New York kill zone end (New York hour)
input int             InpCooldown    = 3;             // Cooldown bars between signals
input int             InpRsiLen      = 14;            // RSI length
input double          InpRsiOB       = 70;            // No longs at or above RSI
input double          InpRsiOS       = 30;            // No shorts at or below RSI

//--- Trade plan
input group "Trade plan"
input double InpTargetPips   = 300;   // Target (pips)
input double InpBEPips       = 150;   // Stop to breakeven at +pips (0 = off)
input int    InpSlLookback   = 5;     // Stop beyond extreme of last N bars
input double InpSlBufferPips = 3;     // Stop buffer (pips)
input double InpMinSlPips    = 10;    // Minimum stop (pips)
input double InpMaxSlPips    = 100;   // Maximum stop (pips); wider setups are skipped
input double InpMinRR        = 3.0;   // Minimum target : stop

//--- Execution
input group "Execution (MT5)"
input ENUM_FS_MODE InpMode       = FS_MODE_SIGNALS; // Mode
input bool   InpManage           = true;   // Manage EA positions (breakeven)
input bool   InpManageManual     = false;  // Also manage manual positions on this symbol
input ulong  InpMagic            = 7077777; // Magic number
input int    InpSlippagePoints   = 30;     // Max slippage (points)
input double InpMaxSpreadPips    = 5.0;    // Skip entries when spread is wider (pips)
input bool   InpNewsFilter       = true;   // Block entries near high-impact news
input int    InpNewsMinutes      = 30;     // News window before and after (minutes)

//--- Money
input group "Money & challenge"
input ENUM_FS_SIZING InpSizing   = FS_SIZE_CHALLENGE; // Position sizing
input double   InpRiskPct        = 1.0;    // Fixed risk per trade (%)
input double   InpGoal           = 500;    // Challenge goal (account currency)
input int      InpTrades         = 3;      // Challenge trades in total
input datetime InpChallengeStart = 0;      // Count challenge trades closed since (0 = all EA trades)
input double   InpMarginSafety   = 3.0;    // Margin safety factor (x broker margin)
input double   InpCostBufferPips = 20;     // Plan wins net of this many pips (spread + swap)
input double   InpDefaultP300    = 0.15;   // Fallback P(target) when history is short
input double   InpDefaultPBE     = 0.15;   // Fallback P(breakeven) when history is short
input double   InpPipOverride    = 0;      // Pip size override (0 = auto)

//--- History check
input group "History check"
input int    InpHistoryBars      = 3000;   // Bars of broker history to replay
input double InpSimSpreadPips    = 0;      // Spread for the replay (0 = current spread)
input double InpSwapFallbackPips = -0.5;   // Swap per night (pips) if the symbol's swap mode is not supported

//--- Display
input group "Display & alerts"
input bool   InpShowPanel  = true;   // Show panel
input bool   InpDrawLevels = true;   // Draw signal / position levels
input bool   InpDrawHistory= true;   // Draw historical signal arrows
input bool   InpAlerts     = true;   // Pop-up alerts
input bool   InpPush       = false;  // Push notifications (MT5 mobile)
input bool   InpJournal    = true;   // CSV journal in MQL5\Files

//+------------------------------------------------------------------+
//| Types                                                            |
//+------------------------------------------------------------------+
struct Setup
  {
   int      i;          // bar index (0 = oldest loaded bar)
   int      dir;        // +1 long, -1 short
   double   sl;         // stop price (chart / bid prices)
   double   riskPips;   // stop distance from the bar close
  };

struct SimTrade
  {
   int      i;
   int      exitI;
   int      dir;
   int      why;        // 0 stop, 1 breakeven stop, 2 target
   double   pips;       // net of spread and swap
   double   riskPips;
  };

struct HistStats
  {
   int      n;
   int      nTp;
   int      nBe;
   double   p300;
   double   pBe;
   double   winPips;    // mean net pips of target trades
   double   bePips;     // mean net pips of breakeven trades
   double   avgR;
   double   netPips;
   double   medStop;
   bool     valid;
  };

struct LiveSignal
  {
   bool     active;
   datetime barTime;
   int      dir;
   double   sl;
   double   riskPips;
   string   text;
  };

//+------------------------------------------------------------------+
//| Globals                                                          |
//+------------------------------------------------------------------+
CTrade     g_trade;
string     g_sym;
double     g_point, g_pip, g_tickSize, g_volMin, g_volMax, g_volStep;
int        g_digits;
int        g_rsiHandle = INVALID_HANDLE;
datetime   g_lastBar   = 0;
int        g_serverOff = 0;        // server - UTC, seconds
bool       g_serverNy  = false;    // server clock = New York + 7h (tracks US DST)
HistStats  g_stats;
LiveSignal g_sig;
string     g_lastNote  = "";
double     g_planLots  = 0, g_planProb = 0;
const string PFX = "FSV7_";

//+------------------------------------------------------------------+
//| Helpers: symbol & money                                          |
//+------------------------------------------------------------------+
double PipSize()
  {
   if(InpPipOverride > 0)
      return InpPipOverride;
   string s = g_sym;
   StringToUpper(s);
   bool metal = StringFind(s, "XAU") >= 0 || StringFind(s, "XAG") >= 0 || StringFind(s, "GOLD") >= 0 || StringFind(s, "SILVER") >= 0;
   if(g_digits == 3 || g_digits == 5 || metal)
      return g_point * 10.0;
   return g_point;
  }

double PipValuePerLot()
  {
   double tv = SymbolInfoDouble(g_sym, SYMBOL_TRADE_TICK_VALUE_LOSS);
   if(tv <= 0)
      tv = SymbolInfoDouble(g_sym, SYMBOL_TRADE_TICK_VALUE);
   if(tv <= 0 || g_tickSize <= 0)
      return 0;
   return tv * g_pip / g_tickSize;
  }

double MarginPerLot(int dir)
  {
   double price = dir > 0 ? SymbolInfoDouble(g_sym, SYMBOL_ASK) : SymbolInfoDouble(g_sym, SYMBOL_BID);
   if(price <= 0)
      price = iClose(g_sym, InpTF, 0);
   double m = 0;
   if(!OrderCalcMargin(dir > 0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL, g_sym, 1.0, price, m) || m <= 0)
      return 0;
   return m * MathMax(InpMarginSafety, 1.0);
  }

double StopOutFraction()
  {
   if(AccountInfoInteger(ACCOUNT_MARGIN_SO_MODE) == ACCOUNT_STOPOUT_MODE_PERCENT)
     {
      double so = AccountInfoDouble(ACCOUNT_MARGIN_SO_SO);
      if(so > 0)
         return MathMax(so, 50.0) / 100.0;   // never assume a stop-out below 50%
     }
   return 0.5;
  }

double SpreadPipsNow()
  {
   double ask = SymbolInfoDouble(g_sym, SYMBOL_ASK), bid = SymbolInfoDouble(g_sym, SYMBOL_BID);
   if(ask <= 0 || bid <= 0 || ask < bid)
      return 0;
   return (ask - bid) / g_pip;
  }

// Swap per night in pips for one direction (positive = credit, negative = charge).
double SwapPipsPerNight(int dir)
  {
   long   mode = SymbolInfoInteger(g_sym, SYMBOL_SWAP_MODE);
   double v    = SymbolInfoDouble(g_sym, dir > 0 ? SYMBOL_SWAP_LONG : SYMBOL_SWAP_SHORT);
   double pv   = PipValuePerLot();
   double px   = iClose(g_sym, InpTF, 0);
   switch((int)mode)
     {
      case SYMBOL_SWAP_MODE_DISABLED:
         return 0;
      case SYMBOL_SWAP_MODE_POINTS:
         return v * g_point / g_pip;
      case SYMBOL_SWAP_MODE_CURRENCY_DEPOSIT:
         return pv > 0 ? v / pv : InpSwapFallbackPips;
      case SYMBOL_SWAP_MODE_INTEREST_CURRENT:
      case SYMBOL_SWAP_MODE_INTEREST_OPEN:
         return px > 0 ? v / 100.0 / 360.0 * px / g_pip : InpSwapFallbackPips;
     }
   return InpSwapFallbackPips;
  }

double NormalizeLots(double lots)
  {
   if(g_volStep <= 0)
      return 0;
   double steps = MathFloor(lots / g_volStep + 1e-9);
   double v = steps * g_volStep;
   if(v < g_volMin - 1e-12)
      return 0;
   return MathMin(v, g_volMax);
  }

//+------------------------------------------------------------------+
//| Helpers: time                                                    |
//+------------------------------------------------------------------+
// Day of month of the n-th Sunday (n>=1) of a month.
int NthSunday(int year, int month, int n)
  {
   MqlDateTime d;
   d.year = year; d.mon = month; d.day = 1; d.hour = 0; d.min = 0; d.sec = 0;
   datetime t = StructToTime(d);
   MqlDateTime x;
   TimeToStruct(t, x);
   int first = 1 + (7 - x.day_of_week) % 7;
   return first + 7 * (n - 1);
  }

// New York UTC offset (seconds) at a UTC instant.
int NyOffset(datetime utc)
  {
   MqlDateTime d;
   TimeToStruct(utc, d);
   MqlDateTime a;
   a.year = d.year; a.mon = 3;  a.day = NthSunday(d.year, 3, 2);  a.hour = 7; a.min = 0; a.sec = 0;   // 02:00 EST
   MqlDateTime b;
   b.year = d.year; b.mon = 11; b.day = NthSunday(d.year, 11, 1); b.hour = 6; b.min = 0; b.sec = 0;   // 02:00 EDT
   datetime start = StructToTime(a), end = StructToTime(b);
   return (utc >= start && utc < end) ? -4 * 3600 : -5 * 3600;
  }

void MeasureServerClock()
  {
   datetime srv = TimeTradeServer(), gmt = TimeGMT();
   g_serverOff = (int)(MathRound((double)(srv - gmt) / 1800.0) * 1800.0);
   g_serverNy  = (g_serverOff - NyOffset(gmt) == 7 * 3600);
  }

datetime ServerToNy(datetime srv)
  {
   if(g_serverNy)
      return srv - 7 * 3600;
   datetime utc = srv - g_serverOff;
   return utc + NyOffset(utc);
  }

// Swap rollovers (server midnights, weekends skipped, triple day x3) in (t0, t1].
int Rollovers(datetime t0, datetime t1)
  {
   int n = 0;
   long tri = SymbolInfoInteger(g_sym, SYMBOL_SWAP_ROLLOVER3DAYS);
   datetime m = (datetime)(((long)t0 / 86400 + 1) * 86400);
   for(; m <= t1; m += 86400)
     {
      MqlDateTime d;
      TimeToStruct(m - 1, d);
      if(d.day_of_week == 0 || d.day_of_week == 6)
         continue;
      n += (d.day_of_week == (int)tri) ? 3 : 1;
     }
   return n;
  }

//+------------------------------------------------------------------+
//| Signal engine (mirror of research/engine.py, sweep reversal)     |
//+------------------------------------------------------------------+
int EvaluateSetups(const MqlRates &r[], const double &rsi[], int n, Setup &out[])
  {
   ArrayResize(out, 0);
   double shPrice = 0, slPrice = 0;
   int    shBar = -1, slBar = -1;
   bool   shBroken = true, slBroken = true, shSwept = false, slSwept = false;
   int    structDir = 0;
   int    lastBullSweep = -1000000, lastBearSweep = -1000000;
   bool   intraday = PeriodSeconds(InpTF) < 4 * 3600;
   bool   usePd = InpUsePD && PeriodSeconds(InpTF) < 86400;
   int    L = InpSwingLeft, R = InpSwingRight;

   for(int i = 0; i < n; i++)
     {
      double o = r[i].open, h = r[i].high, l = r[i].low, c = r[i].close;

      //--- swings confirmed on this bar
      if(i >= L + R)
        {
         int p = i - R;
         bool isH = true, isL = true;
         for(int k = p - L; k <= i && (isH || isL); k++)
           {
            if(k == p)
               continue;
            if(r[k].high >= r[p].high)
               isH = false;
            if(r[k].low <= r[p].low)
               isL = false;
           }
         if(isH)
           { shPrice = r[p].high; shBar = p; shBroken = false; shSwept = false; }
         if(isL)
           { slPrice = r[p].low;  slBar = p; slBroken = false; slSwept = false; }
        }

      //--- structure breaks (close beyond the latest swing)
      if(shBar >= 0 && !shBroken && c > shPrice)
        { structDir = 1; shBroken = true; }
      if(slBar >= 0 && !slBroken && c < slPrice)
        { structDir = -1; slBroken = true; }

      //--- liquidity sweeps
      bool swL = slBar >= 0 && !slBroken && !slSwept && l < slPrice && c > slPrice;
      bool swH = shBar >= 0 && !shBroken && !shSwept && h > shPrice && c < shPrice;
      if(swL)
         slSwept = true;
      if(swH)
         shSwept = true;
      bool pdL = false, pdH = false;
      if(usePd)
        {
         int ds = iBarShift(g_sym, PERIOD_D1, r[i].time, false);
         if(ds >= 0)
           {
            double pdh = iHigh(g_sym, PERIOD_D1, ds + 1), pdl = iLow(g_sym, PERIOD_D1, ds + 1);
            if(pdl > 0 && l < pdl && c > pdl)
               pdL = true;
            if(pdh > 0 && h > pdh && c < pdh)
               pdH = true;
           }
        }
      if(swL || pdL)
         lastBullSweep = i;
      if(swH || pdH)
         lastBearSweep = i;

      //--- gates
      if(i < 205 || i < InpMssLen || i < InpSlLookback || rsi[i] == EMPTY_VALUE || rsi[i] <= 0)
         continue;
      double body = MathAbs(c - o), rng = h - l;
      double lw = MathMin(o, c) - l, uw = h - MathMax(o, c);
      bool pinL = rng > 0 && lw >= 2 * body && lw >= 0.5 * rng && h - c <= rng / 3.0;
      bool pinS = rng > 0 && uw >= 2 * body && uw >= 0.5 * rng && c - l <= rng / 3.0;
      double hh = r[i - 1].high, ll = r[i - 1].low;
      for(int k = i - InpMssLen; k < i; k++)
        {
         hh = MathMax(hh, r[k].high);
         ll = MathMin(ll, r[k].low);
        }
      bool mssL = c > hh && c > o;
      bool mssS = c < ll && c < o;
      bool engL = c > o && r[i - 1].close < r[i - 1].open && c >= r[i - 1].open && o <= r[i - 1].close;
      bool engS = c < o && r[i - 1].close > r[i - 1].open && c <= r[i - 1].open && o >= r[i - 1].close;
      bool trigL = InpTrigger == FS_TRIG_PIN ? pinL : InpTrigger == FS_TRIG_PIN_MSS ? (pinL || mssL) : (pinL || mssL || engL);
      bool trigS = InpTrigger == FS_TRIG_PIN ? pinS : InpTrigger == FS_TRIG_PIN_MSS ? (pinS || mssS) : (pinS || mssS || engS);

      bool kzOk = true;
      if(InpKillZones && intraday)
        {
         MqlDateTime ny;
         TimeToStruct(ServerToNy(r[i].time), ny);
         kzOk = (ny.hour >= InpKZ1Start && ny.hour < InpKZ1End) || (ny.hour >= InpKZ2Start && ny.hour < InpKZ2End);
        }
      if(!kzOk)
         continue;

      bool sweepL = i - lastBullSweep <= InpSweepWindow;
      bool sweepS = i - lastBearSweep <= InpSweepWindow;
      bool longOk = sweepL && trigL && rsi[i] < InpRsiOB;
      bool shortOk = sweepS && trigS && rsi[i] > InpRsiOS;
      if(!longOk && !shortOk)
         continue;

      //--- stop plan
      double lo = l, hi = h;
      for(int k = i - InpSlLookback + 1; k <= i; k++)
        {
         lo = MathMin(lo, r[k].low);
         hi = MathMax(hi, r[k].high);
        }
      double rpL = MathMax((c - (lo - InpSlBufferPips * g_pip)) / g_pip, InpMinSlPips);
      double rpS = MathMax(((hi + InpSlBufferPips * g_pip) - c) / g_pip, InpMinSlPips);
      bool okL = longOk && rpL <= InpMaxSlPips && InpTargetPips / rpL >= InpMinRR;
      bool okS = shortOk && rpS <= InpMaxSlPips && InpTargetPips / rpS >= InpMinRR;
      if(okL && okS)
         continue;   // ambiguous bar: both sides qualify (rare) - no trade
      if(!okL && !okS)
         continue;
      int sz = ArraySize(out);
      ArrayResize(out, sz + 1);
      out[sz].i = i;
      out[sz].dir = okL ? 1 : -1;
      out[sz].riskPips = okL ? rpL : rpS;
      out[sz].sl = okL ? c - rpL * g_pip : c + rpS * g_pip;
     }
   return ArraySize(out);
  }

//+------------------------------------------------------------------+
//| History replay (mirror of research/sim.py)                        |
//+------------------------------------------------------------------+
bool Walk(const MqlRates &r[], int n, const Setup &s, double spreadPx, double swapL, double swapS, SimTrade &t)
  {
   int    d = s.dir;
   double c = r[s.i].close;
   double entry = d > 0 ? c + spreadPx : c;
   double risk = d > 0 ? entry - s.sl : s.sl - entry;
   if(risk <= 0)
      return false;
   double tp = entry + d * InpTargetPips * g_pip;
   double stop = s.sl;
   bool   beOn = false;
   for(int k = s.i + 1; k < n; k++)
     {
      double o = r[k].open, h = r[k].high, l = r[k].low;
      double px = 0;
      int    why = -1;
      if(d > 0)
        {
         if(l <= stop)
           { px = MathMin(o, stop); why = beOn ? 1 : 0; }
         else if(h >= tp)
           { px = tp; why = 2; }
         else if(InpBEPips > 0 && !beOn && h - entry >= InpBEPips * g_pip)
           { stop = entry; beOn = true; }
        }
      else
        {
         if(h + spreadPx >= stop)
           { px = MathMax(o + spreadPx, stop); why = beOn ? 1 : 0; }
         else if(l + spreadPx <= tp)
           { px = tp; why = 2; }
         else if(InpBEPips > 0 && !beOn && entry - (l + spreadPx) >= InpBEPips * g_pip)
           { stop = entry; beOn = true; }
        }
      if(why >= 0)
        {
         int nights = Rollovers(r[s.i].time, r[k].time);
         t.i = s.i;
         t.exitI = k;
         t.dir = d;
         t.why = why;
         t.pips = d * (px - entry) / g_pip + (d > 0 ? swapL : swapS) * nights;
         t.riskPips = risk / g_pip;
         return true;
        }
     }
   return false;
  }

void ReplayHistory(const MqlRates &r[], int n, const Setup &setups[], int ns)
  {
   ZeroMemory(g_stats);
   double spread = InpSimSpreadPips > 0 ? InpSimSpreadPips : MathMin(MathMax(SpreadPipsNow(), 0.1), InpMaxSpreadPips);
   double spreadPx = spread * g_pip;
   double swL = SwapPipsPerNight(1), swS = SwapPipsPerNight(-1);
   int busyUntil = -1, last = -1000000;
   double sumR = 0, sumWin = 0, sumBe = 0;
   double stops[];
   ArrayResize(stops, 0);
   if(InpDrawHistory)
      ObjectsDeleteAll(0, PFX + "H");
   for(int j = 0; j < ns; j++)
     {
      if(setups[j].i < busyUntil || setups[j].i - last < InpCooldown)
         continue;
      SimTrade t;
      if(!Walk(r, n, setups[j], spreadPx, swL, swS, t))
         break;
      busyUntil = t.exitI;
      last = setups[j].i;
      g_stats.n++;
      g_stats.netPips += t.pips;
      sumR += t.pips / t.riskPips;
      int m = ArraySize(stops);
      ArrayResize(stops, m + 1);
      stops[m] = t.riskPips;
      if(t.why == 2)
        { g_stats.nTp++; sumWin += t.pips; }
      if(t.why == 1)
        { g_stats.nBe++; sumBe += t.pips; }
      if(InpDrawHistory)
        {
         string nm = PFX + "H" + IntegerToString(setups[j].i);
         double y = t.dir > 0 ? r[t.i].low : r[t.i].high;
         if(ObjectCreate(0, nm, t.dir > 0 ? OBJ_ARROW_BUY : OBJ_ARROW_SELL, 0, r[t.i].time, y))
           {
            ObjectSetInteger(0, nm, OBJPROP_COLOR, t.why == 2 ? clrLime : t.why == 1 ? clrSilver : clrTomato);
            ObjectSetString(0, nm, OBJPROP_TOOLTIP, StringFormat("%s  stop %.1fp  -> %s  %+.1f pips", t.dir > 0 ? "BUY" : "SELL", t.riskPips,
                            t.why == 2 ? "TARGET" : t.why == 1 ? "breakeven" : "stop", t.pips));
           }
        }
     }
   if(g_stats.n > 0)
     {
      g_stats.p300 = (double)g_stats.nTp / g_stats.n;
      g_stats.pBe  = (double)g_stats.nBe / g_stats.n;
      g_stats.winPips = g_stats.nTp > 0 ? sumWin / g_stats.nTp : InpTargetPips - InpCostBufferPips;
      g_stats.bePips  = g_stats.nBe > 0 ? sumBe / g_stats.nBe : 0;
      g_stats.avgR = sumR / g_stats.n;
      ArraySort(stops);
      int m = ArraySize(stops);
      g_stats.medStop = (m % 2 == 1) ? stops[m / 2] : 0.5 * (stops[m / 2 - 1] + stops[m / 2]);
      g_stats.valid = g_stats.n >= 30;
     }
  }

//+------------------------------------------------------------------+
//| Position sizing                                                  |
//+------------------------------------------------------------------+
double Lookup(const double &v[], int cells, double step, double bal)
  {
   if(bal >= InpGoal - 1e-9)
      return 1.0;
   if(bal <= 0)
      return 0.0;
   int idx = (int)MathFloor(bal / step);
   if(idx >= cells)
      return 1.0;
   return v[idx];
  }

// Best lot size for balance `bal` given the value function `v` of the
// remaining trades. Returns the probability of reaching the goal.
double BestLots(double bal, const double &v[], int cells, double step, double stopPips, double pipVal,
                double marginLot, double so, double p, double q, double winPips, double bePips, double &lots)
  {
   lots = 0;
   double perLot = stopPips * pipVal + so * marginLot;
   if(perLot <= 0 || g_volStep <= 0)
      return 0;
   int maxSteps = (int)MathFloor(bal / perLot / g_volStep + 1e-9);
   int minSteps = (int)MathCeil(g_volMin / g_volStep - 1e-9);
   int capSteps = (int)MathFloor(g_volMax / g_volStep + 1e-9);
   if(maxSteps > capSteps)
      maxSteps = capSteps;
   double best = 0;
   int firstStep = minSteps < 1 ? 1 : minSteps;
   for(int s = firstStep; s <= maxSteps; s++)
     {
      double L = s * g_volStep;
      double val = p * Lookup(v, cells, step, bal + L * pipVal * winPips)
                   + q * Lookup(v, cells, step, bal + L * pipVal * bePips)
                   + (1.0 - p - q) * Lookup(v, cells, step, bal - L * pipVal * stopPips);
      if(val > best + 1e-12)
        { best = val; lots = L; }
     }
   return best;
  }

// Exact dynamic programme: probability of reaching InpGoal within `k`
// trades from `bal`, and the lot size that achieves it for a trade whose
// stop is `stopPips` (future trades use the typical stop).
double ChallengeLots(double bal, int k, double stopPips, int dir, double &lots)
  {
   lots = 0;
   if(bal >= InpGoal)
      return 1.0;
   if(k <= 0)
      return 0.0;
   if(k > 5)
      k = 5;
   double pipVal = PipValuePerLot();
   double marginLot = MarginPerLot(dir);
   double so = StopOutFraction();
   if(pipVal <= 0 || marginLot <= 0)
      return 0;
   double p = g_stats.valid ? g_stats.p300 : InpDefaultP300;
   double q = g_stats.valid ? g_stats.pBe  : InpDefaultPBE;
   double win = MathMin(g_stats.valid ? g_stats.winPips : InpTargetPips, InpTargetPips - InpCostBufferPips);
   double be = g_stats.valid ? g_stats.bePips : 0.0;
   double typStop = g_stats.medStop > 0 ? g_stats.medStop : stopPips;
   int cells = 4001;
   double step = InpGoal / (cells - 1);
   double prev[], cur[];
   ArrayResize(prev, cells);
   ArrayResize(cur, cells);
   ArrayInitialize(prev, 0.0);
   double dummy;
   for(int j = 1; j < k; j++)
     {
      for(int b = 0; b < cells; b++)
         cur[b] = BestLots(b * step, prev, cells, step, typStop, pipVal, marginLot, so, p, q, win, be, dummy);
      ArrayCopy(prev, cur);
     }
   double prob = BestLots(bal, prev, cells, step, stopPips, pipVal, marginLot, so, p, q, win, be, lots);
   if(prob <= 0)
     {
      // goal unreachable from here: fall back to the smallest affordable lot
      double perLot = stopPips * pipVal + so * marginLot;
      lots = (perLot > 0 && bal / perLot >= g_volMin) ? g_volMin : 0;
     }
   return prob;
  }

double FixedLots(double bal, double stopPips, int dir)
  {
   double pipVal = PipValuePerLot(), marginLot = MarginPerLot(dir), so = StopOutFraction();
   if(pipVal <= 0)
      return 0;
   double want = bal * InpRiskPct / 100.0 / (stopPips * pipVal);
   double cap = bal / (stopPips * pipVal + so * marginLot);
   return NormalizeLots(MathMin(want, cap));
  }

int ChallengeTradesDone()
  {
   if(!HistorySelect(InpChallengeStart, TimeCurrent() + 86400))
      return 0;
   long ids[];
   ArrayResize(ids, 0);
   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
     {
      ulong tk = HistoryDealGetTicket(i);
      if(tk == 0)
         continue;
      if((ulong)HistoryDealGetInteger(tk, DEAL_MAGIC) != InpMagic)
         continue;
      long entry = HistoryDealGetInteger(tk, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_OUT_BY)
         continue;
      long pid = HistoryDealGetInteger(tk, DEAL_POSITION_ID);
      bool seen = false;
      for(int j = 0; j < ArraySize(ids); j++)
         if(ids[j] == pid)
           { seen = true; break; }
      if(!seen)
        {
         int m = ArraySize(ids);
         ArrayResize(ids, m + 1);
         ids[m] = pid;
        }
     }
   return ArraySize(ids);
  }

double PlanLots(int dir, double stopPips, double &prob)
  {
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   prob = 0;
   if(InpSizing == FS_SIZE_FIXED)
      return FixedLots(bal, stopPips, dir);
   int left = InpTrades - ChallengeTradesDone();
   if(bal >= InpGoal)
     {
      prob = 1.0;
      return FixedLots(bal, stopPips, dir);   // goal reached: protect it
     }
   if(left <= 0)
      return 0;
   double lots;
   prob = ChallengeLots(bal, left, stopPips, dir, lots);
   return NormalizeLots(lots);
  }

//+------------------------------------------------------------------+
//| Filters                                                          |
//+------------------------------------------------------------------+
bool NewsBlocked(string &why)
  {
   why = "";
   if(!InpNewsFilter || MQLInfoInteger(MQL_TESTER))
      return false;
   string cur[2];
   cur[0] = SymbolInfoString(g_sym, SYMBOL_CURRENCY_BASE);
   cur[1] = SymbolInfoString(g_sym, SYMBOL_CURRENCY_PROFIT);
   datetime now = TimeTradeServer();
   for(int c = 0; c < 2; c++)
     {
      if(cur[c] == "" || (c == 1 && cur[1] == cur[0]))
         continue;
      MqlCalendarValue vals[];
      int nv = CalendarValueHistory(vals, now - InpNewsMinutes * 60, now + InpNewsMinutes * 60, NULL, cur[c]);
      for(int k = 0; k < nv; k++)
        {
         MqlCalendarEvent ev;
         if(CalendarEventById(vals[k].event_id, ev) && ev.importance == CALENDAR_IMPORTANCE_HIGH)
           {
            why = cur[c] + " " + ev.name;
            return true;
           }
        }
     }
   return false;
  }

bool HasPosition()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) == g_sym && (ulong)PositionGetInteger(POSITION_MAGIC) == InpMagic)
         return true;
     }
   return false;
  }

//+------------------------------------------------------------------+
//| Orders & management                                              |
//+------------------------------------------------------------------+
bool Execute(string &msg)
  {
   msg = "";
   if(!g_sig.active)
     { msg = "no active signal"; return false; }
   if(HasPosition())
     { msg = "a Falcon position is already open"; return false; }
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED))
     { msg = "algo trading is disabled (enable the Algo Trading button)"; return false; }
   double spread = SpreadPipsNow();
   if(spread > InpMaxSpreadPips)
     { msg = StringFormat("spread %.1f pips is above %.1f", spread, InpMaxSpreadPips); return false; }
   string news;
   if(NewsBlocked(news))
     { msg = "high-impact news: " + news; return false; }

   int d = g_sig.dir;
   double price = d > 0 ? SymbolInfoDouble(g_sym, SYMBOL_ASK) : SymbolInfoDouble(g_sym, SYMBOL_BID);
   double sl = g_sig.sl;
   double risk = d > 0 ? (price - sl) / g_pip : (sl - price) / g_pip;
   if(risk < InpMinSlPips)
     { sl = price - d * InpMinSlPips * g_pip; risk = InpMinSlPips; }
   if(risk > InpMaxSlPips * 1.1 || InpTargetPips / risk < InpMinRR * 0.9)
     { msg = StringFormat("price moved: stop now %.1f pips", risk); return false; }
   double tp = price + d * InpTargetPips * g_pip;
   double stopsLevel = (double)SymbolInfoInteger(g_sym, SYMBOL_TRADE_STOPS_LEVEL) * g_point;
   if(MathAbs(price - sl) <= stopsLevel)
     { msg = "stop is inside the broker's minimum stop distance"; return false; }
   double prob;
   double lots = PlanLots(d, risk, prob);
   if(lots <= 0)
     { msg = "lot size below the broker minimum for this balance"; return false; }
   double m = 0;
   if(OrderCalcMargin(d > 0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL, g_sym, lots, price, m) && m > AccountInfoDouble(ACCOUNT_MARGIN_FREE))
     { msg = StringFormat("not enough free margin for %.2f lots", lots); return false; }

   sl = NormalizeDouble(sl, g_digits);
   tp = NormalizeDouble(tp, g_digits);
   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints((ulong)InpSlippagePoints);
   g_trade.SetTypeFillingBySymbol(g_sym);
   bool ok = d > 0 ? g_trade.Buy(lots, g_sym, 0.0, sl, tp, "Falcon V7") : g_trade.Sell(lots, g_sym, 0.0, sl, tp, "Falcon V7");
   uint rc = g_trade.ResultRetcode();
   if(!ok || (rc != TRADE_RETCODE_DONE && rc != TRADE_RETCODE_PLACED))
     {
      msg = StringFormat("order failed: %u %s", rc, g_trade.ResultRetcodeDescription());
      return false;
     }
   msg = StringFormat("%s %.2f lots @ %s  SL %s  TP %s", d > 0 ? "BUY" : "SELL", lots,
                      DoubleToString(g_trade.ResultPrice(), g_digits), DoubleToString(sl, g_digits), DoubleToString(tp, g_digits));
   g_sig.active = false;
   Journal("ORDER", msg);
   return true;
  }

void ManagePositions()
  {
   if(!InpManage || InpBEPips <= 0)
      return;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || PositionGetString(POSITION_SYMBOL) != g_sym)
         continue;
      bool mine = (ulong)PositionGetInteger(POSITION_MAGIC) == InpMagic;
      if(!mine && !InpManageManual)
         continue;
      long   type = PositionGetInteger(POSITION_TYPE);
      double open = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl   = PositionGetDouble(POSITION_SL);
      double tp   = PositionGetDouble(POSITION_TP);
      double bid  = SymbolInfoDouble(g_sym, SYMBOL_BID), ask = SymbolInfoDouble(g_sym, SYMBOL_ASK);
      double be   = NormalizeDouble(open, g_digits);
      if(type == POSITION_TYPE_BUY)
        {
         if(bid - open >= InpBEPips * g_pip && (sl == 0 || sl < be - g_point / 2))
            if(g_trade.PositionModify(tk, be, tp))
               Journal("BREAKEVEN", StringFormat("ticket %I64u stop -> %s", tk, DoubleToString(be, g_digits)));
        }
      else if(type == POSITION_TYPE_SELL)
        {
         if(open - ask >= InpBEPips * g_pip && (sl == 0 || sl > be + g_point / 2))
            if(g_trade.PositionModify(tk, be, tp))
               Journal("BREAKEVEN", StringFormat("ticket %I64u stop -> %s", tk, DoubleToString(be, g_digits)));
        }
     }
  }

//+------------------------------------------------------------------+
//| Output                                                           |
//+------------------------------------------------------------------+
void Journal(string kind, string text)
  {
   if(!InpJournal || MQLInfoInteger(MQL_TESTER))
      return;
   int h = FileOpen("FalconSniperV7_journal.csv", FILE_CSV | FILE_READ | FILE_WRITE | FILE_ANSI | FILE_SHARE_READ, ',');
   if(h == INVALID_HANDLE)
      return;
   FileSeek(h, 0, SEEK_END);
   FileWrite(h, TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS), g_sym, kind, text,
             DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2));
   FileClose(h);
  }

void Notify(string text)
  {
   if(InpAlerts)
      Alert(text);
   if(InpPush)
      SendNotification(text);
  }

void DrawLevel(string name, double price, color clr, string label)
  {
   if(!InpDrawLevels)
      return;
   string nm = PFX + name;
   if(ObjectFind(0, nm) < 0)
      ObjectCreate(0, nm, OBJ_HLINE, 0, 0, price);
   ObjectSetDouble(0, nm, OBJPROP_PRICE, price);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, nm, OBJPROP_STYLE, STYLE_DASH);
   ObjectSetString(0, nm, OBJPROP_TEXT, label);
   ObjectSetString(0, nm, OBJPROP_TOOLTIP, label);
  }

void UpdateButton()
  {
   string nm = PFX + "EXEC";
   bool show = g_sig.active && InpMode == FS_MODE_SIGNALS;
   if(!show)
     {
      ObjectDelete(0, nm);
      return;
     }
   if(ObjectFind(0, nm) < 0)
     {
      ObjectCreate(0, nm, OBJ_BUTTON, 0, 0, 0);
      ObjectSetInteger(0, nm, OBJPROP_CORNER, CORNER_RIGHT_LOWER);
      ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, 260);
      ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, 60);
      ObjectSetInteger(0, nm, OBJPROP_XSIZE, 240);
      ObjectSetInteger(0, nm, OBJPROP_YSIZE, 40);
      ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, 11);
     }
   ObjectSetString(0, nm, OBJPROP_TEXT, StringFormat("EXECUTE %s %.2f", g_sig.dir > 0 ? "BUY" : "SELL", g_planLots));
   ObjectSetInteger(0, nm, OBJPROP_BGCOLOR, g_sig.dir > 0 ? clrSeaGreen : clrFireBrick);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, clrWhite);
   ObjectSetInteger(0, nm, OBJPROP_STATE, false);
  }

void UpdatePanel()
  {
   if(!InpShowPanel)
      return;
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   double pv = PipValuePerLot();
   string s = StringFormat("FALCON SNIPER V7  |  %s %s  |  broker prices\n", g_sym, EnumToString(InpTF));
   s += StringFormat("Pip %s  ·  $%.2f per pip per lot  ·  spread %.1fp  ·  swap L %+.2fp / S %+.2fp per night\n",
                     DoubleToString(g_pip, g_digits), pv, SpreadPipsNow(), SwapPipsPerNight(1), SwapPipsPerNight(-1));
   s += StringFormat("Leverage 1:%I64d  ·  margin safety x%.1f  ·  stop-out %.0f%%\n",
                     AccountInfoInteger(ACCOUNT_LEVERAGE), InpMarginSafety, StopOutFraction() * 100);
   if(g_stats.n > 0)
      s += StringFormat("History (%d bars, net of spread+swap): %d trades · target %.1f%% · breakeven %.1f%% · avg %+.3fR · %+.0f pips · median stop %.0fp\n",
                        InpHistoryBars, g_stats.n, g_stats.p300 * 100, g_stats.pBe * 100, g_stats.avgR, g_stats.netPips, g_stats.medStop);
   else
      s += "History: no completed trades in the loaded bars\n";
   if(g_stats.n > 0 && g_stats.medStop > InpMaxSlPips * 0.9)
      s += "Stop fit: typical stop is close to the maximum. Use a lower timeframe or a smaller target.\n";
   if(InpSizing == FS_SIZE_CHALLENGE)
     {
      int done = ChallengeTradesDone();
      s += StringFormat("Challenge: balance %.2f -> goal %.2f · trades left %d of %d · zero-edge ceiling %.1f%%\n",
                        bal, InpGoal, MathMax(InpTrades - done, 0), InpTrades, MathMin(100.0, 100.0 * bal / InpGoal));
     }
   else
      s += StringFormat("Sizing: fixed %.2f%% risk · balance %.2f\n", InpRiskPct, bal);
   if(g_sig.active)
      s += g_sig.text + StringFormat("\nPlan: %.2f lots%s\n", g_planLots,
                                     InpSizing == FS_SIZE_CHALLENGE ? StringFormat(" · P(goal) %.1f%%", g_planProb * 100) : "");
   else
      s += "Signal: none on the last closed bar\n";
   if(g_lastNote != "")
      s += "Note: " + g_lastNote + "\n";
   s += "Mode: " + (InpMode == FS_MODE_AUTO ? "AUTO" : "signals + EXECUTE button") + (HasPosition() ? " · position open" : "");
   Comment(s);
  }

//+------------------------------------------------------------------+
//| Bar processing                                                   |
//+------------------------------------------------------------------+
void OnNewBar()
  {
   MeasureServerClock();
   int want = InpHistoryBars + 1;
   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   int got = CopyRates(g_sym, InpTF, 0, want, rates);
   if(got < 260)
     {
      g_lastNote = StringFormat("waiting for history (%d bars)", got);
      UpdatePanel();
      return;
     }
   double rsi[];
   ArraySetAsSeries(rsi, false);
   if(BarsCalculated(g_rsiHandle) < got || CopyBuffer(g_rsiHandle, 0, 0, got, rsi) != got)
     {
      g_lastNote = "waiting for RSI";
      g_lastBar = 0;   // retry on the next tick
      UpdatePanel();
      return;
     }
   int n = got - 1;                       // exclude the forming bar
   Setup setups[];
   int ns = EvaluateSetups(rates, rsi, n, setups);
   ReplayHistory(rates, n, setups, ns);

   g_sig.active = false;
   if(ns > 0 && setups[ns - 1].i == n - 1)
     {
      Setup s = setups[ns - 1];
      string key = PFX + g_sym + "_" + EnumToString(InpTF) + "_last";
      datetime lastSig = GlobalVariableCheck(key) ? (datetime)GlobalVariableGet(key) : 0;
      int barsSince = lastSig > 0 ? iBarShift(g_sym, InpTF, lastSig, false) - 1 : 1000000;
      if(!HasPosition() && barsSince >= InpCooldown && rates[n - 1].time != lastSig)
        {
         g_sig.active = true;
         g_sig.barTime = rates[n - 1].time;
         g_sig.dir = s.dir;
         g_sig.sl = s.sl;
         g_sig.riskPips = s.riskPips;
         GlobalVariableSet(key, (double)rates[n - 1].time);
         g_planLots = PlanLots(s.dir, s.riskPips + (s.dir > 0 ? SpreadPipsNow() : 0), g_planProb);
         double pv = PipValuePerLot();
         g_sig.text = StringFormat("SNIPER %s %s @ %s · SL %s (%.1fp) · TP %+.0fp · risk $%.2f · win ≈ $%.2f",
                                   s.dir > 0 ? "BUY" : "SELL", g_sym, DoubleToString(rates[n - 1].close, g_digits),
                                   DoubleToString(s.sl, g_digits), s.riskPips, InpTargetPips,
                                   g_planLots * pv * (s.riskPips + (s.dir > 0 ? SpreadPipsNow() : 0)),
                                   g_planLots * pv * MathMin(InpTargetPips - InpCostBufferPips, g_stats.valid ? g_stats.winPips : InpTargetPips));
         Journal("SIGNAL", g_sig.text + StringFormat(" | lots %.2f P(goal) %.3f", g_planLots, g_planProb));
         Notify("Falcon V7 " + g_sig.text + StringFormat(" · lots %.2f", g_planLots));
         if(InpDrawLevels)
           {
            DrawLevel("SL", s.sl, clrTomato, StringFormat("Falcon SL %.1fp", s.riskPips));
            DrawLevel("TP", rates[n - 1].close + s.dir * InpTargetPips * g_pip, clrLime, StringFormat("Falcon TP +%.0fp", InpTargetPips));
           }
         if(InpMode == FS_MODE_AUTO)
           {
            string msg;
            bool done = Execute(msg);
            g_lastNote = msg;
            Notify("Falcon V7 AUTO: " + (done ? msg : "not placed: " + msg));
           }
        }
     }
   if(!g_sig.active && !HasPosition())
     {
      ObjectDelete(0, PFX + "SL");
      ObjectDelete(0, PFX + "TP");
     }
   UpdateButton();
   UpdatePanel();
  }

//+------------------------------------------------------------------+
//| Event handlers                                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
   g_sym      = _Symbol;
   g_digits   = (int)SymbolInfoInteger(g_sym, SYMBOL_DIGITS);
   g_point    = SymbolInfoDouble(g_sym, SYMBOL_POINT);
   g_tickSize = SymbolInfoDouble(g_sym, SYMBOL_TRADE_TICK_SIZE);
   g_volMin   = SymbolInfoDouble(g_sym, SYMBOL_VOLUME_MIN);
   g_volMax   = SymbolInfoDouble(g_sym, SYMBOL_VOLUME_MAX);
   g_volStep  = SymbolInfoDouble(g_sym, SYMBOL_VOLUME_STEP);
   g_pip      = PipSize();
   if(g_point <= 0 || g_pip <= 0 || g_volStep <= 0)
     {
      Print("Falcon V7: symbol specification unavailable for ", g_sym);
      return INIT_FAILED;
     }
   if(InpSwingLeft < 1 || InpSwingRight < 1 || InpMssLen < 1 || InpSlLookback < 1 || InpMinSlPips <= 0 ||
      InpMaxSlPips <= InpMinSlPips || InpTargetPips <= 0 || InpHistoryBars < 300 || InpTrades < 1 || InpGoal <= 0)
     {
      Print("Falcon V7: invalid inputs");
      return INIT_PARAMETERS_INCORRECT;
     }
   g_rsiHandle = iRSI(g_sym, InpTF, InpRsiLen, PRICE_CLOSE);
   if(g_rsiHandle == INVALID_HANDLE)
      return INIT_FAILED;
   g_sig.active = false; g_sig.barTime = 0; g_sig.dir = 0; g_sig.sl = 0; g_sig.riskPips = 0; g_sig.text = "";
   ZeroMemory(g_stats);
   g_trade.SetExpertMagicNumber(InpMagic);
   EventSetTimer(15);
   g_lastBar = 0;
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   if(g_rsiHandle != INVALID_HANDLE)
      IndicatorRelease(g_rsiHandle);
   ObjectsDeleteAll(0, PFX);
   Comment("");
  }

void OnTick()
  {
   datetime t = iTime(g_sym, InpTF, 0);
   if(t != 0 && t != g_lastBar)
     {
      g_lastBar = t;
      OnNewBar();
     }
   ManagePositions();
  }

void OnTimer()
  {
   if(g_lastBar == 0)
      OnTick();
   ManagePositions();
   UpdatePanel();
  }

void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
  {
   if(id == CHARTEVENT_OBJECT_CLICK && sparam == PFX + "EXEC")
     {
      string msg;
      bool ok = Execute(msg);
      g_lastNote = msg;
      Notify("Falcon V7: " + (ok ? msg : "not placed: " + msg));
      UpdateButton();
      UpdatePanel();
     }
  }

void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD || trans.deal == 0)
      return;
   if(!HistoryDealSelect(trans.deal))
      return;
   if((ulong)HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != InpMagic)
      return;
   long entry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
   if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_OUT_BY)
      return;
   double pnl = HistoryDealGetDouble(trans.deal, DEAL_PROFIT) + HistoryDealGetDouble(trans.deal, DEAL_SWAP) + HistoryDealGetDouble(trans.deal, DEAL_COMMISSION);
   string msg = StringFormat("%s position closed: %+.2f · balance %.2f", HistoryDealGetString(trans.deal, DEAL_SYMBOL), pnl, AccountInfoDouble(ACCOUNT_BALANCE));
   Journal("CLOSE", msg);
   Notify("Falcon V7 " + msg);
   UpdatePanel();
  }
//+------------------------------------------------------------------+
