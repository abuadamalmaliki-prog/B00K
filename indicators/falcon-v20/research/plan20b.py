import math, pickle, random
from goaldp import r_bins, max_p
C3 = pickle.load(open("combo_C3.pkl", "rb")); Rs = [t["R"] for t in C3]
FR = (0.0, 0.02, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
def tables(Rs, nmax=12, pts=160, xmin=1e-3):
    bins = r_bins(Rs, 60)
    lo = math.log(xmin)
    xs = [math.exp(lo * (1 - j / (pts - 1))) for j in range(pts)]
    def val(Vn, x):
        if x >= 1.0 - 1e-12: return 1.0
        if x < xmin: return 0.0
        u = (math.log(x) - lo) / (-lo) * (pts - 1); j = int(u); a = u - j
        return Vn[j] if j >= pts - 1 else Vn[j] * (1 - a) + Vn[j + 1] * a     # linear in log-x
    V = [[0.0] * pts]; F = [[0.0] * pts]
    for n in range(1, nmax + 1):
        v, f = [], []
        for x in xs:
            best, bf = -1.0, 0.0
            for fr in FR:
                p = sum(w * val(V[-1], x * (1 + fr * r)) for r, w in bins)
                if p > best + 1e-12: best, bf = p, fr
            v.append(best); f.append(bf)
        V.append(v); F.append(f)
    return xs, V, F, val
xs, V, F, val = tables(Rs)
lo = math.log(xs[0])
def fpol(n, x):
    j = int(round((math.log(x) - lo) / (-lo) * (len(xs) - 1))); j = max(0, min(len(xs) - 1, j))
    return F[min(n, 12)][j]
def bold(n, x, b=1.9):
    return min(1.0, (1 - x) / (b * x)) if x > 0 else 1.0
x0 = 30 / 5000
for n in (7, 10):
    print(f"DP n={n}: P($30->$5,000) = {100*val(V[n], x0):.3f}%   (fine goaldp check: {100*max_p(Rs, n):.3f}%)")
random.seed(7)
def mc(policy, N=7, sims=400000, goal=5000.0):
    mil = [60, 150, 500, 1500, 5000]; hits = {m: 0 for m in mil}; bust = 0
    for _ in range(sims):
        B, top = 30.0, 30.0
        for k in range(N, 0, -1):
            if B >= goal or B < 1: break
            fr = policy(k, B / goal)
            if fr <= 0: break
            B *= 1 + fr * random.choice(Rs); top = max(top, B)
        for m in mil: hits[m] += top >= m
        bust += B < 3
    return {m: hits[m] / sims for m in mil}, bust / sims
for name, pol in (("DP policy", fpol), ("bold rule (one win reaches goal, else all-in)", bold)):
    h, b = mc(pol)
    print(f"{name:46s} " + " ".join(f"P(ever ${m})={100*h[m]:.2f}%" for m in h) + f" | ends < $3: {100*b:.1f}%")
pickle.dump((xs, V, F), open("c3_dp_fine.pkl", "wb"))
