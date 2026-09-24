# V7 research harness

Everything behind the V7 README, reproducible. Results are **net of spread and swap** unless stated.

```
python3 fetch.py                         # ~2 years of H1 (+60 days M15) for 11 instruments into data/
python3 bakeoff.py "(14400, 3600)"       # 6 strategy families incl. a random-entry control, seen/unseen x halves
python3 challenge7.py 0.5 0.5            # $30 -> $500 in 3 trades: exact DP + replay at 1:500 / 1:1000 / 1:3000
python3 parity.py                        # EA engine & trade replay vs research engine; Pine swap counter vs research
```

| File | Purpose |
|---|---|
| `engine.py` | Bar-by-bar signal engine (sweep reversal); `raw=True` returns every setup |
| `sim.py` | Trade simulator with the cost model: longs fill at the ask, shorts stop/fill on the ask, swap per 17:00 NY rollover (Wed x3), stop-first, gapped stops at the open |
| `strategies.py` | Setup generators: sweep reversal, London breakout, Donchian 55/10, daily-trend pullback, NR7, random control; assumed JustMarkets-Standard-like spreads |
| `bakeoff.py` | Evaluates every family on seen (5) / unseen (6) instruments x first / second half |
| `challenge7.py` | Goal odds: exact dynamic programme and historical replay with lot steps, pip values, margin and stop-out |
| `mq_mirror.py` | Line-by-line Python transliteration of the EA's `EvaluateSetups()` |
| `parity.py` | Proves the EA logic equals the research engine |

Spreads in `strategies.py` are assumptions for a standard (non-raw) account. Check yours in MT5 Market Watch.
