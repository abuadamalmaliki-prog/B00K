# Team B: mean-reversion scalps (XAUUSD, M1 to M15)

**Result: none of the 11 families passes.** The least bad is ROUND ($5 round-number wick-and-reject on M15), with VAL +0.028R ± 0.049 and Y2025 −0.023R. It fails.

- **Run:** `python teamB/teamB.py` from `research/`. It takes about 40 s and is deterministic (random control seed 7). Every number below is copied from its output.
- **Data:** 2025-01-01 to 2026-09-23, complete. Trading days: DISC 85, VAL 88, Y2025 258, HOLD 18.
- **Combos tried:** 360 in total across 11 families. Each family stayed at or under 40.

## Search (identical for every family, DISC only)
The search runs in stages. Each stage keeps its incumbent, so the frozen variant is the highest DISC avgR among everything tried with at least 0.5 trades per trading day.

- **Stage A:** signal parameters, with a fixed exit: SL 1.5×ATR14 of the chart timeframe, TP1 1R, TP2 2R, split, max_hold 120.
- **Stage B1:** stop 1.0 or 2.0 ATR. ZSCORE also tried its source's own stop, max($8, 2.5 ATR).
- **Stage B2:** (TP1, TP2) ∈ {(0.5,1.5), (0.75,1.5), (1,2), (1.5,3)}, each with be off and on.
- **Stage B3:** max_hold 60 or 240.

Other settings:
- **H1 filter:** "H1" means buy only when the last completed H1 close is above the H1 EMA50, and sell only below it (`frost.htf_on_ltf`).
- **Asia session:** "asia" means 18:00–02:59 New York.
- **Random control:** fed the bar indices of the VAL trades.
- **Lookahead check:** signals computed on data truncated at three cut points matched the full-data signals for every family.

