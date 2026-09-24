# Gold 20x50: XAUUSD, 20 setups a day, TP 50 pips

## TradingView indicator: `Gold_20x50_Setups.pine`

**Install:** open TradingView → Pine Editor → paste the file → Add to chart. Use XAUUSD on a 1 to 15 minute chart.

**What it draws:**
- **Setups:** 20 per trading day, at the first bar of each hour 08:00, 09:00 … 23:00, 00:00, 01:00, 02:00, 03:00, Malaysia time. The trading day runs 07:00 to 06:59 MYT.
- **Colors:** BUY labels are gold (#D4AF37), SELL labels olive green (#808000), and TP lines and TP hits gold. SL lines are dotted gray.
- **Direction:** buy when the previous daily close is above its 50-day SMA, otherwise sell. It can be set to buy only or sell only.
- **Levels:** TP is 50 pips ($5.00) from the fill. SL is an input, default 30 pips. Spread is an input, default 3 pips.
- **Scoring:** outcomes are scored bar by bar. If TP and SL are both touched in the same bar, the trade counts as SL.
- **Day split:** a dashed line at each trading-day start, labelled with that day's tally, e.g. `TP 7/20 SL 13`.
- **Table:** today's setups, TP and SL, plus results for all days on the chart (average TP per 20 and days with 18+ TP). Below that is a trade history of the last 20 trades: time, side, entry, TP, SL and result.
- **Alerts:** on every BUY and SELL setup.

## Measured results

The Python engine (`engine.py`) runs the same rules on Twelve Data XAU/USD bars. It fills at the bar open plus a 3-pip spread, and counts a TP and SL in the same bar as SL.

| Data | Direction | TP / SL (pips) | Days with 20 setups | Avg TP per 20 | Days with 18+ TP |
|---|---|---|---|---|---|
| M1, Aug 2025 to Sep 2026 | SMA-50 buy/sell | 50 / 30 | 298 | 7.2 | 0.7% |
| M1, Aug 2025 to Sep 2026 | buy only | 50 / 30 | 298 | 7.3 | 0.3% |
| M15, Jun 2020 to Sep 2026 | SMA-50 buy/sell | 50 / 30 | 1569 | 6.7 | 0.2% |
| M1, Aug 2025 to Sep 2026 | SMA-50 buy/sell | 50 / 2500 | 293 | 19.7 | 96.2% |
| M15, Jun 2020 to Sep 2026 | buy only (`strategy.py`) | 50 / 2500 | 1613 | 19.8 | 97.8% |

**SL 30 can't produce 18 of 20.** A 30-pip stop sits closer than a 50-pip target, and gold touches it first about 64% of the time. `smc_edge_study.py` tested each SMC concept separately, and a model on all of them together:

- Concepts tested: structure, BOS/CHoCH, FVG, order blocks, liquidity sweeps, premium/discount and sessions.
- None of them predicted the next move better than plain buy-only on 2024-2026 data. The model's test AUC was 0.45-0.53, which is chance level.

**What produces 18-20 of 20 is the wide stop.** SL 2500 pips with buy-only (gold's long-run uptrend) does it:

- **Cost of one loss:** 2,500 pips, which erases 50 wins.
- **Drawdown:** the backtest max drawdown was $17,015 per 0.01 lot per entry.
- **Open trades:** up to 275 trades were open at once.
- **Net result:** +$95,175 per 0.01 lot per entry over 2020-2026. Only 2026 was negative (-$6,530).
- **The edge is gold's uptrend:** in a falling market a buy-only rule loses.

To see this on the chart, set SL to 2500 in the indicator.

## Files

| File | Contents |
|---|---|
| `Gold_20x50_Setups.pine` | The TradingView indicator |
| `strategy.py`, `engine.py` | Slot schedule, rules and backtest engine |
| `run_strategy.py` | Year-by-year results and `trades.csv` |
| `analyze_timeframes.py` | The same rules on each timeframe |
| `smc_edge_study.py`, `features.py` | The SMC reverse-engineering study, using `../smc_strategy/smc.py` |
| `download_twelvedata.py` | Twelve Data downloader; set `TWELVEDATA_API_KEY` first |
| `test_engine.py` | 9 fill and exit rule tests |
