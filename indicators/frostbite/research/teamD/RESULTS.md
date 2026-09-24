# Team D: price action and smart-money concepts (M1–M15)

Code: `teamD/teamD.py`. Run it from `research/` with `python teamD/teamD.py`. It prints every DISC combination and every number below in about 40 s. `best_signals()` returns the signal frame for the chosen technique, and `best_exit()` returns its TP1, TP2, be and max_hold.
Data: 2025-01-01 to 2026-09-23, run in a fresh process after both yearly files were complete.

**Result: no family passes.** 13 families were tested with 373 DISC combinations in total, and every family stayed under 40.

| family | best params (frozen on DISC) | combos | DISC avgR/n | VAL n | per_day | win% | TP1% | TP2% | avgR±se | PF | Y2025 avgR | HOLD avgR | random median [5-95%] | stress avgR | PASS/FAIL |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SESS_SWEEP | tf=3,conf=0,htf=1; TP1.0/2.0 split mh240 | 27 | +0.119/49 | 54 | 0.61 | 37.0 | 50.0 | 27.8 | -0.121±0.148 | 0.77 | -0.226 (n=157) | +0.023 (n=9) | -0.128 [-0.382, +0.044] | -0.182 | FAIL |
| SWING_SWEEP | tf=5,k=10,conf=1,htf=0; TP1.5/3.0 be mh120 | 35 | +0.200/146 | 153 | 1.74 | 44.4 | 31.4 | 9.2 | +0.007±0.096 | 1.01 | -0.068 (n=450) | +0.173 (n=26) | -0.052 [-0.165, +0.103] | -0.012 | FAIL |
| CHOCH | tf=1,k=5,need_trend=0,htf=1; TP1.0/2.0 be mh60 | 35 | +0.013/367 | 392 | 4.45 | 43.4 | 43.4 | 22.2 | -0.160±0.053 | 0.73 | -0.150 (n=1167) | -0.095 (n=69) | -0.099 [-0.151, -0.003] | -0.214 | FAIL |
| FVG | tf=5,gmin=0.25,stop=0,htf=1; TP1.0/2.0 be mh120 | 35 | +0.074/371 | 356 | 4.05 | 52.0 | 49.4 | 24.7 | +0.021±0.056 | 1.04 | -0.092 (n=1052) | -0.082 (n=88) | -0.062 [-0.199, -0.004] | -0.029 | FAIL |
| OB | tf=5,k=5,body=0,htf=1; TP1.0/2.0 split mh240 | 35 | +0.067/153 | 155 | 1.76 | 33.5 | 44.5 | 25.8 | -0.117±0.086 | 0.78 | -0.056 (n=528) | -0.192 (n=27) | -0.053 [-0.110, +0.072] | -0.160 | FAIL |
| BOS_PB | tf=5,k=5,fib=0.5,stop=1; TP1.0/2.0 split mh240 | 35 | +0.059/234 | 232 | 2.64 | 39.7 | 45.7 | 25.4 | -0.044±0.069 | 0.91 | -0.039 (n=740) | -0.137 (n=45) | -0.069 [-0.191, +0.055] | -0.059 | FAIL |
| PA_LEVEL | tf=15,lv=r10,pat=1; TP1.0/2.0 split mh120 | 29 | +0.101/459 | 394 | 4.48 | 36.5 | 41.9 | 18.3 | -0.140±0.051 | 0.74 | -0.147 (n=818) | +0.117 (n=82) | -0.048 [-0.144, +0.008] | -0.172 | FAIL |
| EQ_SWEEP | tf=1,k=3,tol=0.1,conf=1; TP1.5/3.0 be mh60 | 35 | +0.098/130 | 152 | 1.73 | 42.1 | 42.1 | 16.4 | -0.025±0.104 | 0.96 | -0.101 (n=418) | -0.200 (n=33) | -0.098 [-0.222, +0.126] | -0.091 | FAIL |
| SILVER_BULLET | tf=5,gmin=0.25,htf=1; TP1.5/3.0 be mh60 | 23 | +0.160/57 | 60 | 0.68 | 48.3 | 40.0 | 15.0 | +0.150±0.169 | 1.29 | +0.036 (n=160) | -0.204 (n=15) | -0.101 [-0.296, +0.198] | +0.110 | FAIL |
| S15_ICT_SWEEP | tf=5,htf=0; TP1.5/3.0 split mh120 | 19 | +0.408/51 | 62 | 0.7 | 33.9 | 30.6 | 14.5 | -0.264±0.153 | 0.61 | -0.298 (n=176) | -0.508 (n=15) | -0.099 [-0.226, +0.195] | -0.290 | FAIL |
| S16_PD_BREAK | tf=1,htf=0; TP1.0/2.0 be mh60 | 20 | -0.048/411 | 425 | 4.83 | 48.2 | 47.8 | 24.2 | -0.053±0.052 | 0.9 | -0.188 (n=1381) | +0.046 (n=79) | -0.117 [-0.180, -0.086] | -0.092 | FAIL |
| S17_SB_SWEEP_FVG | tf=1,htf=0; TP1.5/2.0 split mh120 | 18 | +0.218/63 | 54 | 0.61 | 33.3 | 33.3 | 27.8 | -0.204±0.168 | 0.71 | -0.165 (n=156) | -0.425 (n=12) | -0.068 [-0.321, +0.071] | -0.242 | FAIL |
| S18_SWEEP_FVG | tf=5,k=10,htf=0; TP1.5/3.0 split mh240 | 27 | +0.518/44 | 67 | 0.76 | 32.8 | 29.9 | 9.0 | -0.321±0.136 | 0.52 | -0.157 (n=185) | +0.694 (n=8) | -0.069 [-0.172, +0.167] | -0.389 | FAIL |