## Results
| family | best params (DISC-frozen) | combos | DISC avgR/n | VAL n | per_day | win% | TP1% | TP2% | VAL avgR±se | PF | Y2025 avgR (n) | HOLD avgR (n) | random median [5-95%] | stress avgR | PASS/FAIL |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BB | tf=15,mult=2.0,htf=H1,sess=all; stop=1.5ATR TP1=1.0 TP2=2.0 be=True mh=120 | 31 | 0.011/129 | 147 | 1.67 | 49.7 | 32.7 | 11.6 | 0.0058±0.0762 | 1.01 | -0.0711 (402) | 0.2464 (18) | 0.0131 [-0.0504, 0.0581] | -0.0207 | FAIL: VAL avgR/se=0.08; Y2025 avgR<=0; VAL-rc=-0.007; stress<0 |
| RSI | tf=5,n=7,lo=25,trig=in,htf=H1; stop=1.5ATR TP1=0.75 TP2=1.5 be=False mh=120 | 35 | 0.0639/414 | 406 | 4.61 | 41.1 | 53.4 | 32.5 | -0.0775±0.0465 | 0.84 | -0.0786 (1280) | -0.1555 (81) | -0.0406 [-0.1749, 0.0065] | -0.1027 | FAIL: VAL avgR/se=-1.67; Y2025 avgR<=0; VAL-rc=-0.037; stress<0 |
| VWAP | tf=15,m=1.5,htf=H1,sess=all; stop=1.5ATR TP1=1.5 TP2=3.0 be=True mh=120 | 35 | 0.0728/123 | 162 | 1.84 | 44.4 | 24.1 | 4.3 | -0.0574±0.0824 | 0.88 | -0.032 (443) | 0.0067 (31) | -0.0494 [-0.1774, 0.0798] | -0.0866 | FAIL: VAL avgR/se=-0.70; Y2025 avgR<=0; VAL-rc=-0.008; stress<0 |
| KC | tf=15,m=2.0,htf=H1,sess=all; stop=1.5ATR TP1=0.5 TP2=1.5 be=True mh=120 | 35 | 0.099/43 | 52 | 0.59 | 63.5 | 61.5 | 17.3 | 0.0097±0.1009 | 1.03 | -0.0112 (153) | -0.0271 (6) | -0.0081 [-0.2216, 0.1983] | -0.0142 | FAIL: VAL avgR/se=0.10; Y2025 avgR<=0; VAL-rc=0.018; stress<0 |
| STOCH | tf=15,thr=20,candle=simple,htf=H1; stop=2.0ATR TP1=1.5 TP2=3.0 be=False mh=120 | 27 | 0.0686/176 | 220 | 2.5 | 48.2 | 10.0 | 2.7 | -0.009±0.0567 | 0.97 | -0.0762 (593) | -0.1966 (45) | -0.0091 [-0.0719, 0.0942] | -0.0218 | FAIL: VAL avgR/se=-0.16; Y2025 avgR<=0; VAL-rc=0.000; stress<0 |
| EXT | tf=5,n=50,x=4.0,htf=H1; stop=1.5ATR TP1=1.0 TP2=2.0 be=True mh=60 | 35 | 0.2751/72 | 71 | 0.81 | 47.9 | 38.0 | 11.3 | -0.1071±0.1073 | 0.77 | 0.0881 (211) | -0.0959 (9) | -0.0390 [-0.2619, 0.1285] | -0.1375 | FAIL: VAL avgR/se=-1.00; VAL-rc=-0.068; stress<0 |
| ROUND | tf=15,step=5.0,pen=0.25,htf=H1; stop=2.0ATR TP1=1.0 TP2=2.0 be=False mh=240 | 35 | 0.0392/419 | 384 | 4.36 | 47.9 | 39.1 | 16.9 | 0.0276±0.0486 | 1.07 | -0.0234 (1012) | 0.0411 (83) | -0.0106 [-0.0660, 0.1015] | 0.0145 | FAIL: VAL avgR/se=0.57; Y2025 avgR<=0; VAL-rc=0.038 |
| ASIA | tf=5,r_end=1200,t_end=150,htf=none; stop=1.5ATR TP1=1.5 TP2=3.0 be=False mh=60 | 35 | 0.1056/175 | 223 | 2.53 | 32.7 | 24.7 | 6.7 | -0.2614±0.0738 | 0.6 | -0.0509 (673) | -0.0247 (49) | -0.0313 [-0.1105, 0.1141] | -0.2871 | FAIL: VAL avgR/se=-3.54; Y2025 avgR<=0; VAL-rc=-0.230; stress<0 |
| ZSCORE | tf=1,z=2.2,adx=0,sess=src,htf=H1; stop=2.0ATR TP1=1.0 TP2=2.0 be=False mh=120 | 28 | 0.1231/77 | 73 | 0.83 | 31.5 | 39.7 | 23.3 | -0.263±0.1224 | 0.58 | -0.2777 (162) | -0.1407 (12) | -0.0633 [-0.2558, 0.0950] | -0.3357 | FAIL: VAL avgR/se=-2.15; Y2025 avgR<=0; VAL-rc=-0.200; stress<0 |
| BBRSI | tf=5,band=mid,adx=32,htf=none; stop=2.0ATR TP1=0.5 TP2=1.5 be=True mh=240 | 35 | 0.026/246 | 257 | 2.92 | 63.0 | 62.6 | 24.9 | -0.0186±0.0498 | 0.95 | -0.1171 (801) | -0.1726 (67) | -0.0484 [-0.1882, 0.0388] | -0.0432 | FAIL: VAL avgR/se=-0.37; Y2025 avgR<=0; VAL-rc=0.030; stress<0 |
| VWAPZ | tf=5,z=4.0,htf=H1; stop=2.0ATR TP1=1.0 TP2=2.0 be=False mh=240 | 29 | 0.171/69 | 72 | 0.82 | 40.3 | 47.2 | 25.0 | -0.0256±0.1253 | 0.95 | -0.0408 (215) | 0.1146 (10) | -0.0637 [-0.2995, 0.0915] | -0.0624 | FAIL: VAL avgR/se=-0.20; Y2025 avgR<=0; VAL-rc=0.038; stress<0 |

## Findings
1. **Nothing passes.**
   - Only 3 of 11 families are positive on VAL: ROUND +0.028R, KC +0.010R and BB +0.006R. All three are under 0.6 standard errors from zero.
   - None beats its random control by 0.05R. The best margin is +0.038R.
   - 10 of 11 go negative in the stress test.
   - 10 of 11 are negative in 2025. EXT is +0.088R in 2025 but −0.107R on VAL.
2. **The DISC edges were selection noise.**
   - The 11 DISC winners averaged +0.096R on DISC and −0.071R on VAL.
   - At the base exit, only 35 of 238 stage-A variants were positive on DISC.
   - The winners were fragile. On an earlier partial download, which had a gap from Jul 2025 to Jan 2026 that distorted indicator warm-up in early January, the search picked different variants in 5 families. The table comes from the final run on complete data.
3. **A high win rate is not an edge.**
   - TP1 0.5R with break-even won 59–76% of trades on DISC but averaged only −0.02 to +0.10R.
   - On VAL, KC wins 63.5% of trades for +0.010R, and BBRSI wins 63.0% for −0.019R.
