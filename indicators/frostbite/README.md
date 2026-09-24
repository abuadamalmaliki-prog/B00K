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

The alert tells you how many orders to open:
- **1 order** (Auto picks this on $30): SL = **SL**, TP = **TP2**.
- **2 orders**: both with the same **SL**. Order A has TP = **TP1**, order B has TP = **TP2**.

If you get a **"Close now: 2-hour limit"** alert, close whatever is still open.

If a signal is marked **skip**, don't take it.

## Settings

| Setting | Default |
|---|---|
| Signals | **More** (about 2.3 a day) or **Fewer, stronger** (about 1.6 a day) |
| Balance ($) | 30 |
| Risk per signal (%) | 2 |
| Orders per signal | **Auto**: 1 order → TP2 on small balances, 2 orders → TP1 + TP2 when the balance allows |
| Spread ($) | 0.30. Set it to what MT5 shows. |
| Show past trades | on |

## Test results (gold, $0.30 spread, periods not used for tuning)

| Mode | Signals / day | Trades | 2 orders: avg | 1 order → TP2: avg | Longest losing streak (1 order) |
|---|---|---|---|---|---|
| More | 2.3 | 821 | +0.05 × risk | +0.06 × risk | 9 |
| Fewer, stronger | 1.6 | 574 | +0.09 × risk | +0.11 × risk | 6 |

About 43–47% of trades end in profit, so strings of losing signals are normal. September 2026 is negative so far.

**Your $30 account:** 0.01 lot of gold moves $1 per $1. A typical stop of about $13 therefore risks about $13 with 1 order and about $27 with 2. The panel and every alert show the exact $ risk and its % of your balance. The account notes are in [`ACCOUNT.md`](ACCOUNT.md).

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
