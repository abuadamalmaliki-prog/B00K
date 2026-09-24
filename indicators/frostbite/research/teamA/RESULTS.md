# Team A: trend and momentum scalps (XAUUSD, M1–M15)

Code: `teamA/teamA.py`. Run it from `research/` to print every number below. The full log is in `teamA/teamA_output.txt`. Data covers 2025-01-01 to 2026-09-23, and both the 2025 and 2026 files are complete. Trading days: DISC 85, VAL 88, Y2025 258, HOLD 18.

How each family was searched (the same for every family, DISC only):
1. Signal grid at TP1 1.0R, TP2 2.0R, split, hold 120.
2. Refinements of the winner, such as the stop multiple.
3. Six (TP1, TP2) pairs × BE on/off.
4. Hold 60 or 240.

The frozen variant is the highest DISC avgR with at least 0.5 trades per day, taken over all combinations tried. Stops are k × ATR(14) of the chart timeframe unless the params say otherwise (k defaults to 1.5). "H1 filter" means the last completed H1 close compared with the H1 EMA50, taken via `htf_on_ltf`.

## Results

| family | best params | combos | DISC avgR/n | VAL n/per_day/win%/TP1%/TP2%/avgR±se/PF | Y2025 avgR | HOLD avgR | random median [5-95%] | stress avgR | result |
|---|---|---|---|---|---|---|---|---|---|
| F1 EMA pullback (20/50 stack) | tf=15, line=50, htf=0, k=2.0; TP1 1.5R TP2 3.0R split hold 120 | 32 | 0.0356/266 | 248/2.82/46.8/14.9/2.0/0.034±0.056/1.1 | -0.0078 (n=809) | -0.0095 (n=49) | -0.0136 [-0.107,0.049] | 0.0212 | FAIL |
| F2 EMA cross + HTF filter | tf=3, fast_slow=(9, 21), htf=15, k=2.0; TP1 1.0R TP2 3.0R BE hold 120 | 27 | 0.0084/642 | 689/7.83/46.4/44.1/12.5/-0.0759±0.0419/0.86 | -0.0306 (n=1948) | -0.0302 (n=135) | -0.0522 [-0.099,0.007] | -0.0988 | FAIL |
| F3 Session VWAP trend | tf=15, trig=pb, htf=0, k=2.0; TP1 1.5R TP2 3.0R split hold 240 | 28 | 0.0422/257 | 247/2.81/45.7/26.3/7.3/0.0057±0.0713/1.01 | 0.0279 (n=758) | -0.0727 (n=49) | -0.0584 [-0.109,0.045] | -0.0087 | FAIL |
| F4 Supertrend flip | tf=15, mult=3, htf=1, stop=st; TP1 1.0R TP2 2.0R split hold 240 | 37 | 0.11/81 | 75/0.85/48.0/21.3/5.3/-0.0027±0.0906/0.99 | 0.0429 (n=247) | -0.3059 (n=17) | -0.0417 [-0.166,0.112] | -0.0096 | FAIL |
| F5 MACD/RSI thrust with H1 trend | tf=5, trig=rsi60; TP1 1.5R TP2 3.0R BE hold 120 | 28 | 0.0266/593 | 649/7.38/39.3/34.8/13.4/-0.0591±0.0486/0.9 | -0.0606 (n=1962) | -0.0279 (n=133) | -0.0748 [-0.143,0.018] | -0.0821 | FAIL |
| F6 Momentum burst bar | tf=5, mult=2.5, htf=1; TP1 1.0R TP2 2.0R BE hold 120 | 33 | 0.1613/145 | 139/1.58/50.4/48.9/25.9/-0.0116±0.0905/0.98 | 0.038 (n=369) | -0.5357 (n=24) | -0.0303 [-0.157,0.096] | -0.0384 | FAIL |
| F7 Session continuation (London/NY) | win=ny, bias=both, trig=brk; TP1 0.75R TP2 1.5R split hold 120 | 35 | 0.16/105 | 139/1.58/45.3/57.6/37.4/0.0071±0.0822/1.02 | -0.0388 (n=373) | -0.3215 (n=26) | 0.0291 [-0.156,0.159] | -0.0321 | FAIL |
| F8 Top-down 1m EMA9/21 cross (junutala) | tf=3, sess=0, bias_tf=10, k=2.0; TP1 1.5R TP2 3.0R BE hold 120 | 24 | 0.0403/514 | 579/6.58/41.3/35.1/12.8/-0.0363±0.0509/0.94 | -0.0456 (n=1626) | -0.0128 (n=111) | -0.0539 [-0.165,0.051] | -0.0572 | FAIL |
| F9 EMA 9/21/200 pullback + ADX (andamagodwin) | tf=5, adx_min=25, sess=1; TP1 1.0R TP2 2.0R split hold 240 | 27 | 0.0744/134 | 129/1.47/42.6/56.6/35.7/0.1198±0.099/1.27 | -0.0478 (n=398) | 0.0794 (n=22) | -0.0218 [-0.126,0.071] | 0.1042 | FAIL |
| F10 FA Gold Scalper v6 EMA34/50/200 (ruthphillipsi) | tf=5, sess=13-17, adx_min=20; TP1 1.0R TP2 2.0R split hold 120 | 26 | 0.1871/63 | 72/0.82/50.0/47.2/25.0/0.1192±0.1278/1.27 | 0.0692 (n=200) | -0.2661 (n=12) | -0.0599 [-0.133,0.065] | 0.094 | FAIL |