**Best technique (`best_signals()`): SILVER_BULLET.** It is the highest VAL avgR, chosen because nothing passed.
- **Rule:** on M5, a fair value gap forms inside 03–04, 10–11 or 14–15 New York time, and a bar in the same window trades into the gap and closes back on the gap's side.
  - The gap must be at least 0.25 ATR, with a bullish middle candle for longs.
  - Trades must agree with the H1 EMA50 trend.
- **Stop:** beyond the gap's far edge plus 0.1 ATR, kept between 0.5 and 2.0 ATR.
- **Exits:** TP1 1.5R, TP2 3R, stop moves to breakeven after TP1, 60-minute max hold.
- **Why it fails:** it passes every PASS test except the significance test (VAL avgR/se = 0.89, below the 1.0 needed).
- **HOLD:** −0.20 on n=15.

## Findings
- **Nothing passes.** The closest is SILVER_BULLET, with the numbers in the table. It fails only because avgR/se is below 1.0. Only 60 VAL trades, a 95% interval of roughly ±0.33R and a negative HOLD make it a forward-test candidate, not an edge.
- **DISC flattered the sweep reversals.** Jan–Apr 2026 gave the high DISC scores: S18 +0.52, S15 +0.41, S17 +0.22 and SWING_SWEEP +0.20. All of them collapsed on VAL (−0.32, −0.26, −0.20, +0.01), and all were negative in 2025.
  - Their DISC samples were small (44–63 trades for the session sweeps), so picking the best DISC variant mostly picked noise.
  - The sources' own tests for #17 and #18 were also negative.
- **Reversal-type setups lose after costs.** On VAL, CHoCH (−0.16), order-block retests (−0.12) and pin bars at $10 levels (−0.14) were all below their random-control medians. Equal-high/low sweeps came in at −0.03.
- **Continuation setups with the H1 EMA50 filter come close to zero, not above it.** These are the FVG retest (+0.02 VAL, −0.09 in 2025) and the BOS pullback (−0.04 and −0.04). On DISC, the same M5 FVG trigger without the filter scored −0.06, so the trend filter does most of the work.
- **M1 is too expensive.** On M1 the $0.30 spread is about 0.1R. On DISC, 32 of 112 M1 combinations were positive, against 91 of 149 on M5.

