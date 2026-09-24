# Falcon Confluence Pro

A multi-factor trend and momentum indicator for **TradingView (Pine Script v6)**. It gives BUY/SELL signals that don't repaint, sets a stop and three targets for every trade, manages the trade bar by bar, and keeps a live scorecard of how the signals have performed on the chart you're viewing.

File: [`falcon_confluence_pro.pine`](falcon_confluence_pro.pine)

---

## Install (2 minutes)

1. Open any chart on TradingView and click **Pine Editor** at the bottom.
2. Delete the template code, then paste the whole contents of `falcon_confluence_pro.pine`.
3. Click **Save**, then **Add to chart**.
4. Open the gear icon to change settings. Every input has a tooltip.

## How a signal is formed

On every bar the indicator scores **six independent factors** for each side:

| # | Factor | Long passes when… (shorts are the mirror) |
|---|--------|-------------------------------------------|
| 1 | Trend | Close > EMA 200 **and** EMA 21 > EMA 50 |
| 2 | Supertrend | Supertrend (10, 3.0) is in an uptrend |
| 3 | Strength & regime | ADX ≥ 20, +DI > −DI, and Choppiness Index < 61.8 (market is trending, not ranging) |
| 4 | Momentum | RSI > 50 **and** MACD histogram > 0 |
| 5 | Volume | Volume ≥ its 20-bar average, on a green candle |
| 6 | Higher timeframe | The previous *closed* HTF bar closed above a rising HTF EMA 50 |

A **BUY** prints only when all of the following hold:

- a **trigger** fires. Either the Supertrend flips up, or there's a **trend pullback**: price dips to the fast EMA and then closes back above it and above the previous bar's high.
- the long score is **≥ the minimum** (default 4 of 6).
- RSI is **not overbought**, so it won't chase exhausted moves.
- the **cooldown** has passed and no long is already open.

A 6/6 signal is marked **★ STRONG**. An opposite signal closes the open trade (a reversal) and opens the new one.

Factors that are switched off, and the volume factor on symbols with no volume data, count as passed. So "6/6" means *every active factor agrees*.

## Trade management

- **Stop:** *Swing* (default) sits beyond the recent swing low or high plus an ATR buffer. If that stop would be closer than 0.5 × ATR or further than 3 × ATR, the *ATR* stop (1.5 × ATR) is used instead.
- **Targets:** TP1 / TP2 / TP3 at 1R / 2R / 3R. One third of the position comes off at each target.
- **Protection:** after TP1 the stop moves to breakeven. After TP2 it trails to TP1. Both can be toggled.
- The live levels are drawn on the chart and relabelled as they fill (✓).

## Non-repainting guarantees

- Signals only print on **closed bars**. A signal you see will never disappear.
- Higher-timeframe data comes from the **previous closed HTF bar** (`[1]` offset + `lookahead_on`, TradingView's documented non-repainting pattern).
- Outcomes are judged **conservatively**. If one bar touches both the stop and a target, the stop counts first. A stop that gaps through fills at the open, not at the stop price. Targets fill at their price, never better.

## Dashboard

Shows the current bias, the state of every factor, both scores, the open position with its stop, next target and open P&L, and the scorecard: closed trades, win rate, TP1/TP2/TP3 hit rates, net R, profit factor and max drawdown (in R).

"R" means multiples of the initial risk. +2R means twice what was risked on the trade.

## Alerts

Right-click the chart → **Add alert** → Condition: *Falcon Confluence Pro*, then choose one of:

- **Falcon Pro · Buy / Sell / Any signal**: simple signal alerts.
- **Any alert() function call** (recommended): one message per closed bar with the full plan (entry, SL, TP1–3, score), plus TP-hit, stop and reversal events.

Set the alert to trigger **Once Per Bar Close**, the same way the indicator itself evaluates.

## Suggested starting points

| Style | Chart | Notes |
|-------|-------|-------|
| Scalping | 5m | HTF auto → 1H. Raise the minimum score to 5 for fewer, cleaner signals. |
| Intraday | 15m – 1H | Defaults. HTF auto → 4H. |
| Swing | 4H – D | Defaults. HTF auto → D / W. |

## Honest limitations

- The scorecard is a **hypothetical backtest** on the bars loaded in your chart. It includes no commissions, spread or slippage. Past results do not guarantee future results.
- No indicator wins every trade. The edge comes from waiting for confluence, cutting losers at the stop, and letting the targets work.
- Test on your own market and timeframe (and on a demo account) before risking real money. This is a decision-support tool, not financial advice.
