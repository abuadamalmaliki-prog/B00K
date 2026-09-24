# Team meeting: which XAUUSD scalping technique goes into Frostbite?

## Who took part
| Agent | Job |
|---|---|
| Scout | Searched GitHub for January–August 2026 gold data and for open trading-technique material: books, open-source indicators, EAs |
| Team A | Trend and momentum scalps |
| Team B | Mean-reversion scalps |
| Team C | Breakouts and session timing |
| Team D | Price action and smart-money concepts (SMC) |
| Lead | Data, shared engine, protocol, meeting, combinations, indicator |

## Data
- **612,880 one-minute XAUUSD bars**, bid and ask, from 1 January 2025 to 23 September 2026 (Dukascopy public feed).
- **Cross-check.** The scout found the same January–August 2026 data published on GitHub (`Dypoi/XAUUSD_Dataset` and three other repositories). Every overlapping minute matches exactly, with a time offset of 0 hours. An independent MT5 broker feed on GitHub (`AhadRasheed/gold-strategy`) has an M5 return correlation of 0.998 with it.
- **Costs.**
  - $0.30 spread (JustMarkets Standard, typical), plus the real feed's widening around news and rollover.
  - Buys fill at the ask; sells fill at the bid and are stopped on the ask.
  - If a one-minute bar touches both the stop and a target, the **stop wins**.
  - Everything is flat before the 17:00 New York rollover.

## Protocol (identical for every team)
- **Tuning:** only on **DISC = January–April 2026**, with at most about 40 settings per family.
- **Frozen settings, then tested unchanged on:**
  - **VAL**: May–August 2026
  - **Y2025**: all of 2025
  - **HOLD**: 1–23 September 2026
- **Also required:** a random-entry control and a stress test (spread $0.45 plus $0.05 slippage).
- **Every signal has one SL, a TP1 and a TP2.**

## Results by team (46 families, 1,422 settings)
| Team | Families | Settings tried | Passed | Closest |
|---|---|---|---|---|
| A · trend/momentum | 10, incl. scout #1–3 | 297 | 0 | **FA Gold Scalper (EMA 34/50/200 pullback, M5, 13–17 UTC):** VAL +0.119R, 2025 +0.069R, stress +0.094R; t = 0.93 |
| B · mean reversion | 11, incl. scout #10, #12, #13, #20 | 360 | 0 | $5 round-number fade: VAL +0.028R, 2025 −0.023R |
| C · breakouts/sessions | 12, incl. scout #4–6, #8, #11, #14, #19 | 392 | 0 | **Prior-day high/low close-beyond (M15, H1 EMA50 side):** VAL +0.105R, 2025 +0.120R, stress +0.092R; t = 0.78 |
| D · price action/SMC | 13, incl. scout #15–18 | 373 | 0 | **Silver Bullet FVG (M5):** VAL +0.150R, 2025 +0.036R, stress +0.110R; t = 0.89 |

**What the teams found:**
- **Most families were no better than random entries after costs.** At a $0.30 spread, M1 scalps lose to costs: the spread is about 0.1R there.
- **High win rates came from exit shape, not edge.** Setups with small targets (TP1 at 0.5R plus breakeven) won 59–76% of trades, but their average result stayed near zero or below.
- **The GitHub techniques did no better.** Techniques taken from the scout's sources that looked strong in January–April (ICT sweeps, SMC fair value gaps, the M1 z-score scalper) all failed on May–August.

## The three near-misses, side by side
Each was positive in January–April, May–August, 2025 and the stress test. None was individually significant. OOT means every period not used for tuning (VAL + 2025 + HOLD).

| | OOT trades | OOT avg R | t | Stress OOT | Neighbouring settings positive |
|---|---|---|---|---|---|
| A · FA Gold Scalper | 284 | +0.068 | 1.11 | +0.042 | 26 / 27 |
| C · prior-day high/low | 306 | +0.106 | 1.58 | +0.084 | 15 / 15 |
| D · Silver Bullet | 235 | +0.050 | 0.61 | **−0.016** | 17 / 18, but −0.083 without its trend filter |

The daily results of the three are uncorrelated (|r| ≤ 0.06), so combining them adds independent trades.

## Decision
**Frostbite = A + C, one trade at a time.** Team A's setup is renamed **Icicle** and Team C's **Avalanche**.
- **D is dropped** because it loses under the stress costs and only works with its trend filter on.
- **Priority:** if both fire on the same bar, Icicle goes first.
- **Exits:** both keep their frozen exits. Icicle uses TP1 1R and TP2 2R; Avalanche uses TP1 1.5R and TP2 3R. Both use two orders (split) and a 120-minute limit.

