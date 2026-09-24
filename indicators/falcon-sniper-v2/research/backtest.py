"""Reproduce the README results table.

    python3 fetch.py      # downloads ~2 years of H1 data (and more) into data/
    python3 backtest.py   # runs the Falcon Sniper V2 mirror with default settings

H4 bars are built from H1 data. Results are before spread, commission and slippage.
"""
import os, statistics
from engine import Engine, DEFAULTS, load, resample

PIPS = {"EURUSD": 0.0001, "GBPUSD": 0.0001, "AUDUSD": 0.0001, "USDJPY": 0.01, "XAUUSD": 0.1}
HTF = {3600: 14400, 14400: 86400}  # the indicator's Auto HTF for H1 / H4 charts


def run(sym, tf, **over):
    P = dict(DEFAULTS); P.update(over); P["_htf_secs"] = HTF[tf]
    h1 = load(f"data/{sym}_1h.csv")
    rows = h1 if tf == 3600 else resample(h1, tf)
    trades, _, _ = Engine(P).run(rows, resample(rows, HTF[tf]), PIPS[sym], tf)
    return rows, trades


def summary(trades):
    n = len(trades)
    gw = sum(t["r"] for t in trades if t["r"] > 0)
    gl = -sum(t["r"] for t in trades if t["r"] < 0)
    pct = lambda k: 100 * sum(t["hit"][k] for t in trades) / n
    return dict(n=n, win=100 * sum(t["r"] > 0 for t in trades) / n, tp1=pct(0), tp2=pct(1), tp3=pct(2),
                avgR=sum(t["r"] for t in trades) / n, pf=gw / gl if gl else float("inf"),
                sl=statistics.median(t["riskPips"] for t in trades))


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    for tf, name in ((14400, "H4"), (3600, "H1")):
        pooled = []
        for sym in PIPS:
            rows, tr = run(sym, tf)
            pooled += tr
            s = summary(tr)
            months = (rows[-1][0] - rows[0][0]) / (86400 * 30.4)
            print(f"{name} {sym}  trades/mo {s['n'] / months:4.1f}  win {s['win']:4.1f}%  TP1 {s['tp1']:4.1f}%  "
                  f"TP2 {s['tp2']:4.1f}%  TP3 {s['tp3']:4.1f}%  avgR {s['avgR']:+.2f}  PF {s['pf']:.2f}  median SL {s['sl']:.0f}p")
        s = summary(pooled)
        print(f"{name} ALL     trades {s['n']}  win {s['win']:.1f}%  avgR {s['avgR']:+.3f}  PF {s['pf']:.2f}\n")
