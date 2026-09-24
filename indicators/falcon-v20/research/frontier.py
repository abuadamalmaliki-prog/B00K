"""Target / probability / bust frontier for a strategy's setups over all 5-day windows.
usage: python3 frontier.py path/to/trades.pkl [half]   (half: all | 1 | 2)
The pickle is a list of trade dicts with 'sym' and 'setup' keys (from sim15.trade)."""
import pickle, sys
from challenge15 import Book, windows
from common import bars
def load_setups(path):
    trades = pickle.load(open(path, "rb"))
    by = {}
    for t in trades:
        by.setdefault(t["sym"], []).append(tuple(t["setup"]))
    return {k: sorted(set(v)) for k, v in by.items()}
def frontier(setups, half="all", fs=(0.02, 0.05, 0.10, 0.20, 0.35, 0.5), targets=(33, 36, 39, 45, 60, 90, 150), floor=0.0):
    b = Book(setups)
    w = windows()
    mid = bars("EURUSD", 3600)[len(bars("EURUSD", 3600)) // 2][0]
    if half == "1": w = [x for x in w if x[1] <= mid]
    if half == "2": w = [x for x in w if x[0] >= mid]
    print(f"{len(w)} windows ({half})")
    rows = []
    for T in targets:
        best = None
        line = f"target ${T:>4}: "
        for f in fs:
            r = b.evaluate(f, T, floor=floor, wins=w)
            line += f"f={f:.2f} P={100*r['p_goal']:5.1f}% bust={100*r['p_bust']:4.1f}% | "
            if best is None or r["p_goal"] > best[1]["p_goal"]: best = (f, r)
        print(line)
        rows.append((T, best))
    return rows
if __name__ == "__main__":
    frontier(load_setups(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else "all")
