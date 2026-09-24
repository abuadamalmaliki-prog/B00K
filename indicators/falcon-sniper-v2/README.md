# 🎯 Falcon Sniper V2

A **sniper-entry** indicator for TradingView (Pine Script v6). It waits for a liquidity sweep, confirms it with a rejection candle inside a London or New York kill zone, sets a tight stop behind the sweep, and aims for a **300-pip final target**. On the way it takes partial profits at 50 and 150 pips and protects the trade.

File: [`falcon_sniper_v2.pine`](falcon_sniper_v2.pine). V1 is still available in [`../falcon-confluence-pro`](../falcon-confluence-pro).

---

## 1. Install (2 minutes)

1. Open TradingView and pick an instrument (e.g. `OANDA:XAUUSD`, `OANDA:USDJPY`, `OANDA:EURUSD`).
2. Open **Pine Editor**, delete the template, paste the whole file, and click **Save**, then **Add to chart**.
3. Set the chart timeframe (see [section 5](#5-timeframe-masterclass-for-a-300-pip-target)). **H4 is the default recommendation.**
4. Check the dashboard row **Pip · target reach**. It must show the right pip size for your instrument (section 4).

---

## 2. What's inside: 20+ techniques in 6 layers

| Layer | Techniques | Role |
|---|---|---|
| **Liquidity** | Swing highs/lows (pivots), previous-day high/low, stop-hunt sweeps | **Hard gate**: no sweep, no trade |
| **Trigger** | Pin-bar rejection, micro market-structure shift (MSS), engulfing (optional) | **Hard gate**: the "trigger pull" |
| **Timing** | London kill zone, New York kill zone (New York time, DST-aware) | **Hard gate** below 4H |
| **Structure & zones** | BOS, CHoCH, Fair Value Gaps, Order Blocks, premium/discount, OTE 61.8% | Drawn on the chart and scored |
| **Context** | HTF EMA 50/200 bias, EMA 50/200 trend, RSI turn, MACD, displacement, relative volume | Scored (13-point confluence) |
| **Risk** | Stop behind the sweep, 10–100 pip stop band, ≥ 3:1 reward:risk to final target, 3 targets, breakeven, trail | Every signal |

Hover over any 🎯 signal label to see which of the 13 confluence factors passed.

### Why not 500 or 1,000 techniques?

I tested it. Before choosing the defaults, every technique above was run on two years of real H1/H4 data for EURUSD, GBPUSD, AUDUSD, USDJPY and gold, about 13,000 simulated setups:

| Finding | Evidence |
|---|---|
| **Liquidity sweeps** had an edge | +0.035R per trade with a sweep vs −0.028R without |
| **Pin-bar rejections** had an edge | +0.027R, the best of the triggers |
| **Kill-zone timing** had an edge | +0.023R inside vs −0.024R outside |
| Order blocks, engulfing, HTF trend filter, RSI turn | Flat to slightly negative |
| **Stacking more confluence made it worse** | Setups scoring 4–7 of 13 averaged **+0.2R**; setups scoring 8+ averaged **−0.02R** |

Most indicators are built from the same few inputs (price and volume), so adding hundreds of them mostly repeats the same information. Each extra filter removes good trades as well as bad ones. So V2 uses the few techniques that held up across instruments and time as **gates**, and shows everything else as **context**. That is also why *Minimum confluence* defaults to 0.

---

## 3. The sniper setup: exactly when a signal prints

**BUY** (SELL is the mirror image) prints on a **closed** bar only when all of these are true:

1. **Sweep.** Within the last 5 bars, price wicked **below** a confirmed swing low or the previous day's low and **closed back above** it. That's a stop hunt: sell-side liquidity has been taken.
2. **Trigger.** The bar is a **pin bar**: lower wick ≥ 2× the body and ≥ half the bar, close in the top third. Or it's an **MSS**: a bullish close above the highs of the last 3 bars.
3. **Kill zone.** The bar is inside London (02:00–05:00 New York time) or New York (07:00–10:00 New York time). On 4H and higher charts this rule is off.
4. **Tight stop.** The stop sits beyond the lowest low of the last 5 bars (the sweep wick) plus a 3-pip buffer. It must be **≤ 100 pips**, and **300 pips ÷ stop ≥ 3**. Stops tighter than 10 pips are widened to 10.
5. **Not chasing.** RSI is below 70.
6. **Spacing.** At least 3 bars since the last signal, and no long already open.

An opposite signal closes the open trade (reversal) and opens the new one.

**Non-repainting.** Signals only appear on closed bars. Swings are used only after they're confirmed. HTF and previous-day data come only from closed bars.

---

## 4. Pips: what "300 pips" means on each instrument

Set the pip size correctly, or every target is wrong. Auto mode handles forex and metals. For everything else, choose **Manual**.

| Instrument | 1 pip | 300 pips = | Auto? |
|---|---|---|---|
| EURUSD, GBPUSD, AUDUSD, most FX | 0.0001 | 0.0300 in price | ✅ |
| USDJPY, EURJPY, GBPJPY (JPY-quoted) | 0.01 | 3.00 yen | ✅ |
| **XAUUSD (gold)** | **0.10** | **$30.00** | ✅ |
| XAGUSD (silver) | 0.01 | $3.00 | ✅ |
| US30, NAS100, BTCUSD… | broker-specific | set **Manual** (usually 1.0) | ❌ |

### Targets and trade management (defaults)

| Level | Distance | What happens |
|---|---|---|
| **TP1** | +50 pips | Close ⅓. Stop moves to **breakeven**, so the trade can't lose from here (barring a gap). |
| **TP2** | +150 pips | Close ⅓. Stop moves to **TP1**, locking in profit. |
| **TP3** 🎯 | **+300 pips** | Close the last ⅓. Full target. |

Switch off *Scale out* to hold everything for 300 pips. TP1 and TP2 then only move the stop.

### Position size: always risk a fixed %, not fixed lots

```
Lots = (Account × Risk %) ÷ (Stop in pips × Pip value per lot)
```

| Instrument | Pip value per 1.00 standard lot |
|---|---|
| EURUSD, GBPUSD, AUDUSD | $10 |
| USDJPY | ≈ $6.5–7 (1,000 JPY) |
| XAUUSD (100 oz) | $10 per 0.10 move |

**Example.** A $10,000 account risking 1% has $100 at risk. With a 25-pip stop on EURUSD that's $100 ÷ (25 × $10) = **0.40 lots**. With a 60-pip stop on gold it's $100 ÷ (60 × $10) = **0.16 lots**.

---

## 5. Timeframe masterclass for a 300-pip target

### 5.1 How far is 300 pips?

Measured over the last 12 months of data:

| Instrument | Average daily range | 300 pips equals | What that means |
|---|---|---|---|
| **XAUUSD** | ~1,050 pips ($105) | **0.3 days** | 300 pips is a normal intraday move, the **best fit** |
| **USDJPY** | ~94 pips | **3.2 days** | A few days' swing |
| GBPUSD | ~71 pips | 4.2 days | About a week's swing |
| EURUSD | ~54 pips | 5.6 days | 1–2 week trend |
| AUDUSD | ~47 pips | 6.4 days | 1–2 week trend, rarely reached |

**Lesson 1.** Pick the instrument before the timeframe. On gold, 300 pips is routine. On EURUSD it's a multi-day trend, so most of the profit comes from TP1/TP2 and TP3 is a bonus.

### 5.2 Top-down analysis: three timeframes, three jobs

| Job | Question it answers | Timeframe |
|---|---|---|
| **Bias** | Which way is the big money flowing? Where is liquidity resting? | Daily / Weekly |
| **Setup** | Has liquidity just been swept into a zone? | **H4** (or H1) |
| **Entry** | Exact trigger candle and tight stop | Where the indicator runs |

**Rule of thumb:** each timeframe is **4–6× the one below it**, e.g. W → D → H4, or D → H4 → H1. The indicator's HTF row does this automatically: an H1 chart reads H4 bias, and an H4 chart reads Daily.

### 5.3 Which chart to run Falcon Sniper on

These are backtest results with default settings over about 2 years of data, before costs:

| Chart | Result | Recommendation for a 300-pip target |
|---|---|---|
| **H4** | 1,332 trades · PF **1.21** · avg **+0.10R** per trade · profitable in **both halves** of the period (PF 1.12 → 1.29) | ✅ **Primary.** Best balance of noise and target size. |
| **H1** | 1,387 trades · PF 1.07 · positive on EURUSD (1.32) and GBPUSD (1.16), negative on AUDUSD, USDJPY and gold · first half PF 0.92, second half 1.23 | ⚠️ Majors only (EURUSD, GBPUSD). Expect weaker, less stable results. |
| M15 / M5 | Too little clean data to judge. Stops of 10–15 pips against a 300-pip target mean TP3 is almost never reached. | ❌ Not for a 300-pip target. Use R-multiple targets instead. |
| Daily | The 100-pip stop cap filters out almost every setup | ❌ Too few signals. Use D/W for **bias** only. |

**H4 per instrument:**

| H4 | Trades/month | Win rate | TP1 hit | TP2 hit | **TP3 (300p) hit** | Profit factor | Median stop |
|---|---|---|---|---|---|---|---|
| **XAUUSD** | 0.8 | 45.8% | 54.2% | 37.5% | **16.7%** | 1.70 | 81 pips |
| **USDJPY** | 8.3 | 56.1% | 53.6% | 15.8% | 4.0% | **1.68** | 52 pips |
| EURUSD | 9.2 | 41.1% | 30.4% | 3.9% | 0.3% | 1.28 | 34 pips |
| GBPUSD | 11.0 | 41.5% | 32.2% | 5.1% | 0.8% | 1.02 | 43 pips |
| AUDUSD | 10.5 | 40.1% | 22.4% | 1.4% | 0.3% | 1.02 | 31 pips |

**Lesson 2.** Hit rates fall steeply as the target gets further away. That's normal. A sniper system makes its money by losing small (−1R) and letting a minority of trades run.

### 5.4 Kill zones in your local time (Kuwait, UTC+3, no daylight saving)

| Kill zone | New York time | Kuwait time: Nov → Mar | Kuwait time: Mar → Nov |
|---|---|---|---|
| **London** | 02:00–05:00 | **10:00–13:00** | **09:00–12:00** |
| **New York** | 07:00–10:00 | **15:00–18:00** | **14:00–17:00** |

The indicator converts times automatically and shades the kill zones on the chart. The two columns differ because the US changes its clocks and Kuwait doesn't.

### 5.5 Your routine, step by step

1. **Sunday:** on the **Weekly/Daily** chart, mark the obvious highs and lows where stops are resting.
2. **Each session:** open the **H4** chart (H1 for EURUSD/GBPUSD) with Falcon Sniper, and set alerts (section 7).
3. **Alert fires:** check the dashboard. Is the sweep real (a clear wick through a level)? Is the stop inside your risk budget?
4. **Enter** at the close of the signal bar. Place the stop and the three targets exactly as drawn. Size the position with the formula in section 4.
5. **Manage by the rules:** after TP1 the stop goes to breakeven; after TP2 it moves to TP1. **Never move a stop further away.**
6. **Review weekly:** compare the dashboard scorecard (win rate, TP hit rates, net pips, drawdown) with your own results.

**Expected holding time for TP3:** gold, hours to about 2 days. USDJPY and GBPUSD, several days. EURUSD and AUDUSD, one to two weeks.

---

## 6. Dashboard

| Row | Meaning |
|---|---|
| Liquidity | Which side was swept, and how recently |
| Kill zone | London ✓ / New York ✓ / Closed / n/a on 4H and higher |
| Structure | Last break direction, and whether a fresh CHoCH printed |
| Price zone | Discount / Premium, and whether price is in the OTE zone of the current range |
| Zones FVG · OB | Active bullish ▲ and bearish ▼ zones |
| HTF bias | Higher-timeframe EMA bias (informational unless the HTF gate is on) |
| Confluence L / S | 13-factor score for each side (context, not a quality grade) |
| Pip · target reach | Pip size in use, and 300 pips as a multiple of the daily ATR |
| Position / Stop / Open P&L | The live trade, in pips and in R |
| Scorecard | Closed trades, win rate, TP1/2/3 hit rates, net pips, net R, profit factor, max drawdown |

---

## 7. Alerts

Right-click the chart → **Add alert** → Condition: **Falcon Sniper V2**:

- **Any alert() function call** (recommended). Every closed bar that has news sends one message, including the full plan, for example:
  `SNIPER BUY (Pin bar, 7/13) | Entry 1.08520 | SL 1.08270 (-25.0p) | TP1 … | TP2 … | TP3 …`
  It also sends TP-hit, stop and reversal events.
- **Falcon Sniper · Buy / Sell / Any signal**: simple versions.

Always set the alert frequency to **Once Per Bar Close**.

---

## 8. Settings that matter most

| Setting | Default | Change it when… |
|---|---|---|
| Pip size | Auto | You trade indices, crypto or stocks (set Manual) |
| TP1 / TP2 / TP3 pips | 50 / 150 / 300 | Your instrument's daily range makes 300 unrealistic (section 5.1) |
| Stop min / max | 10 / 100 pips | Gold on H4 needs room. Stops are often 60–100 pips. |
| Setup location | Liquidity sweep | "Any POI" gives more signals and tested weaker |
| Entry trigger | Pin bar + MSS | "Pin bar only" gives fewer, cleaner signals |
| HTF gate | Off | You only want trades with the higher-timeframe trend (tested weaker, but it's your call) |
| Kill zones | On, trade only inside | Switch the gate off to see every setup on H1 and below |

---

## 9. Honest limitations. Read before risking money.

- The backtest covers about 2 years on five instruments. Reproduce it yourself with [`research/`](research): run `python3 fetch.py`, then `python3 backtest.py`. That's a line-for-line Python mirror of the indicator's logic. It includes **no spread, commission or slippage**, which matter most on tight stops. Past results do not guarantee future results.
- The edge measured is **modest**: about +0.1R per trade on H4. That's real money over many trades with disciplined sizing. It doesn't win every trade and it's not a money printer.
- A 300-pip target is **rarely reached** on EURUSD and AUDUSD (under 1% of trades on H4). It's reached far more often on gold and USDJPY.
- Forward-test on a **demo account** for at least 30 trades before going live, and never risk more than 1–2% per trade.
- This is a decision-support tool, not financial advice.