| Period | Trades | Per day | Win % | TP1 hit | TP2 hit | Avg R | PF |
|---|---|---|---|---|---|---|---|
| DISC Jan–Apr 2026 (tuning) | 129 | 1.5 | 52.7 | 45.0% | 20.9% | +0.279 | 1.74 |
| VAL May–Aug 2026 | 142 | 1.6 | 47.9 | 39.4% | 17.6% | +0.096 | 1.21 |
| Y2025 | 405 | 1.6 | 47.4 | 42.2% | 15.3% | +0.103 | 1.23 |
| HOLD 1–23 Sep 2026 | 27 | 1.5 | 37.0 | 22.2% | 3.7% | **−0.166** | 0.66 |
| **All OOT** | **574** | 1.3 | 47.0 | 40.6% | 15.3% | **+0.089 ± 0.047** (t 1.90) | 1.20 |

**Checks:**
- **Stress on OOT:** spread $0.45 + slippage gives +0.066R; spread $0.60 + slippage gives +0.050R.
- **Random control, VAL:** the median is −0.032R and the 5–95% range is −0.108 to +0.143. Frostbite scored +0.096R.
- **By month:** 17 of 21 months are positive. The worst are 2025-03 (−0.15R), 2026-05 (−0.09R) and 2026-09 so far (−0.17R).
- **Worst streaks:** the largest drawdown is 11.6R, and the longest losing streak is 6 trades.
- **Breakeven after TP1** instead of two untouched orders gives +0.082R versus +0.089R on OOT. The default stays "leave both orders alone".

## How strong is this evidence?
- **Out of sample, but chosen:** the two setups were picked from about 46 families because their out-of-sample results were the best. That makes the combined figures look better than a fresh test would.
- **Small edge:** +0.09R per trade, with a t of 1.9 before allowing for that selection. That is small and not proven.
- **Recent weakness:** the newest data, September 2026, is negative.
- **Gold only:** only gold was tested. The rules run on any symbol, but other pairs are untested. The EURUSD download was throttled by the data source and did not finish in time.

## Verification
| Check | Result |
|---|---|
| Engine fill rules (hand-built price paths) | all tests pass (`research/test_engine.py`) |
| Pine logic mirrored bar by bar in Python vs research signals | **1,026 / 1,026 signals identical** (direction, setup; SL within $0.007) |
| Chart scorecard logic (M5 bars) vs research engine (M1) | same trades; VAL +0.098 vs +0.096R, 2025 +0.118 vs +0.103R |
| Pine syntax | offline parser OK |
| Independent code review | no compile errors; 6 issues fixed (see README) |

Reproduce: `research/meeting.py` (this page) and `research/mirror.py` (parity). The team code and results are in `research/team{A,B,C,D}/`, and the scout's sources are in `research/SCOUT_REPORT.md`.

## Follow-up (v2): XAUUSD M5 only, more signals, math-based filters

**Math-based families** (`research/quant.py`, tuned on Jan–Apr 2026 only; target 2+ signals a day):

| Family | Signals / day | May–Aug 2026 | 2025 | Stress (May–Aug 2026) |
|---|---|---|---|---|
| Kalman trend + residual z-score pullback | 2.4 | +0.004R | **−0.102R** | −0.012R |
| Kalman slope flip | 4.8 | +0.009R | **−0.056R** | −0.005R |
| Ehlers SuperSmoother + Fisher transform | 3.7 | −0.011R | −0.035R | −0.033R |
| Regression-slope t-statistic pullback | 4.6 | −0.155R | −0.088R | −0.187R |

None holds up. In v2 the Kalman filter draws the smooth trend line only.

**More signals from the two setups that held up** (periods not used for tuning):

| Version | Signals / day | Avg per trade | Stress |
|---|---|---|---|
| Icicle + Avalanche, first break per side per day (Fewer, stronger) | 1.6 | +0.089R | +0.066R |
| Icicle + Avalanche, every break (**More**, v2 default) | 2.3 | +0.052R | +0.029R |
| + Icicle on M15 and Avalanche on M5 | 3.0 | +0.024R | −0.009R |

v2 offers the first two as modes. Parity: 1,550 / 1,550 signals identical in More mode.

## Follow-up (v2.1): account specs, one order, physics check

- **One order vs two** (periods not used for tuning):
  - Order B (TP2) alone: **+0.059R** in More mode and **+0.108R** in Fewer mode.
  - Order A (TP1) alone: +0.045R and +0.069R.
  - The tuning period ranks them the same way (B +0.263R / +0.343R vs A +0.177R / +0.215R).
  - A single order halves the $ risk, so *Orders per signal = Auto* uses 1 order → TP2 on small balances.
- **Physics filter:** keep only the signals that point the same way as the Kalman velocity (the smooth line's direction).
  - 92% (More) and 98% (Fewer) of signals already do.
  - Filtering didn't help: +0.045R vs +0.052R (More) and +0.082R vs +0.089R (Fewer).
  - Not adopted.
- **Account specs** (JustMarkets Standard): 0.01 minimum lot, 1:3000, stop-out 20%, no commission. See `ACCOUNT.md`.
