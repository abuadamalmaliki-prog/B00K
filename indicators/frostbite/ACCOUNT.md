# Account notes: JustMarkets Standard, $30

| Spec | Value | What it means for Frostbite |
|---|---|---|
| Execution | Market; scalping and EAs allowed | Frostbite's 5-minute scalps are allowed |
| Minimum lot | **0.01** | On gold, 0.01 lot = 1 oz, so **$1 per $1 move**. This decides the risk, not your % setting. |
| Maximum lot | 100 | — |
| Spread | From 0.3 pips, floating, no commission | Frostbite's cost model uses $0.30 on gold. Set **Spread** to what MT5 shows for XAUUSD. |
| Leverage | Up to 1:3000 | Margin for 0.01 lot of gold at ~$4,300 ≈ **$1.43**. Margin is never the limit here; the stop loss is. |
| Margin call / stop-out | 40% / 20% | If a loss takes equity below 20% of margin (≈ $0.29 per 0.01 lot), MT5 closes the order before the SL. That happens only when the balance is smaller than the stop's loss. |
| Swap-free option | Islamic account | Not needed: Frostbite closes every trade within 2 hours and before the 17:00 New York rollover, so no swap is charged. |
| Account currencies | USD, MYR, … | Frostbite shows risk in USD. On a MYR account, convert the balance to USD when you enter it. |

## The arithmetic for $30

| | Risk per signal at 0.01 lot | Share of $30 |
|---|---|---|
| Typical stop 2026 (~$13) · **1 order** | ~$13 | ~45% |
| Typical stop 2026 (~$13) · 2 orders | ~$27 | ~90% |

- **Losing streaks:** in testing, the longest was 6 signals in Fewer mode and 9 in More mode. At $30, two to three stop-losses in a row use up the balance.
- **Auto setting:** with $30, *Orders per signal* picks **1 order → TP2**.
- **Why TP2:** over the periods not used for tuning, a single order aimed at TP2 averaged **+0.11R** in Fewer mode and **+0.06R** in More mode. That is better than the TP1 order (+0.07R / +0.05R), and the TP2 order was also better in the tuning period.
- **Warnings:** every alert and the panel show the exact $ risk and its % of your balance. They warn when a stop would cost more than the balance.
- **Smaller trades:** JustMarkets' Standard Cent account trades the same signals 100× smaller, about $0.13 per signal at 0.01 lot.

## What changed in the indicator after these specs

1. **New setting, *Orders per signal*:** Auto, 1 order → TP2, or 2 orders → TP1 + TP2. Auto picks 1 order when two 0.01-lot orders would exceed your risk setting.
2. **Risk display:** the alert and panel show risk in $ and as a % of balance, with a warning when the risk is larger than the balance.
3. **Physics check:** the smooth line is a Newtonian position + velocity model (Kalman filter). 92–98% of signals already point the same way as it moves. Filtering out the rest did not improve results (Fewer mode: +0.082R vs +0.089R), so the signals are unchanged.