## Methods, adaptations and credits
- **Family definitions** (see the docstrings in `teamD.py`). Longs and shorts are mirror images.
  - **SESS_SWEEP:** sweeps of the Asian range (18:00–03:00 NY), the London range (03:00–08:00 NY) or PDH/PDL.
  - **SWING_SWEEP:** sweeps of the last confirmed k-bar swing high or low.
    - `conf=1` also requires a close beyond the reclaim bar's extreme (a light market-structure-shift check).
  - **CHOCH:** after a swing-low sweep, a close above the last swing high within 20 bars.
  - **FVG:** a retest of the latest gap.
  - **OB:** a retest of the last opposite candle before a BOS leg.
  - **BOS_PB:** a BOS, then a 50% or 61.8% pullback with a bullish close. The H1 filter is always on.
  - **PA_LEVEL:** an engulfing or pin bar that touches session VWAP, a $10 round number or PDH/PDL.
  - **EQ_SWEEP:** a sweep of equal highs or lows, meaning two swing points within a tolerance of ATR.
- **No lookahead:**
  - Pivots count only k bars after the pivot and are used from the next bar on.
  - Session ranges are locked only after the session ends.
  - HTF values use `frost.htf_on_ltf`.
  - Every signal is on a closed bar.
- **Stops and search:**
  - Stops are structural plus 0.1 ATR, kept between 0.5 and 2.0 ATR of the signal timeframe.
  - The search has two stages. Stage A tunes the signal parameters at fixed exits. Stage B tests 10 target/mode pairs at 120 minutes, then the other max_hold values on the best pair.
  - The selection rule is the highest DISC avgR with at least 0.5 trades per day.
- **Random control:** random bars in the same NY hours with random direction and the same targets and mode. Stops are the family's own stop sizes in ATR units, re-sampled onto the random bars, because `stop_fn` cannot see the trade direction that a structural stop depends on.
- **Scout references, tested under this protocol with each source's own targets as the stage-A exits.** Where a source enters on a limit or stop order, it is adapted to "signal on the close of the bar that retests or breaks the level" so it works as a closed-bar indicator.
  - **#15 → S15_ICT_SWEEP.** PineGen-AI, github.com/PineGen-AI/ICT-Daily-Liquidity-Sweep-PineGen-AI- (README only).
    - Asian box 00–08 UTC, used as 19:00–03:00 NY, plus PDH/PDL.
    - A wick through the level with a close back inside on the same bar, traded 03:00–12:00 NY. TP 1.5R and 3R.
  - **#16 → S16_PD_BREAK.** AhadRasheed, github.com/AhadRasheed/gold-strategy (`strategy.py`).
    - PDH/PDL taken, then a reversal candle beyond the level, then a close beyond that candle's high or low.
    - The source's short side needs a green candle and then a red one. This version uses the mirror image of the long side.
  - **#17 → S17_SB_SWEEP_FVG.** cjosh4toyotas-stack, github.com/cjosh4toyotas-stack/silver-bullet-backtest (`bot/sb_paper_bot.py`).
    - The first bar that sweeps the 2-hour extreme, scanning from 30 minutes before each Silver Bullet window, sets the bias.
    - The first FVG in that direction must form inside the window, and the retest must come before the window closes. One trade per window.
  - **#18 → S18_SWEEP_FVG.** ManasDoitto, github.com/ManasDoitto/trading-pine-strategies (SMC liquidity sweep + FVG v1.0).
    - A sweep of the k-bar swing or PDH/PDL, then within 5 bars an FVG with a displacement candle of at least 1 ATR, then a retest within 10 bars.
    - Their chandelier and liquidity targets are replaced by the brief's R grid.
  - **SILVER_BULLET and the FVG minimum size in ATR:** from BAKOME-Hub, github.com/BAKOME-Hub/BAKOMEGoldScalper. The Silver Bullet hours are ICT's.
- **Engine (`frost.py`):** read in full, and I found no bug. One small note: `max_hold` counts 1-minute rows, not clock minutes, because closed-market minutes are dropped. It makes no practical difference for intraday holds.
