# SMC daily-bias scalper: XAUUSD M1, TP 50 pips, 20 entries a day

## Rules

| | |
|---|---|
| Bias | SMC market structure (BOS/CHoCH trend) on D1, built from the M1 feed |
| Confirmation | The previous day's candle closed in the bias direction. If they disagree, no trades that day |
| Entries | One every 5 min in the bias direction from 01:00, 20 per day maximum |
| TP | Exactly 50 pips ($5.00) |
| SL | 800 pips ($80.00) |
| Costs | 3-pip spread on every trade |
| Weekends and data holes | Open trades are closed at the last bar before any hole longer than 3 h. They count as losses |

## Results

The backtest follows these rules:

- A signal is known at a bar's close, and the entry fills at the next bar's open.
- If TP and SL are both touched in the same bar, it counts as SL.
- A TP always pays exactly 50 pips, even if the bar gaps past it.
- The rules were chosen on 2025 data, checked on Jan-Apr 2026, and locked before the May-Aug 2026 test was run once.

| Period | 20-trade days | Days with ≥18/20 TP | Avg TP per 20 | Win rate | Net pips | Worst day |
|---|---|---|---|---|---|---|
| Train 2025 | 67 | 79% | 18.1 | 90.5% | +31,202 | -4,950 |
| Validation Jan-Apr 2026 | 19 | 95% | 19.5 | 97.4% | +10,500 | -5,800 |
| **Test May-Aug 2026** | 20 | **85%** | **17.6** | 88.0% | **-16,474** | -15,150 |
| All | 106 | 83% | 18.3 | 91.3% | +25,228 | -15,150 |

On the unseen test, 17 of 20 days were a perfect 20/20. The other three went 1/20, 1/20 and 10/20. Each bad day cost more than the 17 good days made together, so the test lost money.

## What this means

- **High hit rate comes from the stop, not the signal.** A 50-pip TP with an 800-pip SL hits about 94% of the time even on a random walk. SMC bias adds only a few points on top of that.
- **The 20 entries a day are really one bet.** They go in the same direction within about 100 minutes, so a day ends up almost 20/20 or almost 0/20.
- **It breaks even only at about 94% good days.** One 800-pip loss erases 16 wins, and on the test only 85% of days were good.
- **Days with no bias get no trades.** When D1 structure and the previous candle disagree, the strategy sits out. That happened on 140 of 247 days (57%), and on those days you get 0 signals, not 20.
- **The M1 file doesn't agree with its own H1 bars.** The median close difference is about $30 per hour, and no timezone offset fixes it. M1 also has weekend bars and gaps: about 15 days per month in 5,000-bar chunks. Verify on a clean broker feed before you trust any of these numbers.

## Files

| File | Contents |
|---|---|
| `smc.py` | Causal SMC detectors: swings, BOS/CHoCH, FVG, order blocks, liquidity sweeps, premium/discount, session levels |
| `data.py` | Loader and cleaning; `quality_report()` |
| `backtest.py` | numba M1 backtester and a random-entry baseline |
| `strategy.py` | Strategy rules and the locked `FINAL` parameters |
| `run_backtest.py` | Reproduces the results table |

Run it with:

```
python3 run_backtest.py XAUUSD_M1_H1_2025-2026Aug.csv
```

Tests:

| Test | What it checks |
|---|---|
| `test_backtest.py` | 16 fill and exit rules |
| `test_smc.py` | No look-ahead in the SMC detectors |
| `test_strategy.py <csv>` | No look-ahead in the full signal pipeline |
