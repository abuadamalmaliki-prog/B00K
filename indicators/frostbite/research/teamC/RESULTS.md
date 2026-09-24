# Team C: breakouts and session timing (XAUUSD, M1–M15)

Run: `<venv python> teamC/teamC.py` from `research/` (about 35 s). The full log is in `teamC/teamC_output.txt`.
Data: 2025-01-01 to 2026-09-23, both years complete (539 days loaded). DISC has 85 trading days.
Every number below is copied from the log, which came from one final run on the complete data.

Protocol (the same for every family): stage 1 tests signal variants on DISC with a fixed order (default stop, TP1 1R, TP2 2R, hold 120, split). Stage 2 then tunes the order on the best stage-1 variant, one step at a time: TP1 {0.5,1,1.5} × TP2 {2,3} × be {F,T} (12 combos), then max_hold {60,240} (2), then the stop multiplier ×{0.67,1.33} (2).
"Best" means the highest DISC avgR among variants with at least 0.5 trades per day. Signals are cut to DISC before they are simulated. The frozen variant is then reported unchanged on VAL, Y2025 and HOLD, with a VAL random control (20 runs) and a VAL stress test (spread 0.45, slip 0.05).
The default stop is 1.5 × ATR14 of the chart TF. The range families can instead use `rng` (0.5 × box width) or `opp` (1 × box width, i.e. the opposite side), both bounded by ATR.

## Results (all 12 families; none passes)

