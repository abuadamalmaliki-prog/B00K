# Research Trend Signals (Buy / Sell / TP / SL)

A TradingView **indicator** (Pine Script v6, not a strategy) built only from the four
papers it was asked to cover. It prints **BUY**, **SELL**, **TP** and **SL** levels, and it
does not use SMC, ICT or any pattern-based concepts.

File: [`research_trend_signals.pine`](research_trend_signals.pine)

## Install

1. TradingView → open a chart → **Pine Editor** (bottom panel).
2. Select everything in the editor, paste the whole file, press **Add to chart**.
3. It compiles with no errors and no warnings (checked against TradingView's own compiler).

## What you see

| On the chart | Meaning |
|---|---|
| Green **BUY** label under a bar | Long signal at that bar's close |
| Red **SELL** label over a bar | Short signal at that bar's close |
| Grey line | Entry price of the open trade |
| Green line **TP** | Take profit of the open trade |
| Red line **SL** | Stop loss of the open trade |
| Green circle "TP", red cross "SL" | The bar where the TP or SL was hit (drawn at the fill price) |
| Grey square "EXIT" | An opposite signal closed the trade at the close |
| Small grey × | A signal that a filter removed |
| Orange background | Financial-cycle boom zone |
| Purple background | Funding-stress regime |
| Coloured line | Trend reference price (EMA) |

The dashboard (top right) shows the current trend signal, the position and its levels, the
TP distance, the cycle gap, the stress reading, and counts of trades, TP hits, SL hits and
signal exits, with the net result in R (1R = the stop distance). **Costs and slippage are not
included.**

## Where each rule comes from

| Output | Paper | What is used |
|---|---|---|
| **BUY / SELL** | Lempérière, Deremble, Seager, Potters & Bouchaud (2014), *Two centuries of trend following* (arXiv:1404.3274) | Their trend signal, Eq. (1): `s = (p(t) − EMAₙ of prices up to t−1) / σₙ`, with `σₙ` = EMA of absolute price changes (EMA decay 1/n). Their fitted saturation, Eq. (3): conviction = `tanh(s / s*)`, `s* ≈ 0.89`. BUY when conviction crosses above +c, SELL when it crosses below −c. |
| **TP** | Avellaneda & Stoikov (2008), *High-frequency trading in a limit order book* (Quantitative Finance 8:3) | The optimal exit quote for inventory q = +1 (long) or −1 (short): reservation price `r = s − qγσ²(T−t)` (Eq. 29) ± half the optimal spread `γσ²(T−t) + (2/γ)ln(1+γ/k)` (Eq. 30). For a long, TP = entry + σ·[(1/γ)ln(1+γ/k) − γ(T−t)/2]. |
| **SL** | Lempérière et al. (2014) | The paper sizes every position by 1/σₙ, so σₙ is its unit of risk. SL = entry ∓ (multiple) × σₙ. |
| Funding-stress filter | Goldberg, Kennedy & Miu (2010), *Central bank dollar swap lines and overseas dollar funding costs* (NBER WP 15763) | The paper tracks dollar-funding stress (LIBOR-OIS, FX-swap basis). LIBOR no longer exists, so the default gauge is the St. Louis Fed Financial Stress Index `FRED:STLFSI4`, which is built from funding spreads. BUY signals are skipped while it is above 1.0. |
| Financial-cycle filter | Borio (2012), *The financial cycle and macroeconomics: what have we learnt?* (BIS WP 395) | The BIS real-time early-warning method: the gap between the (log) price and its **one-sided** Hodrick-Prescott trend, with the 15–25 % danger zone used for property-price gaps. BUY signals are skipped when the gap is 20 % or more. |

The one-sided HP filter is the Kalman filter of Meyer-Gohde (2010), as implemented in
`hp1()` of [alexandrumonahov/hpfilter](https://github.com/alexandrumonahov/hpfilter)
(CC BY-SA 4.0). It is written here as scalar recursions of the same model
(Hamilton 1994, ch. 13).

## Settings and why the defaults are what they are

**Buy / Sell**
- *Trend horizon n* = 50 bars. The paper used 5 months on monthly data and found the effect robust from 2.5 to 10 months. It also found that very short trends (a few days) have weakened since 1990. On a daily chart that range is about 50–210 bars, so daily or higher timeframes fit the paper best.
- *Saturation s\** = 0.89, the paper's fitted value.
- *Minimum conviction* = 0.5. 0 gives the paper's pure sign(s) rule; 0.5 adds a dead band against whipsaw.

**Take profit** (Avellaneda & Stoikov)
- *γ* = 0.0141 and *k* = 0.212 are the paper's simulation values (γ = 0.1, k = 1.5, σ = 2, dt = 0.005) rescaled to units of one bar's volatility (× σ√dt = 0.1414). This makes them work on any symbol and timeframe.
- *Horizon T − t* = 50 bars. With the defaults the TP sits about 4.2 σ from entry, where σ is the RMS bar-to-bar change. The horizon is capped at 500 bars; if other settings would put the TP on the wrong side of entry, it is floored at 0.5 σ and the dashboard says so.

**Stop loss**
- 3.0 × σₙ from entry.

**Financial-cycle filter**
- *Cut-off period* = 2000 bars, so λ = 1 / (16 sin⁴(π / period)). For reference, the BIS credit gap's λ = 400,000 on quarterly data is a cut-off of 158 quarters. 2000 daily bars is about 8 years. The first quarter of the period is warm-up, during which the filter never blocks.
- *Boom-zone gap* = 20 %, the midpoint of the BIS 15–25 % property-price band.

**Funding-stress filter**
- *Threshold* = 1.0 on STLFSI4 (0 = average conditions). Since 1993 it has been above 1.0 in about 8 % of weeks, and those weeks line up with the known stress episodes: 1998, 2001–02, **Aug 2007 – Jul 2009** (the period the NBER paper studies), 2010–11, early 2016, Mar–May 2020 and Mar 2023. If you switch to another gauge, such as `TVC:VIX`, set a threshold on that gauge's scale.

## Alerts

Create an alert on the indicator and choose one of:
- **BUY** / **SELL**: the message includes the entry, TP and SL prices.
- **TP hit** / **SL hit** / **Signal exit**.
- **Any alert() function call**: a single alert with every event of the bar and its prices.

Use "Once Per Bar Close".

## Repainting

- Signals, TP/SL hits and exits are evaluated only on closed bars (`barstate.isconfirmed`), so what you see in history is what you would have seen live.
- The stress index is read with `request.security(..., close[1], lookahead = barmerge.lookahead_on)`, which gives the last completed value. This is the non-repainting form from the Pine docs.
- The HP filter is one-sided (causal). A two-sided HP filter would repaint.
- If a bar touches both TP and SL, it is counted as SL (the pessimistic reading). A gap through a level fills at the open.

## How it was checked

1. **TradingView compiler.** The script was sent to TradingView's Pine compiler service: **0 errors, 0 warnings**. The same service was shown to reject deliberately broken v6 code, including local-scope `alertcondition`, a series length passed to `ta.rma`, `var bool = na`, and a float `if` condition.
2. **Math.** `verification/verify_math.py` checks three things:
   - The scalar Kalman used in Pine equals a matrix port of `hp1()` to within 4e‑11.
   - It equals the endpoint of the exact two-sided HP filter on every expanding sample: 2e‑9 at λ = 1600, 7e‑8 at λ = 400,000, and 2e‑5 in log price at the default λ ≈ 1e10.
   - The Avellaneda–Stoikov spread formula reproduces the paper's Tables 1–3 (1.49, 1.35, 3.02).
3. **Execution.** The actual `.pine` file was run in [PineTS](https://github.com/LuxAlgo/PineTS), an open-source Pine runtime, on 3000 synthetic bars under three configurations. The synthetic bars include trends, gaps, a bubble and a crash. An independent line-by-line Python mirror (`verification/mirror.py`) was run on the same bars.
   - Every BUY, SELL, filtered signal, TP hit, SL hit and exit matched on every bar.
   - Once the mirror copies two PineTS runtime details (its `ta.rma` reads the first `na` as 0, and it rounds to 10 decimals), every price and value matches too, to 1e‑9.
   - The runs exercised gap fills, bars that touched both TP and SL, exit-and-reverse on the same bar, the TP floor, and both filters in both modes.

Re-run everything with `verification/run_all.sh`. It needs Python with numpy and scipy, plus Node 18+.

A quick run on long daily FRED series (Nasdaq Composite, WTI, USD/JPY, EUR/USD; closes only, no costs) was used to sanity-check the defaults, not to optimise them. BUY signals taken while STLFSI4 was above 1.0 did worse than those outside stress on three of the four series. Oil went the other way on only 7 trades. The boom filter fires only in bubble-like moves, and in the Nasdaq it peaked the day before the March 2000 top. These are small samples; treat them as indicative only.

## Limitations

- This is research turned into rules, not financial advice. Test it on your market and timeframe, with your costs, before trading it.
- Avellaneda–Stoikov is a market-making model. Using its exit quote as a trend trade's take profit is an adaptation, and γ and k come from the paper's simulation, not from your market's order flow.
- The NBER paper describes a crisis and the policy response to it; it gives no trading rule. The stress filter is a translation of its finding (funding stress = scramble for dollars) into a regime gate.
- One-sided HP trends keep extrapolating after sharp reversals (the end-point problem Hamilton, 2017, criticises). Early recoveries after a crash can therefore read as boom-zone.
- STLFSI4 is weekly. Historical bars may use a reading a few days before it was officially published; live bars use only published values.
