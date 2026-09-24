# Team meeting: which technique maximises P($30 → $5,000 by 1 Nov 2026)?

Five research agents plus the lead each took a set of technique families and ran them through **one identical protocol**:

- **Data:** about 2.7 years of H1 price data on 11 instruments (EURUSD, GBPUSD, AUDUSD, NZDUSD, USDCAD, GBPAUD, USDJPY, EURJPY, GBPJPY, XAUUSD, XAGUSD).
- **Costs:** every trade pays spread; longs fill at the ask, shorts stop on the ask. Swap is 0.5 pip per night, Wednesday counts ×3. Gapped stops fill at the open.
- **Discovery vs validation:** each family's settings were chosen on 5 instruments only, then tested unchanged on 6 instruments it never saw, split into two time halves.
- **Pass:** average profit per trade (R) above 0 after costs, on the unseen instruments, in **both** halves.
- **Control:** random entries with the same stop, target and exit rules, to show what the exits alone produce.

## Results by team (the best settings from each family)

| Team | Family | Win % | Net R/trade | Passed |
|---|---|---|---|---|
| A · mean reversion | RSI-2 dip (target 0.5 ATR, stop 2.5 ATR) | **78.3** | −0.038 | ✗ |
| A | Bollinger fade | 66.7 | −0.069 | ✗ |
| A | Asian-range fade | 42.6 | −0.135 | ✗ |
| A | Previous-day high/low fade | 41.9 | −0.089 | ✗ |
| B · small targets | Sweep reversal, 0.5R target | 61.1 | −0.089 | ✗ |
| B | London breakout, 0.5× range target | **69.7** | −0.030 | ✗ |
| B | NY momentum pullback | 42–60 | −0.09 to −0.17 | ✗ |
| B | Trend pullback, small target | 60.4 | −0.104 | ✗ |
| C · trend & momentum | **EMA 9/21 cross, H4, 2R** | 35.7 | **+0.018** | ✗ (u1 +0.027, u2 −0.010) |
| C | Supertrend · MACD · ADX · BB squeeze · daily momentum · Donchian | 25–51 | −0.018 to −0.111 | ✗ |
| D · price action & SMC | FVG · order block · candles · Fibonacci · pivots · round numbers · prior-day/week levels | 32–47 | −0.013 to −0.161 | ✗ |
| E · sessions & calendar | time of day · day of week · weekend gap · London fix · volatility regime · NY opening range · carry | 45–66 | −0.077 to +0.005 | ✗ |
| Lead · combinations | C1 sweep + H4 trend | 12.3 | −0.029 | ✗ |
| Lead | C2 RSI-2 dip + H4 trend | 78.4 | −0.037 | ✗ |
| Lead | **C3 EMA 9/21 cross after a same-direction sweep (H4, 2R)** | 37.6 | **+0.066** | ✅ (u1 +0.198, u2 +0.018) |
| Lead | C4 RSI-2 dip after a sweep | 76.2 | −0.063 | ✗ |

**What the random controls showed:** win rates of 65–78% come from the exit shape, a small target against a large stop. Random entries with the same exits win 60–73% of the time. Most families show a small edge before costs (+0.01 to +0.09R), but spread and swap (about 0.05R per trade) remove it.

## Ranking by the goal that matters

The maximum P(goal by the deadline) is computed with an exact dynamic programme over each strategy's real trades, with optimal risk before every trade:

| Rank | Strategy | Max P($60) | Max P($500) | Max P($5,000) |
|---|---|---|---|---|
| **1** | **C3 Trend-Sweep** | **53.5%** | **7.72%** | **0.886%** |
| 2 | EMA 9/21 cross | 48.6% | 6.08% | 0.634% |
| 3 | Round-number fade | 47.0% | 5.45% | 0.522% |
| 4 | V7 sweep, 300 pips | 39.9% | 4.88% | 0.484% |
| … | London breakout (69.7% win) | 44.3% | 4.04% | 0.287% |
| … | RSI-2 dip (78.3% win) | 37.1% | 1.79% | 0.013% |

These figures assume enough trades are available. The October plan, with the real trade count, is in the README.

## Decision

**V20 uses C3 Trend-Sweep.** It is the only strategy that passed validation, and it ranks first for every goal level. The highest-win-rate strategies rank last for a far goal: their small wins can't compound fast enough, and costs take more from them.

Evidence strength: C3's edge is +0.066R ± 0.054 per trade (about 1.2 standard errors), and the combinations were designed after the family results were known. The plan's probabilities are computed from its actual trade outcomes, not from an assumed edge.
