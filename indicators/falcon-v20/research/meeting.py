"""Team meeting: one comparison table of every candidate strategy (net of costs)."""
import glob, math, pickle, statistics, sys, os
from goaldp import max_p
def load_all():
    cands = {}
    for path in sorted(glob.glob("agent*/*.pkl")):
        if os.path.basename(path) in ("all_results.pkl", "summary.pkl"): continue
        try:
            t = pickle.load(open(path, "rb"))
        except Exception:
            continue
        if isinstance(t, list) and t and isinstance(t[0], dict) and "R" in t[0]:
            cands[path] = t
    # our own V7 sweep (H4, all-in 300 pips, BE at +150, costs)
    sys.path.insert(0, "../v7")
    from strategies import STRATS, SPREAD
    from sim import run_sequential
    from common import PIPS, bars
    v7 = []
    for sym in PIPS:
        for t in run_sequential(bars(sym, 14400), STRATS["A sweep reversal"](sym, 14400), PIPS[sym], spread=SPREAD[sym], swap=0.5):
            t["sym"] = sym; v7.append(t)
    cands["v7/sweep_H4_300pips"] = v7
    return cands
def weeks(trades):
    ts = [t["time"] for t in trades]
    return max(1.0, (max(ts) - min(ts)) / (7 * 86400))
if __name__ == "__main__":
    cands = load_all()
    rows = []
    for name, tr in cands.items():
        Rs = [t["R"] for t in tr]; n = len(Rs)
        m = sum(Rs) / n; se = statistics.pstdev(Rs) / math.sqrt(n); win = 100 * sum(r > 0 for r in Rs) / n
        rows.append((name, n, win, m, se, n / weeks(tr), max_p(Rs, 40, goal=60), max_p(Rs, 40, goal=500), max_p(Rs, 40)))
    rows.sort(key=lambda r: -r[8])
    print(f"{'candidate':46s} {'n':>5s} {'win%':>6s} {'netR':>8s} {'±SE':>6s} {'/wk':>6s} {'P$60':>6s} {'P$500':>6s} {'P$5000':>7s}")
    for r in rows:
        print(f"{r[0]:46s} {r[1]:5d} {r[2]:6.1f} {r[3]:+8.3f} {r[4]:6.3f} {r[5]:6.1f} {100*r[6]:5.1f}% {100*r[7]:5.2f}% {100*r[8]:6.3f}%")
    pickle.dump(rows, open("meeting_rows.pkl", "wb"))
