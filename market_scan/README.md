# Market scan: which market gives 18+ of 20 TP with the least risk?

## The setup

- **Entries:** 20 per day, at the first bar of each hour 08:00 … 23:00, 00:00, 01:00, 02:00, 03:00, Malaysia time.
- **Exits:** a fixed TP and a fixed SL.
- **Fills:** at the bar open plus the estimated JustMarkets Standard spread.
- **Same-bar rule:** if TP and SL are touched in the same bar, it counts as SL.
- **Unresolved trades:** a trade still open after 30 days is closed at market and counts as not-TP.
- **Data:** Dukascopy M5 bars for 21 markets.

**Rules tested:** buy, sell, daily SMA-50 trend, 20-day trend, and follow or fade the 4h/24h mean. The fade rule is SMC premium/discount: buy below the 24h equilibrium, sell above it.

**Method:**
1. **Choose (2021-23):** for each market, pick the smallest SL/TP ratio that had 18+ TP on at least 90% of days, with positive expectancy.
2. **Check (2024-26):** see how that exact setting did afterwards.
3. **Unseen (2016-20):** run the top picks on these years, which weren't used for anything else.

## Result

| Market, setting | 2016-20 unseen | 2021-23 (chosen here) | 2024-26 check |
|---|---|---|---|
| **US500 (S&P 500), buy, TP 20 / SL 300 pts** | **92.0% of days 18+, avg 18.9/20, +9.6 pts/trade** | 91.1%, 18.9, +4.4 | 89.8%, 18.9, +3.8 |
| US100 (NASDAQ), buy, TP 50 / SL 1200 pts | 93.3%, 19.1, +28.1 | 91.8%, 19.2, +4.6 | 90.0%, 19.2, +3.1 |
| EURJPY, buy, TP 30 / SL 900 pips | 87.4%, 18.5, +3.1 | 90.3%, 19.0, +10.9 | 94.5%, 19.5, +14.6 |
| EURGBP, 24h fade, TP 10 / SL 200 pips | 86.3%, 18.9, −1.6 | 90.9%, 19.3, +3.7 | 89.4%, 19.0, +3.5 |
| USDJPY, buy, TP 50 / SL 900 pips | 75.4%, 16.3, −4.8 | 90.5%, 18.8, +21.8 | 90.1%, 18.9, +9.4 |
| XAUUSD, buy, TP 50 / SL 900 pips (18:1) | not tested | 87.8%, 18.8, −5.8 | 88.3%, 19.3, +15.0 |

**Pick: US500 buy, TP 20 / SL 300 points.**

- **Lowest risk ratio:** SL is 15× TP.
- **Gold does worse at every ratio:**
  - At 12:1, gold had 18+ days only 81-84% of the time.
  - At 24:1, it reached 89-92% but lost money in 2021-23.
- **Consistent:** about 90-92% of days with 18+ TP and positive expectancy in all three periods.
- **Survives higher costs:** still positive with a 2-point spread.
- **Stable settings:** nearby settings (TP 15-30, SL 200-600) give 84-93% of days with 18+.

**US100 is the Nasdaq option.** It is just as consistent, but needs a 24:1 stop.

The full table is in `scan_results.csv`, and `robust.py` reproduces the 2016-20 and stress checks.

## Honest limits

- **Days aren't guaranteed.** About 1 day in 10 still lands below 18. A losing trade costs 15 wins (US500) or 24 wins (US100).
- **The edge is the long-term uptrend.** The S&P/NASDAQ buy edge comes from the indices rising over time, so a long bear market would hurt it.
- **Swap isn't included.** Long index CFDs pay overnight swap; winners usually close within hours.
- **Check the contract size on JustMarkets.** Open MT5, right-click US500 → Specification.
  - USD per point at 0.01 lot = contract size × 0.01.
  - With contract size 1, a 20-point TP pays $0.20 at 0.01 lot. To win about $5 per TP like your gold trades, you'd use 0.25 lot.

## TradingView

**Install:** paste `Twenty_Setups.pine` into the Pine Editor and add it to a US500 chart, 5 m recommended (any S&P 500 CFD feed works).

**Presets:** US500 (default), US100, EURGBP, XAUUSD and Custom.

**Styles:**
- BUY labels are gold.
- SELL labels are olive green.
- TP lines and TP hits are gold.
- SL lines and SL hits are gray.

**What it shows:**
- **Day split:** each trading day starts with a dashed line and a tally.
- **Table:** today's count, the hit rate on your chart, and the last 20 trades.

**Files:**

| File | Contents |
|---|---|
| `scan.py` | The 21-market scan |
| `rank.py` | Picks each market's setting on 2021-23 |
| `robust.py` | The 2016-20 check, spread stress and nearby settings |

Data is downloaded with `npx dukascopy-node -i usa500idxusd -from 2021-01-01 -to 2026-09-23 -t m5 -f csv`.
