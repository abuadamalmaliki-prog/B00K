# Scout report: GitHub data and technique references

Every repository below was added to the session with read access and shallow-cloned. No downloaded code was run; only CSV and parquet files were parsed.

## 1. Data: XAUUSD January–August 2026 on GitHub

| # | Repository | File | Timeframe | Verified range (UTC) | Source | Verdict |
|---|---|---|---|---|---|---|
| A | Dypoi/XAUUSD_Dataset | `XAUUSD_M1_20250901_20260901.csv` | M1 bid + ask | 2025-09-01 → 2026-09-01 | not stated; **identical to Dukascopy** | Best. Clean: no duplicates, no NaN, trading minutes only |
| B | chrismwangi022-beep/XAU-LEAN | `…/dukascopy/…/xauusd_{bid,ask}_m1_2026_{01..08}.csv` | M1 bid, ask | 2026-01-01 → 2026-08-20 | Dukascopy (stated) | Identical to A |
| C | meffyou226-oss/Meffs | `data/xauusd_m1/XAUUSD_M1_2026_{01..08}.csv` | M1/M5/M15/H1 bid | 2026-01-01 → 2026-08-26 | Dukascopy (stated) | Identical to A; 33% flat filler rows |
| D | Sai310421/xauusd-data | `csv/XAUUSD/XAUUSD_M1_2026Q1Q2.csv` | M1 | 2026-02-25 → 2026-05-26 | says "mid quote"; is Dukascopy bid | Only 3 months |
| E | AhadRasheed/gold-strategy | `data/XAUUSD_5M.csv` | M5 (MT5 broker export) | 2025-04-11 → 2026-09-17 | unnamed MT5 broker; labelled +00:00 but really EET/EEST server time | **Independent feed**; after conversion, M5 return correlation with Dukascopy is 0.998 |
| F | simom1/XAUUSD-history | `2026/xauusd_2026_*.parquet` | ticks | Jan 2024 – Aug 2026 (README) | not Dukascopy; fixed $0.26 spread | Independent, but 602 MB |
| G | getdata-finance/xauusd-3m-… | `XAUUSD_3m.csv` | M3 | 2026-03-23 → 2026-09-23 | not stated | About $26 above spot; futures-like, not used |
| H | CoderABD7000/xauusd-gc-tick-data | `XAUUSD_M1_Sep_2026.csv` | M1 | September 2026 only | GC=F futures | Not used |

**Cross-check against our Dukascopy download.** All 112,831 overlapping bid minutes and all 118,471 overlapping ask minutes match file A exactly: time offset 0 hours, median difference $0.000, M5 return correlation 1.000. Our research data is therefore the same data that other people publish on GitHub for January–August 2026.

## 2. Technique catalogue

Performance figures are each source's own claims. None are verified.

1. **EMA 9/21/200 trend pullback, M5**: andamagodwin/forex (`xau_scalper/strategy.py`, `mql5/XauScalper.mq5`).
   - BUY when all of these hold:
     - close is above EMA200 and EMA21 is above EMA200;
     - price touched EMA21 within the last 5 bars;
     - a bullish bar closes above EMA9, with EMA9 above EMA21;
     - RSI is between 45 and 70 and rising;
     - ADX is at least 25.
   - Stop 1.5 ATR (minimum $1.50), take profit 1R, time stop 60 bars.
   - Entries only 07–17 UTC.
   - Claims PF 1.42 on 2026 data at a $0.20 spread, PF about 1.0 at $0.60, and PF 0.72 on M1.
2. **FA Gold Scalper v6, M15**: ruthphillipsi/XAUUSD-EA-20PROJECT (`FA_Gold_Scalper_v6.pine`).
   - BUY when all of these hold:
     - EMA34 > EMA50 > EMA200, and price touched EMA34 within the last 3 bars;
     - a bullish candle closes above the prior bar's high;
     - ADX is above 20 and RSI is between 45 and 70.
   - Stop at the 5-bar swing ± 0.2 ATR, clamped to 0.6–3 ATR; take profit 2R.
   - Entries only 13–17 UTC.
   - Claims PF 1.69 on M15 and PF 1.10 on M5.
3. **1-minute EMA 9×21 + VWAP + RSI with a 10-minute bias**: junutala/XAUStrategy (`XAU_Scalping_Strategy.pine`).
   - Stop 1.1 ATR. TP1 at 1.3R closes 50%, TP2 at 2.5R. Breakeven at +1R.
4. **Asian-range breakout**: Mrshahidali420/ORB-Multi-Model-Indicator (`XAU_Pro_Indicator.pine`, setup A).
   - Box 19:00–02:00 New York; skip the day if the box is wider than 2 ATR.
   - Trade the first close beyond the box + 0.05 ATR, between 03:00 and 11:30 New York.
   - Stop at the other side of the box, capped at 0.5–1.5 ATR; take profit 2R.
5. **New York opening-range breakout**: same repository (setup B), citing Crabel (1990) and Zarattini & Aziz (2023).
   - Range: the first 15 minutes after 09:30 or after the 08:20 COMEX open.
   - Trade only in the direction of the opening-range candle; take profit 2R; no new entries after 12:00 New York.
6. **Two-session breakout**: Andresfcarreno/forja- (`XAUUSD_SessionBreakout.pine`).
   - Box 00–07 UTC traded 07–11 UTC, and box 11:00–13:30 UTC traded 13:30–17:00 UTC.
   - Filters: H1 EMA50 above EMA200, and box size 0.5–3 ATR.
   - Stop 1.5 ATR, take profit 4R.
