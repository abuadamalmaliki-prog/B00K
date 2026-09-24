# V3 research harness

Line-for-line Python mirror of Falcon Sniper V3's signal and trade logic, used to make every decision in the V3 README.

```
python3 fetch.py          # ~2 years of H1 (and 60 days of M15) for 11 instruments into data/
python3 mgmt.py '[("V3 defaults", dict(partials=False, beAfterTp1=True, trailTp2=False, tp1Pips=150, tp2Pips=200, noReverse=True))]'
python3 challenge.py 1000 # $30 -> $500 in 3 trades, historical replay at 1:1000 leverage
python3 dp.py             # exact optimal sizing (dynamic programming) per instrument
```

| File | What it does |
|---|---|
| `engine.py` | Bar-by-bar mirror of the indicator (swings, sweeps, zones, triggers, kill zones, trade management) |
| `common.py` | Data loading, pip sizes, path analysis (did price reach +300 before the stop?) |
| `pool.py` | Builds the trade pool with entry features for the reverse-engineering study |
| `mgmt.py` | Seen vs unseen instruments × first vs second half, for any set of settings |
| `challenge.py` | Historical replay of the goal challenge with real lot steps, pip values and margin |
| `dp.py` | Exact dynamic-programming optimum for reaching a goal within N trades |

Results are before spread, commission and slippage.
