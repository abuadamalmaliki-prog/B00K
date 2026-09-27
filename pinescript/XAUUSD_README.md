# XAUUSD Asian Range Breakout (Auto TP/SL)

A TradingView **indicator** (Pine Script v6) for gold on **M5 or M15**. Each day it
draws the plan on the chart by itself: the Asian range, a **BUY STOP** and a
**SELL STOP** with their **SL** and **TP**. When one fills, it draws the trade as a
green TP zone and a red SL zone, then marks how the trade ended.

File: [`xauusd_asian_range_breakout.pine`](xauusd_asian_range_breakout.pine)

> **Read this first.** This is the only pattern, out of everything tested on 17
> years of gold data, that held up after costs. Its edge is **small**. On the
> held-out years 2018–2026 it made **+0.015 R per trade, which is not statistically
> significant**. Drawdowns reach 53 R. Forward-test it on a demo account before
> risking money.

## Your daily routine (Malaysia time)

Everything runs on the New York clock, because gold's daily break and the US data
releases follow New York's daylight saving. The dashboard shows today's times in
Malaysia time automatically; they shift by one hour twice a year:

| Step | New York | Malaysia, Nov – Mar | Malaysia, Mar – Nov |
|---|---|---|---|
| Asian range is measured | 18:30 – 03:00 | 07:30 – 16:00 | 06:30 – 15:00 |
| Place **both** stop orders | 03:00 (London open) | **16:00** | **15:00** |
| Cancel the order that did not fill | 08:20 (COMEX open) | 21:20 | 20:20 |
| Close any open trade | 13:30 | 02:30 (next day) | 01:30 (next day) |

**The orders:**
- **BUY STOP** at the range high. SL = range low. TP = entry + 3 × (entry − SL).
- **SELL STOP** at the range low. SL = range high. TP = entry − 3 × (SL − entry).
- Only one trade per day: when one order fills, cancel the other (OCO).

Use **pending stop orders**. Waiting for a candle to close beyond the range and
then entering at market roughly halves the edge (tested; see below).

The "Plan ready" alert fires as soon as the range completes, with both levels in
the message, so you do not have to watch the chart.

## What you see on the chart

| Drawing | Meaning |
|---|---|
| Orange box | The Asian range, extended to the order-cancel time |
| Green / red dashed lines with labels | The BUY STOP and SELL STOP levels, each with its SL and TP |
| **BUY** / **SELL** label | The order that filled, with the fill time in your time zone |
| Green box | Entry to TP |
| Red box | Entry to SL |
| Small label at the end | How it ended: TP, SL or TIME, with the result in R |
| Dashboard | Today's times, today's plan, the open trade, and stats for the trades on your chart |

## How this pattern was found

The request was a "hidden gem" for XAUUSD on M5/M15. The honest answer first:
firms like Jane Street make money from market making, speed and infrastructure,
not from chart patterns posted on GitHub. Anything public that claims that level
of edge is almost certainly overfit. What can be done is to test what is out
there on enough data, with costs, and keep only what survives.

**Data:** 5.9 million one-minute XAUUSD bars, March 2009 – January 2026
(HistData.com via the Hugging Face dataset `fokan/xauusd-2009-2026`), built into
M5 and M15 bars. The files' clock is New York time up to 2018, but from 2019 it is
London time minus 5 hours: it switches daylight saving on the European dates, so for
about four weeks a year it is an hour behind New York. All bars were converted to
true New York time (after that, gold's 17:00–18:00 break sits at 17:00 on every day
of every year). January–July 2023 is missing 30–40 % of its minutes. Costs: 1 bp of price per round trip (about 0.30 USD at 3000 USD
gold), with 2 bp as a stress test. Settings were chosen on 2009–2017 only;
2018–2026 was held out.

**GitHub strategies checked:**

