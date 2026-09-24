"""V20 plan quant for C3 Trend-Sweep: opportunities per month, exact DP policy/probability tables
(as a function of balance/goal and trades left), and milestone probabilities."""
import math, pickle, random, statistics
from goaldp import r_bins
from challenge15 import Book, windows
C3 = pickle.load(open("combo_C3.pkl", "rb"))
Rs = [t["R"] for t in C3]
FR = (0.0, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.45, 0.6, 0.8, 1.0)
def dp_tables(Rs, nmax=20, pts=60, xmin=1e-3):
    """V[n][j], F[n][j]: max P(reach goal) and best risk fraction with n trades left at x_j = B/goal."""
    bins = r_bins(Rs)
    lo, hi = math.log(xmin), 0.0
    xs = [math.exp(lo + (hi - lo) * j / (pts - 1)) for j in range(pts)]
    def val(Vn, x):
        if x >= 1.0 - 1e-12: return 1.0
        if x < xmin: return 0.0
        u = (math.log(x) - lo) / (hi - lo) * (pts - 1); j = int(u)
        if j >= pts - 1: return Vn[-1]
        return Vn[j]          # floor: conservative
    V = [[0.0] * pts]; F = [[0.0] * pts]
    for n in range(1, nmax + 1):
        v, f = [], []
        for x in xs:
            best, bf = -1, 0.0
            for fr in FR:
                p = sum(w * val(V[-1], x * (1 + fr * r)) for r, w in bins)
                if p > best + 1e-12: best, bf = p, fr
            v.append(best); f.append(bf)
        V.append(v); F.append(f)
    return xs, V, F
if __name__ == "__main__":
    # 1) opportunities in 21-day windows (one position at a time across 11 instruments)
    import combos
    from common import PIPS
    by = {sym: combos.c3(sym, 14400) for sym in PIPS}
    print("C3 setups per symbol:", {k: len(v) for k, v in by.items()})
    b = Book(by, tf=14400)
    w = windows(days=21)
    res = [b.run_window(a, e, 0.001, 1e9, 0.0, 1.0, 30.0) for a, e in w]
    trades = sorted(k for _, k in res)
    print(f"C3 trades available per 21-day window (one at a time): median {trades[len(trades)//2]}, 10th pct {trades[len(trades)//10]}, 90th pct {trades[9*len(trades)//10]}")
    # 2) DP tables
    xs, V, F = dp_tables(Rs)
    x0 = 30 / 5000
    def lookup(T, n, x):
        j = max(0, min(len(xs) - 1, int((math.log(x) - math.log(xs[0])) / (math.log(xs[-1]) - math.log(xs[0])) * (len(xs) - 1))))
        return T[n][j]
    for n in (5, 8, 10, 12, 15, 20):
        print(f"n={n:2d} trades left, $30 -> $5,000: max P={100*lookup(V, n, x0):.3f}%  first-trade risk {100*lookup(F, n, x0):.0f}% of balance")
    pickle.dump((xs, V, F), open("c3_dp.pkl", "wb"))
    # 3) Monte Carlo of the DP policy: probability of EVER reaching each milestone before the deadline
    random.seed(1)
    N = trades[len(trades) // 2]
    mil = [60, 150, 500, 1500, 5000]
    hits = {m: 0 for m in mil}; sims = 200000; busted = 0
    for _ in range(sims):
        B, top = 30.0, 30.0
        for k in range(N, 0, -1):
            x = B / 5000
            if x >= 1 or B < 1: break
            fr = lookup(F, min(k, 20), x)
            if fr == 0: break
            B *= 1 + fr * random.choice(Rs)
            top = max(top, B)
        for m in mil:
            if top >= m: hits[m] += 1
        busted += B < 3
    print(f"DP policy, {N} trades, {sims} simulations: " + " ".join(f"P(ever ${m})={100*hits[m]/sims:.2f}%" for m in mil) + f" | ends below $3: {100*busted/sims:.1f}%")