7. **London breakout of the last Tokyo hour**: je-suis-tm/quant-trading (`London Breakout backtest.py`, Apache-2.0).
8. **Dual Thrust**: same repository; attributed to M. Chalek.
   - Levels: open ± 0.5 × max(HH−LC, HC−LL) over 5 days.
9. **Previous-day high/low breakout, then retest**: phatnomenal/blackXAU_AUTOMATED-BOT-TRADE (`blackXAU2.mq5`).
   - An M5 close beyond the level with a strong body, then entry on the retest with an H1 EMA 50/200 filter.
10. **M1 Z-score reversion to SMA20**: n30dyn4m1c/gold-pro-scalper (`XAU_Quant_Reversion_TickRobust.mq5`, MIT).
    - Enter when |z| > 2.2 and the stretch has stopped, with ADX ≤ 22 and a cost gate.
    - Take profit at the mean; stop max($8, 2.5 ATR).
11. **M1 Donchian-30 breakout**: same repository.
    - Enter when ADX > 30, price is on the correct side of EMA50 and DI spread ≥ 5.
12. **Bollinger(60,2) + RSI(20) 35/65 + ADX < 32 range scalper**: hasnocool/tradingview-pine-scripts (exlux99, MPL-2.0).
13. **Daily VWAP band reversion**: nopponkaeward-max/EA_ATR_news (`StatDayTrade.pine`).
    - Enter at z = (close − VWAP)/stdev20 of ±2, on a reversal candle.
    - Stop 1.5 ATR, take profit 1.5R.
14. **TTM Squeeze**: Alorse/pinescript-strategies. Concept from J. Carter, *Mastering the Trade*.
15. **ICT Asian-range / previous-day high-low sweep reversal**: PineGen-AI/ICT-Daily-Liquidity-Sweep (README only).
    - A wick through the level, then a close back inside.
    - TP1 1.5R (closes 50%), TP2 3R.
    - Related: "Turtle Soup" from Raschke & Connors, *Street Smarts*.
16. **Previous-day high/low sweep, then a break of the reversal candle, M5, 1:2**: AhadRasheed/gold-strategy (`strategy.py`). Claims PF 1.34 without costs.
17. **ICT Silver Bullet (sweep, then fair value gap)**: cjosh4toyotas-stack/silver-bullet-backtest. The source's own test is **negative**: PF 0.64–0.69 on NQ, ES and CL.
18. **SMC sweep + displacement FVG + chandelier exit**: ManasDoitto/trading-pine-strategies. The source reports losses: PF 0.84–0.93.
19. **ATR news straddle at 08:30 New York**: nopponkaeward-max/EA_ATR_news (`EA_ATR_News.mq5`).
    - Stop orders at ± 1 ATR; stop 1 ATR, take profit 2R.
20. **$5 / $10 / $50 round-number levels**: CANX $5 levels and GCGrid on TradingView, and mhs54/tradingview-indicator.
    - Pullback-and-reject at the level, or the first close through a $50 or $100 level.

**Skipped:**
- Proprietary EAs with no rules (claims such as "PF 4.24, 81.7% win rate").
- Scripts that use a hard-coded "fair value".
- Strategies with no exits.

## 3. Sources

**Data:**
- github.com/Dypoi/XAUUSD_Dataset
- github.com/chrismwangi022-beep/XAU-LEAN
- github.com/meffyou226-oss/Meffs
- github.com/Sai310421/xauusd-data
- github.com/AhadRasheed/gold-strategy
- github.com/simom1/XAUUSD-history
- github.com/getdata-finance/xauusd-3m-ohlcv-metals-historical-data
- github.com/CoderABD7000/xauusd-gc-tick-data

**Techniques:**
- github.com/andamagodwin/forex
- github.com/ruthphillipsi/XAUUSD-EA-20PROJECT
- github.com/junutala/XAUStrategy
- github.com/Mrshahidali420/ORB-Multi-Model-Indicator
- github.com/Gannn10/XAUUSD-LNNY
- github.com/Andresfcarreno/forja-
- github.com/yulz008/GOLD_ORB
- github.com/je-suis-tm/quant-trading
- github.com/phatnomenal/blackXAU_AUTOMATED-BOT-TRADE
- github.com/n30dyn4m1c/gold-pro-scalper
- github.com/hasnocool/tradingview-pine-scripts
- github.com/nopponkaeward-max/EA_ATR_news
- github.com/Alorse/pinescript-strategies
- github.com/PineGen-AI/ICT-Daily-Liquidity-Sweep-PineGen-AI-
- github.com/cjosh4toyotas-stack/silver-bullet-backtest
- github.com/BAKOME-Hub/BAKOMEGoldScalper
- github.com/ManasDoitto/trading-pine-strategies
- github.com/mhs54/tradingview-indicator

**Lists:**
- github.com/just-nilux/awesome-tradingview
- github.com/pAulseperformance/awesome-pinescript
- github.com/freqtrade/freqtrade-strategies

**Books and papers** (cited only; not downloaded):
- Crabel, *Day Trading with Short Term Price Patterns and Opening Range Breakout* (1990)
- Zarattini & Aziz (2023)
- Raschke & Connors, *Street Smarts*
- Carter, *Mastering the Trade*
- Young, *Expert Advisor Programming for MetaTrader 5*
