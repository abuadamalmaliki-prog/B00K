"""Maximum probability of reaching a balance goal within N trades, for a strategy's empirical
R-distribution (net of costs), with the risk fraction chosen optimally before every trade.
Balance grid is log-spaced; risk fractions up to 100% of balance (all-in)."""
import math, pickle, functools
def r_bins(Rs, nb=40):
    Rs = sorted(Rs); n = len(Rs); out = []
    for k in range(nb):
        chunk = Rs[k * n // nb:(k + 1) * n // nb]
        if chunk: out.append((sum(chunk) / len(chunk), len(chunk) / n))
    return out
def max_p(Rs, N, start=30.0, goal=5000.0, pts=320, fracs=(0.02, 0.05, 0.1, 0.2, 0.3, 0.45, 0.6, 0.8, 1.0)):
    bins = r_bins(Rs)
    lo, hi = math.log(1.0), math.log(goal)
    grid = [math.exp(lo + (hi - lo) * i / (pts - 1)) for i in range(pts)]
    def idx(B):
        if B >= goal: return pts          # goal state
        if B < 1.0: return -1             # ruined (< $1: cannot open a 0.01 lot sensibly)
        return min(pts - 1, int((math.log(B) - lo) / (hi - lo) * (pts - 1)))   # floor = conservative
    V = [0.0] * pts
    for k in range(N):
        W = []
        for B in grid:
            best = 0.0
            for f in fracs:
                v = 0.0
                for r, w in bins:
                    j = idx(B * (1 + f * r))
                    v += w * (1.0 if j == pts else 0.0 if j < 0 else V[j])
                best = max(best, v)
            W.append(best)
        V = W
    return V[idx(start)]
if __name__ == "__main__":
    import sys
    trades = pickle.load(open(sys.argv[1], "rb"))
    Rs = [t["R"] for t in trades]
    m = sum(Rs) / len(Rs); win = sum(r > 0 for r in Rs) / len(Rs)
    print(f"{sys.argv[1]}: n={len(Rs)} win={100*win:.1f}% avgR={m:+.3f}")
    for N in (10, 20, 40, 60):
        print(f"  N={N:3d} trades: max P($5,000)={100*max_p(Rs, N):.3f}%  max P($500)={100*max_p(Rs, N, goal=500):.2f}%  max P($60)={100*max_p(Rs, N, goal=60):.1f}%")
