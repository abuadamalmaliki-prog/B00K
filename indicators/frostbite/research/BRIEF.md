# Frostbite research brief (read fully before starting)

**Goal:** find the XAUUSD **scalping** technique that holds up best after costs, for a TradingView indicator that shows **BUY / SELL** with **SL, TP1 and TP2**. The trader places orders by hand in MT5 (JustMarkets Standard, no commission).

## Tools
- Python: `/tmp/claude-0/-home-user-B00K/01e03a29-5c0a-5983-a2cb-27e1534e4369/scratchpad/frost/venv/bin/python` (numpy, pandas, numba). Run from `/home/user/B00K/indicators/frostbite/research` and `import frost`.
- `frost.py` is the shared engine. **Do not edit it.** If you believe it has a bug, write it in your RESULTS.md and tell the lead in your final report.
- Key calls:
  - `b = frost.bars(tf_minutes)` gives bid bars (1, 3, 5, 15, 60 …) with columns o,h,l,c,v,time,ny_h,ny_m,ny_min,tday,utc_h,dow,end.
  - Indicators: `frost.ema, sma, rma, rsi, atr, stdev, vwap_session, htf_on_ltf` (a higher-TF value as known at each lower-TF bar close, with no lookahead).
  - `sig = frost.levels(b, idx, d, stop_dist, t1_r, t2_r)`: idx are bar indices of **closed** signal bars, d is ±1, stop_dist is in price units.
  - `t = frost.simulate(sig, spread=0.30, be=False|True, max_hold=minutes, slip=0.0)`: one position at a time, entry at the next 1-minute open.
  - `frost.by_period(t)`, `frost.stats(t)`, `frost.monthly(t)`, `frost.random_control(idx, b, stop_fn, t1_r, t2_r, n_runs=20)`.
- Data is still downloading (2026 first, then 2025). `frost.coverage()` shows what's loaded. Build and debug on what's there. Run **final numbers only once coverage reaches 2026-09-23** for 2026 (the file `data/XAUUSD_2026_m1.csv.gz` appears when 2026 is complete). Report 2025 if it has finished by then (`data/XAUUSD_2025_m1.csv.gz`), otherwise say it wasn't available.

## Cost model (already in the engine)
Ask = bid + $0.30 + news/rollover widening from the real feed. Longs fill at the ask and exit on the bid; shorts fill at the bid and exit on the ask. If a 1-minute bar touches both the stop and a target, **the stop wins**. Forced flat at 16:50 New York, with no entries until 18:00. Stress test: `spread=0.45, slip=0.05`.

## Order structure (fixed)
Every signal has one **SL**, **TP1** and **TP2**. Two modes:
- `be=False`, "split": two equal positions with the same SL, one targeting TP1 and one TP2.
- `be=True`: as split, but after TP1 the second position's SL moves to entry.

Test both. Allowed grid: TP1 ∈ {0.5, 0.75, 1.0, 1.5} R, TP2 ∈ {1.5, 2.0, 3.0} R (TP2 > TP1), `max_hold` ∈ {60, 120, 240} minutes.

## Protocol (identical for every team)
1. **Tune only on DISC = Jan–Apr 2026.** Keep the search small: **at most ~40 parameter combinations per family**, and report how many you tried.
2. Freeze the best DISC variant (highest avgR with at least 0.5 trades per trading day). Then report it **unchanged** on:
   - **VAL** = May–Aug 2026
   - **Y2025** = 2025
   - **HOLD** = 1–23 Sep 2026
3. Random control on VAL: `random_control` with the same stop rule and targets, 20 runs. Report the median and the 5–95% range.
4. Stress test on VAL: spread 0.45, slip 0.05.
5. **PASS** requires all of these:
   - VAL avgR > 0 with avgR/se ≥ 1.0
   - Y2025 avgR > 0 (if available)
   - VAL avgR above the random-control median by ≥ 0.05R
   - stress-test VAL avgR ≥ 0
   - at least 0.5 trades per trading day

## Rules must work in Pine v6 on one TradingView chart
- Use bar OHLC plus standard indicators on the chart timeframe (M1–M15). Higher-timeframe filters via request.security are allowed (M15, H1, H4, D).
- Avoid rules that depend on volume levels: TradingView's gold volume is tick count and won't match this feed. Session VWAP is acceptable.
- Session times use the New York clock (`ny_h`, `ny_min`).

## Deliverables (in your team folder `research/team<X>/`)
- `team<X>.py`: reproducible code that prints every number in your table.
- `RESULTS.md`: one table covering all families you tested. Columns: family, best params, combos tried, DISC avgR/n, VAL n/per_day/win%/TP1%/TP2%/avgR±se/PF, Y2025 avgR, HOLD avgR, random median, stress avgR, PASS/FAIL. Then 3–6 lines of findings (what worked, what didn't, why).
- In `team<X>.py`, a function `best_signals()` returning the `sig` DataFrame for your single best technique (the one with the highest VAL avgR among those that passed; if none passed, the highest VAL avgR), so the lead can re-run it.
- Final report to the lead (under 300 words): the table rows for your best 3 techniques and your recommendation.

## Honesty rules
Never tune on VAL, Y2025 or HOLD. Never drop losing months. If nothing passes, say so. That is a valid and useful result. Report the numbers exactly as the code prints them.

## Scout references
A scout agent is collecting technique references from GitHub. Its report will be at `/tmp/claude-0/-home-user-B00K/01e03a29-5c0a-5983-a2cb-27e1534e4369/scratchpad/frost/scout/REPORT.md`. When it exists, read it and include any technique that belongs to your family (credit the source).
