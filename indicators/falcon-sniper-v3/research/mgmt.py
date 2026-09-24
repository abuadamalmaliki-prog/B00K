import sys
from common import *
SEEN = ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "XAUUSD"]
UNSEEN = ["NZDUSD", "USDCAD", "GBPAUD", "EURJPY", "GBPJPY", "XAGUSD"]
def evaluate(over, syms, tfs):
    res = {}
    for tf in tfs:
        for h in (0, 1): res[(tf, h)] = []
        for sym in syms:
            rows, tr = run(sym, tf, **over)
            mid = rows[len(rows) // 2][0]
            for t in tr: res[(tf, t["time"] >= mid)].append(t)
    return res
def line(ts):
    if not ts: return "n=0".ljust(34)
    n = len(ts); gw = sum(t["r"] for t in ts if t["r"] > 0); gl = -sum(t["r"] for t in ts if t["r"] < 0)
    return f"n={n:4d} avgR={sum(t['r'] for t in ts)/n:+.3f} PF={gw/gl if gl else 9:4.2f}"
if __name__ == '__main__':
  V = eval(sys.argv[1])
  for name, over in V:
      for label, syms in (("seen5", SEEN), ("UNSEEN6", UNSEEN)):
          r = evaluate(over, syms, (14400, 3600))
          print(f"{name:24s} {label:7s} H4: {line(r[(14400,0)])} | {line(r[(14400,1)])}   H1: {line(r[(3600,0)])} | {line(r[(3600,1)])}")