| Repository | Finding |
|---|---|
| [ilahuerta-IA/backtrader-pullback-window-xauusd](https://github.com/ilahuerta-IA/backtrader-pullback-window-xauusd) | Claims Sharpe 0.89, but 3,450 lines, dozens of toggles, different long and short settings, and re-tuning left in the comments; tested only on the period it was tuned on. Overfit by construction. |
| [soloshun/Quantitative-XAUUSD-Strategy](https://github.com/soloshun/Quantitative-XAUUSD-Strategy) | XGBoost / LSTM / Transformer session models: its own reports show 47–56 % direction accuracy (coin flip) and a 9 % return vs 73 % for buy and hold. |
| [doaneruby970-hub/gold-trader](https://github.com/doaneruby970-hub/gold-trader) | Mostly grid EAs; the long-only grid relies on gold's 2021–2026 bull run; brute-force optimised. |
| [wareshgold/xauusd-strategy-a](https://github.com/wareshgold/xauusd-strategy-a) | Strategy not implemented yet. |

**Patterns tested on the 17 years** (all in `xauusd_research/research.py`):

| Pattern | Result |
|---|---|
| **+1.5 to +3.7 bp at 18:00 New York, every era, t up to 9** | **Fake.** It all happens in the first minute after the daily reopen, where the bar range is 3× normal: spreads normalising, not a tradable move. This is exactly the "pattern that always happens" that looks great on a chart and loses live. |
| Pin bar, engulfing, inside-bar break (M5 and M15) | No edge. Engulfing and inside-bar breaks actually reverse afterwards (t −2 to −5). |
| Three bars in a row → reversal | Real and stable (t −5 to −9), but worth 0.1–0.3 bp against a ~1 bp cost. Not tradable. |
| London fix drop (05:00 NY), 09:30 drop / 10:00 rebound | Strong in 2009–2014, faded since the 2015 fix reform. |
| One session predicting the next (intraday momentum) | Nothing survives; signs flip between halves. |
| London opening-range breakout | In-sample Sharpe 0.65–0.96; out of sample 0.24 (1R) and −0.26 (2R). |
| COMEX opening-range breakout | No edge. |
| **Asian-range breakout at London open** | **Positive in every era, for both BUY and SELL. The only survivor.** |

The Asian session (your daytime) is also where the academic "gold rises in Asian
hours" effect lives: it was the only session with positive returns in all four
eras, even in 2009–2013 when gold fell overall.

**Choosing the settings without overfitting:** 120 variants of the breakout
(exit time, TP multiple, stop placement, entry window) were all positive
in-sample, and 78 % stayed positive out of sample. Picking the single best
in-sample row would have been a mistake (its out-of-sample Sharpe was −0.06), so
the settings were chosen by the average of each variant and its neighbours,
in-sample only: SL at the other side of the range, entries until 08:20, TP 3R,
time exit 13:30. Moving the range window anywhere from 18:05–20:00 to 02:00–03:00
changes little (Sharpe 0.56–0.74 on a per-trade bp basis), so it is a plateau,
not a spike.

## Results (1 R risked per trade, net of 1 bp cost)

| | M5 | M15 |
|---|---|---|
| Trades | 3,720 (~220 / year) | 3,767 |
| Winners | 44 % | 44 % |
| Average per trade, all years | +0.041 R (t = 2.13) | +0.043 R (t = 2.25) |
| 2009–2017 (settings chosen here) | +0.065 R (t = 2.34) | +0.067 R (t = 2.43) |
| **2018–2026 (held out)** | **+0.015 R (t = 0.55)** | **+0.017 R (t = 0.63)** |
| Total | +153 R | +163 R |
| Worst drawdown | 53 R | 53 R |
| Years positive | 9 of 17 | 9 of 17 |
| How trades end | time exit 55 %, SL 38 %, TP 6 % | about the same |

Per year on M5 (R): 2009 +24, 2010 −5, 2011 −3, 2012 −7, 2013 +52, 2014 −4,
2015 +41, 2016 +5, 2017 +24, 2018 +24, 2019 −3, 2020 +18, 2021 −20, 2022 +25,
2023 −22, 2024 +13, 2025 −8.

Two more findings:
- Measured per trade in bp (the same lot size every trade instead of the same risk), the held-out result was better: Sharpe about 0.50. The profit concentrates on wide-range, volatile days, which fixed-risk sizing trades smaller.
- At 2 bp cost the edge roughly halves.

## Limitations

- The edge is small, and it is not statistically significant on the held-out years. Profit came mostly from a few strong years; recent years were mixed (2021 −20 R, 2023 −22 R, 2025 −8 R).
- 44 % winners and a 53 R worst drawdown: at 0.5 % risk per trade that is about a 26 % account drawdown.
- The test used HistData prices. Your broker's feed, spread at the London open and slippage on stop orders will differ.
- The backtest fills stop orders exactly at the level (at the open when price gaps through), and counts a bar that touched both TP and SL as a loss.
- The dashboard's statistics come from the bars loaded on your chart, net of the cost you set.

## How it was checked

1. **TradingView compiler:** 0 errors, 0 warnings.
2. **Mirror reproduces the research:** `verification/xau_mirror.py`, a line-by-line Python port of the indicator, reproduces the 17-year backtest exactly (3,720 trades, +153.3 R, 52.8 R drawdown on M5).
3. **Real script on real data:** the actual `.pine` file was run in [PineTS](https://github.com/LuxAlgo/PineTS) on real gold bars and compared with the mirror bar by bar, on three slices:
   - M5, Feb – Apr 2024: the US daylight-saving switch and the three weeks when New York and London clocks are misaligned.
   - M5, Oct – Dec 2024: the switch back.
   - M15, all of 2025.

   Every plan, BUY, SELL, TP, SL and time exit, and every price and R value, matched exactly.

Reproduce everything:

```bash
cd pinescript/xauusd_research
python3 get_data.py        # downloads ~400 MB, builds M5/M15
python3 research.py        # every table above
cd ../verification
./run_all.sh               # PineTS vs mirror, including the XAUUSD slices
```

## Sources

- XAUUSD M1 data: [fokan/xauusd-2009-2026](https://huggingface.co/datasets/fokan/xauusd-2009-2026) (HistData.com format)
- Intraday gold seasonality (gold rising in Asian hours): [Copenhagen Business School thesis, 2019](https://research.cbs.dk/files/59803241/651553_Thesis_Contract_13383.pdf)
- Pine v6 idioms: [jayadevrana/free-pine-script-indicators](https://github.com/jayadevrana/free-pine-script-indicators); test runtime: [LuxAlgo/PineTS](https://github.com/LuxAlgo/PineTS)
