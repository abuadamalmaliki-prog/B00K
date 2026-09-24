# ❄ Frostbite v2 · XAUUSD M5

Indicator: [`frostbite.pine`](frostbite.pine). Gold only, 5-minute chart only.

## What you see

| On the chart | Meaning |
|---|---|
| Smooth line, **blue** | Trend rising (Kalman filter of price) |
| Smooth line, **pink** | Trend falling |
| **BUY** blue tag under a candle | Buy signal |
| **SELL** pink tag above a candle | Sell signal |
| **Red** line + "SL …" tag | Stop loss |
| **Green dashed** line + "TP1 …" tag | Take profit 1 |
| **Green solid** line + "TP2 …" tag | Take profit 2 |
| Red / green shading | Risk zone / profit zone |
| **TP2 ✓✓**, **TP1 ✓**, **SL ✕** | How the trade ended |

The panel at the top right has three rows: the current state, the lots and today's signal count.

## How to take a signal (MT5)

1. Open **two** orders with the lot size shown, both with the **same SL**.
2. Order A: take profit = **TP1**. Order B: take profit = **TP2**.
3. If you get a **"Close now: 2-hour limit"** alert, close whatever is still open.

If a signal is marked **skip**, don't take it.

## Settings

| Setting | Default |
|---|---|
| Signals | **More** (about 2.3 a day) or **Fewer, stronger** (about 1.6 a day) |
| Balance ($) | 30 |
| Risk per signal (%) | 2 |
| Spread ($) | 0.30. Set it to what MT5 shows. |
| Show past trades | on |

## Test results (gold, $0.30 spread, periods not used for tuning)

| Mode | Signals / day | Trades | Avg per trade | With a wider spread ($0.45) |
|---|---|---|---|---|
| More | 2.3 | 821 | +0.05 × risk | +0.03 × risk |
| Fewer, stronger | 1.6 | 574 | +0.09 × risk | +0.07 × risk |

In both modes about **47% of trades end in profit**, so strings of 3–6 losing signals are normal. September 2026 is negative so far.

**Lot size:** gold's typical stop is about $13, so two 0.01-lot orders risk about $26. The panel and every alert show the exact lots and $ risk.

## Signal times (Malaysia)

| Setup | Hours |
|---|---|
| **ICICLE** (trend pullback) | 21:00 – 01:00 |
| **AVALANCHE** (break of yesterday's high/low) | all day, except about 04:00 – 06:00 |

## Setup on Android (once)

1. Open [`frostbite.pine`](frostbite.pine) on GitHub → **Raw** → **Select all → Copy**.
2. In Chrome, open **tradingview.com**, then **⋮ → Desktop site**. Open an **XAUUSD** chart, then **Pine Editor**. Paste, then **Save** and **Add to chart**.
3. In the TradingView app, open **XAUUSD** on **5 minutes**, then **Indicators → My scripts → Frostbite**.
4. **Alerts → +** → Condition **Frostbite** → **Any alert() function call** → **Push** → **Create**.

## Why these signals

The research team tested 46 techniques (1,422 settings) on 612,880 one-minute gold bars. Version 2 added four math-based families:
- Kalman trend/pullback
- Kalman slope flip
- Ehlers SuperSmoother + Fisher transform
- regression-slope t-statistic

They gave 2–5 signals a day, but all lost after the spread in 2025. So the Kalman filter draws the smooth trend line, and the signals come from the two setups that held up. The details are in [`MEETING.md`](MEETING.md) and [`research/`](research).

**Checks:**
- A bar-by-bar copy of the logic reproduces the research signals exactly: 1,026 / 1,026 in Fewer mode and 1,550 / 1,550 in More mode.
- The script passes the offline Pine parser.
- TradingView's own compiler isn't available here. If it shows an error when you save, send me the message.