| family | best params | combos | DISC avgR / n | VAL n | VAL /day | VAL win% | VAL TP1% | VAL TP2% | VAL avgR ± se | VAL PF | Y2025 avgR | HOLD avgR | rand median [5–95%] | stress avgR | PASS/FAIL |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ASIA Asian-range breakout (London) | tf=15,end=690,stop=rng,wmax=None,per_dir=True; TP1=1.5 TP2=3.0 hold=240 be=False stopx=1.0 | 35 | +0.1581 / 66 | 85 | 0.97 | 43.5 | 16.5 | 3.5 | +0.0307 ± 0.1045 | 1.08 | -0.0170 | +0.2476 | -0.0030 [-0.2141, +0.1312] | +0.0216 | FAIL: val>0 & t>=1, y2025>0, val-rand>=0.05 |
| ORB Opening-range breakout 03:00/08:20/09:30 | tf=5,sess=CMX,L=30,stop=opp,ocd=True; TP1=1.0 TP2=3.0 hold=120 be=True stopx=1.0 | 37 | +0.1168 / 58 | 68 | 0.77 | 52.9 | 52.9 | 10.3 | -0.0205 ± 0.1256 | 0.96 | -0.0775 | +0.3690 | -0.0251 [-0.0751, +0.1785] | -0.0882 | FAIL: val>0 & t>=1, y2025>0, val-rand>=0.05, stress>=0 |
| SESS2 Two-session boxes + H1 EMA50/200 (scout #6) | tf=15,sess=AB,atrf=False; TP1=1.5 TP2=3.0 hold=120 be=True stopx=1.0 | 29 | +0.0957 / 46 | 46 | 0.52 | 39.1 | 19.6 | 6.5 | -0.0854 ± 0.1562 | 0.83 | +0.1060 | +0.4668 | -0.0278 [-0.2849, +0.2867] | -0.0970 | FAIL: val>0 & t>=1, val-rand>=0.05, stress>=0 |
| DT Dual Thrust (scout #8) | tf=15,anchor=D,k=0.2; TP1=0.5 TP2=3.0 hold=120 be=True stopx=1.0 | 28 | +0.0448 / 70 | 80 | 0.91 | 52.5 | 52.5 | 2.5 | -0.1911 ± 0.0857 | 0.56 | -0.0346 | +0.0990 | -0.0162 [-0.1905, +0.1159] | -0.2000 | FAIL: val>0 & t>=1, y2025>0, val-rand>=0.05, stress>=0 |
| PDHL Prior-day high/low close-beyond | tf=15,sess=all,htf=True,first=True; TP1=1.5 TP2=3.0 hold=120 be=False stopx=1.0 | 32 | +0.3625 / 68 | 75 | 0.85 | 48.0 | 30.7 | 10.7 | +0.1046 ± 0.1341 | 1.23 | +0.1204 | -0.0865 | +0.0053 [-0.1000, +0.1724] | +0.0918 | FAIL: val>0 & t>=1 |
| SQZ BB-inside-KC squeeze release | tf=15,dir=mom,sess=act,kcm=1.5; TP1=1.5 TP2=3.0 hold=120 be=True stopx=1.0 | 37 | +0.0688 / 46 | 46 | 0.52 | 32.6 | 19.6 | 8.7 | -0.1858 ± 0.1579 | 0.67 | -0.0504 | +0.0513 | +0.0156 [-0.2291, +0.2730] | -0.1988 | FAIL: val>0 & t>=1, y2025>0, val-rand>=0.05, stress>=0 |
| NR Inside-bar / NR4 / NR7 breakout | tf=5,pat=NR7,htf=True,sess=all; TP1=1.5 TP2=3.0 hold=240 be=True stopx=1.0 | 40 | +0.0825 / 732 | 804 | 9.14 | 37.1 | 34.7 | 15.4 | -0.0995 ± 0.0445 | 0.84 | -0.0550 | +0.0546 | -0.0515 [-0.0859, +0.0011] | -0.1274 | FAIL: val>0 & t>=1, y2025>0, val-rand>=0.05, stress>=0 |
| DRIFT Time-of-day drift (DISC-fitted hours) | k=4,score=t; TP1=1.5 TP2=2.0 hold=120 be=False stopx=0.67 | 26 | +0.1568 / 278 | 286 | 3.25 | 40.6 | 33.6 | 21.7 | -0.0735 ± 0.0690 | 0.87 | -0.0812 | +0.0662 | -0.0502 [-0.1517, +0.0440] | -0.0860 | FAIL: val>0 & t>=1, y2025>0, val-rand>=0.05, stress>=0 |
| NEWS 08:30/10:00 data-release momentum | times=A,tf=5,x=0.0,stop=bar; TP1=0.5 TP2=2.0 hold=120 be=True stopx=1.0 | 40 | +0.1560 / 84 | 86 | 0.98 | 66.3 | 66.3 | 16.3 | -0.0252 ± 0.0862 | 0.93 | +0.0020 | -0.1882 | -0.0182 [-0.1987, +0.0706] | -0.0655 | FAIL: val>0 & t>=1, val-rand>=0.05, stress>=0 |
| DON Donchian breakout + H1 EMA filter | tf=15,N=55,htf=50,sess=all; TP1=1.0 TP2=2.0 hold=240 be=True stopx=1.0 | 40 | +0.0836 / 169 | 197 | 2.24 | 51.3 | 48.7 | 20.3 | +0.0359 ± 0.0728 | 1.08 | +0.0196 | +0.2967 | -0.0165 [-0.0921, +0.1237] | +0.0269 | FAIL: val>0 & t>=1 |
| DCADX Donchian-30 + ADX/DI/EMA50 (scout #11) | tf=5,adx=30,cross=False; TP1=0.5 TP2=3.0 hold=240 be=True stopx=1.0 | 24 | +0.0020 / 335 | 351 | 3.99 | 64.4 | 64.4 | 9.7 | -0.0423 ± 0.0451 | 0.88 | -0.1123 | -0.2318 | -0.0648 [-0.0979, -0.0147] | -0.0619 | FAIL: val>0 & t>=1, y2025>0, val-rand>=0.05, stress>=0 |
| STRAD 08:30 ATR news straddle (scout #19) | tf=1,k=1.0,atf=15; TP1=0.5 TP2=2.0 hold=120 be=False stopx=1.0 | 24 | +0.0664 / 81 | 89 | 1.01 | 30.3 | 55.1 | 29.2 | -0.1755 ± 0.1039 | 0.67 | -0.0803 | -0.0068 | -0.0533 [-0.2217, +0.0746] | -0.1904 | FAIL: val>0 & t>=1, y2025>0, val-rand>=0.05, stress>=0 |

"combos" counts every DISC evaluation, including the stage-2 row that repeats the default order. `per_dir=True` means first break per side per day. `htf=True` / `htf=50` means the last completed H1 close is on the trade's side of its EMA50. `first=True` means first cross per side per trading day.

## Findings

1. **Nothing passes.** The closest is **PDHL**: an M15 close beyond the prior trading day's high or low, on the side of the H1 EMA50, first break per side per day. It was positive on every unseen check except significance: VAL +0.1046R (t = 0.78, n = 75), Y2025 +0.1204R (t = 1.47, n = 216), stress +0.0918R, and 0.099R above the random median. HOLD was −0.0865R on only 15 trades. Its DISC +0.36R shrank about 70% out of sample.
2. **DON** (M15 Donchian-55 with the H1 EMA50 filter) is the only other family positive on VAL, Y2025 and stress (+0.0359 / +0.0196 / +0.0269R), but t = 0.49, so it is roughly breakeven. In this family, only breakouts of **higher-timeframe levels taken with the H1 trend** keep a small positive sign out of sample.
3. The **session boxes do not beat random**: Asian range, ORB 03:00/08:20/09:30, two-session boxes, Dual Thrust and the squeeze. On DISC each variant had only 46–85 trades, so its avgR had a standard error of 0.10–0.17R, and the DISC winners reverted to about zero or below (VAL −0.1911 to +0.0307R).
4. **The fast M1/M5 rules lose steadily**: NR7/inside bar, Donchian-30+ADX, the 08:30 straddle and 08:30 momentum. Their VAL random controls are also negative (−0.02 to −0.065R), which is roughly what the spread plus news widening costs per trade with ATR stops on these timeframes. The high-frequency ones (NR 9/day, DCADX 4/day) accumulate that loss.
5. **No persistent time-of-day drift.** Every DISC hourly t-stat has |t| < 1.1 (see the log). The four hours fitted on DISC reversed out of sample (VAL −0.0735R, Y2025 −0.0812R).

## Scout techniques included (credit to the source repositories; the details are in `teamC.py`)

| scout # | source | where tested | outcome |
|---|---|---|---|
| 4 Asian box 19:00–02:00 NY, trade 03:00–11:30, skip if box > 2 ATR, stop at the opposite side (0.5–1.5 ATR) | github.com/Mrshahidali420/ORB-Multi-Model-Indicator (`XAU_Pro_Indicator.pine`, setup A) | ASIA stage 1, as published on M5 and M15 | The published gate uses the chart's ATR14, so it almost never opens: 0 DISC trades on M5, 2 on M15. Not selected |
| 5 NY ORB from 09:30 / 08:20, 15 min, OR-candle direction only, no entries after 12:00 (Crabel 1990; Zarattini & Aziz 2023) | same repository (setup B / ORB Pro) | ORB stage 1, as published (US and CMX); the OR-direction rule is also an ORB tweak | As published, DISC −0.127R (US) and −0.292R (CMX). The OR-direction tweak on CMX-30 won DISC and failed out of sample (ORB row) |
| 6 Two-session boxes (00–07 UTC → 07–11; 11:00–13:30 → 13:30–17:00), H1 EMA50/200, box 0.5–3 ATR, prior-day extension ≤ 2 ATR, $0.20 buffer, stop 1.5 ATR | github.com/Andresfcarreno/forja- (`XAUUSD_SessionBreakout.pine`) | SESS2 family, UTC clock as published | Box A with the ATR filter never trades. Best (M15, both boxes, no ATR filter): VAL −0.085R, FAIL |
| 8 Dual Thrust, 5-day range, k = 0.5 (M. Chalek) | github.com/je-suis-tm/quant-trading (`Dual Thrust backtest.py`); our version uses only prior days, while the source reads the same day's range | DT family, anchor at the day open or at 03:00 NY | VAL −0.191R, FAIL |
| 11 M1 Donchian-30 + ADX > 30 + DI spread ≥ 5 + EMA50 | github.com/n30dyn4m1c/gold-pro-scalper (`XAU_Quant_Reversion_Breakout.mq5`) | DCADX family (M1/M5; ATR stop in place of the fixed $10 stop and trailing) | M1 was clearly negative on DISC (−0.14 to −0.17R). M5 won; VAL −0.042R, Y2025 −0.112R, FAIL |
| 14 TTM squeeze (J. Carter) | github.com/Alorse/pinescript-strategies (`TTM Squeeze.pine`) | SQZ stage 1: Carter/Alorse KC 1.0 release, plus Alorse's published entry (momentum turn + RSI 30/70) | DISC −0.179R (M5 release), −0.024R (M5 Alorse rule). Not selected. The SQZ family winner failed (VAL −0.186R) |
| 19 08:30 NY ATR straddle ± 1 ATR(M15), stop 1 ATR, TP 2R, 60 min | github.com/nopponkaeward-max/EA_ATR_news (`EA_ATR_News.mq5`) | STRAD family (a close beyond the level stands in for the stop order) | VAL −0.176R, FAIL |

Also used: github.com/yulz008/GOLD_ORB (H1 ORB EA, reference for the ORB family).

## Notes

- Lookahead: a box level is used only by bars that start after the box closes. Prior-day levels come from the previous 17:00-NY trading day. H1 filters come from `frost.htf_on_ltf`. Every signal is a closed-bar close, and entry is at the next 1-minute open. The drift hours were fitted on DISC 1m data only.
- While the data was still downloading, only DISC tuning tables were run. The scout variants were added before the final run. Nothing out of sample was looked at before the single final run. One smoke test of the evaluation code ran on partial data, and its output was discarded unread.
- NR, NEWS and DON used the full 40-combo budget.
- `frost.py`: no bug found. A small gotcha: in `m1()` the column name `xs` shadows `DataFrame.xs`, so use `d["xs"]` (frost itself already does).
- `best_signals()` returns the PDHL signals (the highest VAL avgR, since nothing passed). Simulate them with `frost.simulate(sig, be=False, max_hold=120)`; this reproduces the PDHL row.
