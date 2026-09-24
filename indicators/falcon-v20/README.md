# 🦅 Falcon V20: Trend-Sweep Scanner

**TradingView indicator (Android) → you place the order by hand in MT5 (Android).**
One chart, one alert, 11 symbols scanned on H4. Every alert carries the MT5 order to type.

- Indicator: [`falcon_v20.pine`](falcon_v20.pine)
- How the strategy was chosen: [`MEETING.md`](MEETING.md)
- Reproducible research: [`research/`](research)

---

## 1. The plan

| | |
|---|---|
| Start | **Fri 2 Oct 2026, 00:00 Kuwait** (Thu 1 Oct 17:00 New York) |
| Deadline | **Sun 1 Nov 2026, 00:00 Kuwait** (last trading close Fri 30 Oct) |
| Trading days | **21** |
| Account | JustMarkets Standard, **$30**, leverage **1:3000** |
| Goal | **$5,000** |
| Trades available | median **7** in 21 days (between 4 and 9 in 80% of months), one position at a time across 11 symbols |

### Probabilities (the numbers that matter)

These come from an exact dynamic programme over the strategy's 695 real trades, net of costs, using the risk that gives the highest probability of reaching each level:

| Aim | Maximum probability of reaching it by 1 Nov |
|---|---|
| $45 | 68.3% |
| $60 | 52.2% |
| $90 | 35.8% |
| $150 | 22.1% |
| $500 | 7.1% |
| $1,500 | 2.5% |
| **$5,000** | **0.77%** |

Sizing is set for **$5,000** by default. Along that path, the chance of reaching each level at some point is **$60: 37.6% · $150: 14.2% · $500: 5.3% · $1,500: 2.0% · $5,000: 0.73%**. In the other **99%** of runs the account ends below $3; that is how maximum-probability sizing works for a goal this large.

The setting **Size trades to maximise P of → Next milestone** switches the aim to the next rung ($60 → $150 → $500 → $1,500 → $5,000). The dashboard shows both probabilities live.

---

## 2. The strategy: C3 Trend-Sweep (H4)

It came first out of about 40 techniques and combinations tested by 5 research teams. It was the only one still positive after costs on instruments it never saw ([MEETING.md](MEETING.md)).

**BUY** when all of these are true on a closed H4 bar (SELL mirrors it):
1. **EMA 9 crosses above EMA 21.**
2. Within the last **6 H4 bars** there was a **sell-side liquidity sweep setup**:
   - price wicked below a swing low (5 bars left, 3 right) or the previous day's low, and closed back above it;
   - within 5 bars, a pin bar or a close above the prior 3 bars' highs confirmed it;
   - RSI(14) was below 70 and the sweep stop was no more than 100 pips.
3. **Stop:** 1.5 × ATR(14) from the close. **Target:** 2 × the stop distance (2R).

**Research results** (2.7 years, 11 instruments, net of spread and swap):

| Measure | Value |
|---|---|
| Trades | 695 |
| Win rate | 37.6% |
| Average | **+0.066R** per trade · profit factor 1.10 |
| Unseen instruments | **+0.198R** (first half) · **+0.018R** (second half) |

---

## 3. Setup on Android (no computer needed)

### A. Put the script into TradingView (once)
The TradingView **app** has no Pine Editor, so use the website in Chrome:
1. On your phone, open this file on GitHub, tap **Raw**, then **Select all → Copy**.
2. In Chrome, open **tradingview.com** and log in. Menu **⋮ → tick "Desktop site"**.
3. Open a chart and tap **Pine Editor** at the bottom. Delete the template, paste, and tap **Save** (name it *Falcon V20*), then **Add to chart**.
4. It's now in your account. In the **TradingView app**, open a chart, then **Indicators → My scripts → Falcon V20**.

### B. Settings (gear icon on the indicator)
- **① Plan:** start and deadline are preset (2 Oct and 1 Nov 2026). Start balance **30**, goal **5000**. **Current balance:** update it after every closed trade.
- **② Account:** leverage **3000**, margin safety **×3**, stop-out 50%, lot step 0.01.
- **③ Watchlist:** 11 symbols (OANDA feed). Set each **spread** to what MT5 shows for that symbol.
- Keep the chart on **4 hours (H4)**.

### C. One alert for everything
In the app: **Alerts → +** → Condition **Falcon V20** → **Any alert() function call** → notification **Push** → **Create**. That single alert covers all 11 symbols.

### D. When the alert arrives
It reads like this:
```
Falcon V20 · risk 100% toward goal $5000 · P(goal) 0.77%
BUY EURUSD @≈1.13950 | SL 1.13420 (53.0p) | TP 1.15010 (106.0p) | 0.05 lots, risk $26.50, win ≈ $53.00
```
1. Open **MT5 Android** → **Trade → +** (new order) → pick the symbol.
2. Type **Market Execution**, **Volume** = the lots shown.
3. **Stop Loss** and **Take Profit**: enter the prices shown. If your MT5 price differs slightly from TradingView's, keep the same **pip distances** from your fill price.
4. Tap **Buy** or **Sell**.
5. After the trade closes (stop or target), update **Current balance** in the indicator settings. The next lot size and the probabilities depend on it.

**Rules:** one position at a time (if two alerts come together, take the first line). Don't move the stop or target after entry.

---

## 4. Dashboard

| Row | Meaning |
|---|---|
| Plan | Day X of 21, trading days left |
| Balance → goal | From your input |
| **P(goal by deadline)** | Live maximum probability for your balance and trades left |
| **P(next $…)** | The same for the next milestone |
| Next trade risk | Optimal % of balance and $ for the next signal (and what it aims at) |
| Trades left (est.) | Trading days left × 0.33 (research average) |
| Scanner history | All symbols' past signals net of costs: trades, win %, R per trade |
| Last | The most recent alert text |

---

## 5. Verification

| Check | Result |
|---|---|
| Pine engine vs research, logic mirrored line by line | **800 / 800** signals identical |
| Scorecard vs research | Identical for every symbol (trades, wins, total R) |
| Policy tables in the indicator | Reproduce the dynamic programme: 0.771% vs 0.770% |
| Trading-day counter | 21 days for 2 Oct – 1 Nov 2026 |
| Syntax | Offline Pine parser: OK |
| Independent code review | A separate agent reviewed the Pine v6 code; findings are addressed in the file |

TradingView's own compiler isn't available in this environment. If it reports anything when you save, send me the message.

**Notes**
- The symbols are TradingView's OANDA feed. JustMarkets prices differ by a few points, which is why the pip distances are shown.
- Swap and spread are the biggest costs; the scorecard includes both.
- Research spreads are typical standard-account values. Check yours in MT5.