4. **M1 is the worst timeframe.** The 42 M1 stage-A variants averaged −0.079R on DISC: spread plus noise against a roughly $3.5 M1 ATR.
5. **The H1 trend filter did not survive VAL.** Buying dips only above the H1 EMA50 helped a little on DISC (stage-A mean −0.036R with the filter, −0.060R without) and was chosen in 9 of 11 families, but it did not hold up on VAL.
6. **Two families are clearly negative out of sample.** The Asian-range fade and the scout's M1 z-score scalper (#10) both lose about 0.26R per trade on VAL (t = −3.5 and −2.1).
   - Gold in 2025–26 trended hard, and extended moves kept going past fixed-ATR stops.

**Recommendation:** do not ship a mean-reversion signal from Team B.

## Family definitions
All signals fire on closed bars of the chart timeframe. Entry is at the next 1-minute open.
- **BB:** BB(20, mult). The previous close was outside the band and this close is back inside.
- **RSI:** RSI(n) crosses into the lo/100−lo zone (`in`), or the previous bar was in the zone and this bar closes out of it (`out`).
- **VWAP:** session VWAP (17:00 New York anchor) ± m × volume-weighted stdev. A close back inside after a close outside. No signals between 17:00 and 19:00 New York.
- **KC:** EMA20 ± m × ATR10. A close back inside after a close outside.
- **STOCH:** %K(14,3) below thr on the previous bar (mirror for sells) and a reversal candle on this bar.
  - `simple`: close > open and close > previous close.
  - `strong`: close > open and close > previous high.
- **EXT:** the previous bar's (close − EMA n)/ATR14 is at least x (sell, mirror for buy), and this bar's candle has the opposite colour.
- **ROUND:** the bar wicks at least pen × ATR through the nearest $step level beyond the previous close and closes back on the original side.
  - BUY: L = floor(close[1]/step) × step, close[1] > L, low < L − pen × ATR, close > L.
- **ASIA:** the range is 18:00 New York to r_end. Between r_end and t_end, a wick beyond the range with a close back inside is faded.
- **ZSCORE:** scout #10.
  - z = (close − SMA20)/SD20, |z| ≥ 2.2, and a turn bar.
  - ATR14/SMA50(ATR14) between 0.4 and 2.0.
  - Cost gates: SD20 ≥ $0.90 and |SMA − close| ≥ $1.50.
  - adx=0 means the ADX ≤ 22 gate is off.
  - sess=src means 03:00–12:59 New York.
- **BBRSI:** scout #12, BB(60,2) with RSI(20) crossing over 35 or under 65, and ADX(14) < 32 (adx=0 means the gate is off).
  - `src`: exactly as the source codes it (buy: close < upper band; sell: close > upper band).
  - `mid`: buy only below the BB basis, sell only above it.
- **VWAPZ:** scout #13. z = (close − daily VWAP)/stdev(close, 20). Buy when z ≤ −z on a bullish candle; sell when z ≥ z on a bearish candle.

`best_signals()` returns ROUND, since it has the highest VAL avgR and nothing passed. Simulate it with `frost.simulate(sig, **teamB.BEST_SIM)`, where BEST_SIM is be=False, max_hold=240.

**ROUND in Pine (M15):**
- **BUY:** close[1] > L, low < L − 0.25 × ATR(14) and close > L, where L = math.floor(close[1]/5) × 5. The last completed H1 bar must close above its EMA50: `request.security(..., "60", close > ta.ema(close, 50))`, lookahead off.
- **Levels:** SL = close − 2 × ATR, TP1 = +1R, TP2 = +2R, time stop 240 minutes.
- **SELL:** the mirror, using math.ceil.

## Sources (scout report)
- #10 z-score reversion: github.com/n30dyn4m1c/gold-pro-scalper, `XAU_Quant_Reversion_TickRobust.mq5` (MIT).
- #12 Bollinger(60,2) + RSI(20) + ADX: github.com/hasnocool/tradingview-pine-scripts, exlux99's "Bollinger Bands, RSI and ADX Trading System" (MPL-2.0).
- #13 daily VWAP z-band: github.com/nopponkaeward-max/EA_ATR_news, `StatDayTrade.pine`.
- #20 round numbers: CANX $5 levels, GCGrid (TradingView) and github.com/mhs54/tradingview-indicator. This is the ROUND family. Its $5 and $10 steps were already in our plan; the $50/$100 close-through variant is a breakout, not a fade, so we did not test it.
- **Engine:** no bug found in frost.py.
