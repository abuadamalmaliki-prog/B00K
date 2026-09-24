# ❄ Frostbite: gold scalper

**TradingView indicator (Android) → you place the orders by hand in MT5 (Android).**
Every signal comes with **BUY or SELL, one stop loss (SL), TP1 and TP2**, plus the lot size.

- Indicator: [`frostbite.pine`](frostbite.pine)
- How it was chosen: [`MEETING.md`](MEETING.md)
- Research, data sources and code: [`research/`](research) and [`research/SCOUT_REPORT.md`](research/SCOUT_REPORT.md)

---

## 1. What it trades

Two setups, found by a 5-agent team that tested **46 techniques (1,422 settings)** on **612,880 one-minute gold bars** (January 2025 – September 2026, spread included):

| Setup | When (Malaysia time) | Rule | SL | TP1 | TP2 |
|---|---|---|---|---|---|
| **ICICLE** | 21:00 – 01:00 | EMAs 34 > 50 > 200 (or the reverse for SELL). Price dips to the EMA34, then a strong candle closes back through the previous bar. ADX(14) > 20, RSI(14) 45–70 for BUY, 30–55 for SELL. | Beyond the 5-bar swing ± 0.2 ATR (0.6–3 ATR) | 1 × risk | 2 × risk |
| **AVALANCHE** | all day, except about 04:00 – 06:00 (05:00 – 07:00 from November) | The first 15-minute close above **yesterday's high** (BUY) or below **yesterday's low** (SELL). The last hourly close must be on the same side of the hourly EMA50. | 1.5 × ATR(14) of M15 | 1.5 × risk | 3 × risk |

- **Frequency:** about **1.5 signals per day**. Trades last about 80 minutes (median), and anything still open after **120 minutes** is closed.
- **One trade at a time.** If both setups fire together, ICICLE goes first.

## 2. The honest numbers (gold, $0.30 spread)

These are the periods that were **not** used to tune the settings: May–August 2026, all of 2025, and 1–23 September 2026.

| | |
|---|---|
| Trades | 574 |
| Trades that end in profit | 47% |
| TP1 reached | 41% |
| TP2 reached | 15% |
| Average per trade | **+0.09 × risk** (profit factor 1.20) |
| With a wider $0.45–0.60 spread | +0.07 / +0.05 × risk |
| Months positive | 17 of 21 |
| Worst losing streak / largest drawdown | 6 trades / 11.6 × risk |
| September 2026 so far | −0.17 × risk over 27 trades |

The edge is small and not proven. These two setups were the best of 46, and September 2026 is negative so far. No technique passed every test on its own ([MEETING.md](MEETING.md)).

## 3. Lot size on a $30 account

Gold's typical Frostbite stop is about **$13**. At the minimum 0.01 lot, $1 of price movement = $1.

| | Stop | Two orders × 0.01 lot risk |
|---|---|---|
| Typical ICICLE | $8 – $22 (median $13) | **$17 – $45** (median $26) |
| Typical AVALANCHE | $11 – $20 (median $14) | **$22 – $41** (median $28) |

On a $30 Standard account, one signal at the minimum lot therefore risks most of the balance. Every alert shows the exact $ risk and its % of your balance, and flags it when the minimum lot is above your risk setting (default 2%).

JustMarkets' **Standard Cent** account trades the same signal 100× smaller: two 0.01-lot orders risk about $0.26. If you use it, enter your balance in the same units MT5 shows (cents), and set **Contract size** to match the MT5 symbol specification.

---

## 4. Setup on Android (no computer needed)

### A. Put the script into TradingView (once)
The TradingView **app** has no Pine Editor, so use the website in Chrome:
1. Open [`frostbite.pine`](frostbite.pine) on GitHub, tap **Raw**, then **Select all → Copy**.
2. In Chrome, open **tradingview.com** and log in. Menu **⋮ → tick "Desktop site"**.
3. Open an **XAUUSD** chart, tap **Pine Editor**, delete the template, paste, then **Save** (name it *Frostbite*) → **Add to chart**.
4. In the **TradingView app**: chart → **Indicators → My scripts → Frostbite**.

### B. Chart and settings
- Chart: **XAUUSD, 5 minutes (M5)**. The panel's first row turns green: *M5 ✓ signals and alerts on*.
- **③ Lot size:** enter your **balance** and **risk %**. Set **Spread** to what MT5 shows for gold (default $0.30).
- Leave **①** and **②** as they are. These are the tested settings.

### C. One alert
**Alerts → +** → Condition **Frostbite** → **Any alert() function call** → notification **Push** → **Create**. This one alert sends every signal and every trade event (TP1, TP2, SL, time limit).

### D. When a signal arrives
```
❄ FROSTBITE AVALANCHE · BUY XAUUSD @≈4312.40 | SL 4298.60 ($13.80) | TP1 4333.10 | TP2 4353.80 |
2 orders × 0.01 lots, total risk ≈ $28.20 (94% of balance) ⚠ the minimum lot is above your risk setting | close after 120 min
```
1. **MT5 → Trade → +** → XAUUSD → **Market Execution**, Volume = the lots shown.
2. **Order A:** Stop Loss = **SL**, Take Profit = **TP1** → **Buy/Sell**.
3. **Order B:** the same volume and **SL**, Take Profit = **TP2** → **Buy/Sell**.
4. If your MT5 price differs a little from TradingView's, keep the same **distances** from your fill price.
5. Leave both orders alone. If you get a **"Time limit: close the open Frostbite order(s) now"** alert, close whatever is still open.

If an alert says **"cancelled: price opened beyond a level"**, skip that signal.

---

## 5. The panel

| Row | Meaning |
|---|---|
| Chart | Green on M5. Red means switch to M5: signals and alerts are off. |
| Now | Waiting, or the open trade and whether TP1 is done |
| Levels | SL · TP1 · TP2 of the open trade |
| Last signal / Last event | With Malaysia time |
| This chart | Trades, win %, TP1 %, TP2 % on the loaded history (5-minute bars, your spread) |
| Avg per trade | The same, in × risk after spread |
| Research (gold) | The out-of-sample figure from section 2 |
| Yesterday | The high and low that AVALANCHE watches (also drawn as faint lines) |

## 6. Other pairs
The rules run on **any symbol**: lot size, contract size and spread switch automatically (forex 100,000 units, silver 5,000 oz). The research only proved it on **gold**, so other pairs are untested.

## 7. Verification
| Check | Result |
|---|---|
| Pine logic mirrored bar by bar in Python vs the research | **1,026 / 1,026 signals identical** |
| Chart scorecard vs the 1-minute research engine | Same trades; averages within 0.015 × risk |
| Research data vs GitHub copies of Jan–Aug 2026 gold | identical, minute for minute |
| Pine syntax | offline parser OK |
| Independent code review | A separate agent checked the Pine v6 code line by line against the mirror. It found no compile errors and confirmed exact parity. Six issues were fixed: Avalanche could stay off if the first bar started with an empty value; bars cut short at session end broke the M15/H1 timing; exit at a new trading day; panel state after a new signal; the cancel alert is now sent at once; lot size for SELL orders and non-USD pairs. Re-parsed and re-verified (1,026 / 1,026). |

TradingView's own compiler isn't available here. If it reports anything when you save, send me the message.
