# Trading indicators

| Version | Folder | Status |
|---|---|---|
| **Frostbite v2** | [`frostbite/`](frostbite) | **Current.** XAUUSD M5 only. Smooth Kalman trend line, BUY/SELL tags, SL/TP1/TP2 lines with price tags. Two tested setups (Icicle, Avalanche), about 1.6–2.3 signals a day. |
| V20 | [`falcon-v20/`](falcon-v20) | TradingView only (Android), manual MT5 orders. Scans 11 symbols on H4 with the C3 Trend-Sweep strategy, sizes each trade for the highest probability of the goal by the deadline, one alert with the MT5 order. |
| V7 | [`falcon-sniper-v7/`](falcon-sniper-v7) | MT5 Expert Advisor for JustMarkets execution plus TradingView indicator. Costs included, exact goal sizing, parity-verified. |
| V3 | [`falcon-sniper-v3/`](falcon-sniper-v3) | 300-pip runner, challenge planner (sized on gross wins, ignores costs) |
| V2 | [`falcon-sniper-v2/`](falcon-sniper-v2) | First liquidity-sweep sniper (reversal exits cut runners short) |
| V1 | [`falcon-confluence-pro/`](falcon-confluence-pro) | Six-factor confluence indicator |

Start with the [Frostbite README](frostbite/README.md).