Total combinations tried: 297 across 10 families, between 24 and 37 per family.

The random control, stress test and every check ran on VAL. `best_signals()` returns F9, the highest VAL avgR, because nothing passed. F9 and F10 are effectively tied (0.1198 vs 0.1192).

## Findings

- **Nothing passes.** On M1–M15 gold, plain trend-following and momentum entries are no better than random entries after costs. Examples are EMA pullbacks, EMA crosses, VWAP pullbacks and reclaims, Supertrend flips, MACD/RSI thrusts, burst bars and session continuation. Their VAL avgR is between -0.08 and +0.03, which is inside the random-control 5–95% band. The random medians are themselves negative, from -0.02 to -0.07R: that is the cost of the spread plus the rule that the stop wins when a bar touches both.
- **The DISC winners of the looser families fell back to zero out of sample.** F6 went from +0.16 to -0.01 and F7 from +0.16 to +0.01. Both then lost about 0.3–0.5R per trade in HOLD. Their DISC edge was selection noise.
- **Only the two strict "EMA stack + ADX + RSI + pullback + session" scalps from the scout's sources finished above the random 95th percentile on VAL** (F9 and F10). Each misses PASS on one check:
  - F9 (M5, 07–17 UTC) has avgR/se of 1.21, beats random by 0.14R and survives the stress test, but loses in 2025 (-0.048, n=398).
  - F10 (M5, 13–17 UTC) is positive in DISC, VAL and 2025, and is positive under stress. Its avgR/se is only 0.93, it averages 0.8 trades per day, and HOLD is -0.27 (n=12).
- **Recommendation: F10 is the only candidate worth a second look; F9 should not be used.** F10 is positive in every long period. F9's VAL result is contradicted by a full negative year. Neither is proven, so ship neither without more evidence.
- **Faster timeframes lose more.** M1 variants were the worst in DISC, at -0.09 to -0.16R per trade. Wider stops (2 ATR) and M15 did best among the plain trend rules, which shows that spread and noise dominate small stops. The London window (03–06 NY) continuation of the Asia drift was strongly negative in DISC (-0.20 to -0.23R); that fits a reversal effect, not continuation.

## Sources credited (from the scout report)

- F8: junutala/XAUStrategy, `XAU_Scalping_Strategy.pine` (scout #3). Replicated rules:
  - 1m EMA9×21 cross;
  - 10m or 15m bias: EMA20/50 plus VWAP;
  - M5 RSI below 70 or above 30;
  - chart RSI band;
  - chart VWAP side;
  - session 07–16 London.
- F9: andamagodwin/forex, `xau_scalper/strategy.py` (scout #1). Replicated rules:
  - EMA 9/21/200;
  - touch of EMA21 within the last 5 bars;
  - RSI 45–70 and rising;
  - ADX at least 25;
  - bar range at most 3 ATR;
  - 07–17 UTC with a Friday cutoff at 15 UTC;
  - stop max(1.5 ATR, $1.50).

  The source's spread filter and cooldown after a loss were not replicated: they cannot be done on a TradingView chart.
- F10: ruthphillipsi/XAUUSD-EA-20PROJECT, `FA_Gold_Scalper_v6.pine` (scout #2). Replicated rules:
  - EMA 34/50/200 stack;
  - touch of EMA34 within the last 3 bars;
  - bullish close above the previous high;
  - ADX above 20;
  - RSI 45–70;
  - 13–17 UTC;
  - 5-bar swing stop ± 0.2 ATR, clamped to 0.6–3 ATR.

  The source's profit lock is approximated by the engine's BE mode (tested in stage 3).

## Notes for the lead

- **frost.py:** I found no bug.
- **Lookahead check:** I re-ran every family's signals with the data cut at two points (2026-03-11 and 2026-06-17). Signals on closed bars were identical, including the HTF filters.
- **Stress-test trade counts:** the stress row can differ from VAL by one trade. The stress run simulates VAL signals only, so no position carries over from April.
- **F10 random control:** the random entries have random direction, so they use the mean of the long and short swing-stop distances.
- **Shared scratchpad:** a stray `scratchpad/bisect.py`, written by another agent, shadows Python's stdlib `bisect`. Any script run from the scratchpad root breaks on `import numpy`. I ran my scripts from a subfolder instead.
