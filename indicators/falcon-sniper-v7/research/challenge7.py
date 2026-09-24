"""$30 -> $500 in N trades with costs: exact DP and historical replay, launch-pad sizing."""
import functools, math, statistics, sys
from common import PIPS, bars
from sim import run_sequential
from strategies import STRATS, SPREAD
def last(sym): return bars(sym, 3600)[-1][4]
def spec(sym, lev):
    eu, gu, au, uj, uc = last("EURUSD"), last("GBPUSD"), last("AUDUSD"), last("USDJPY"), last("USDCAD")
    px = last(sym)
    t = {"EURUSD": (10, 1e5 * eu), "GBPUSD": (10, 1e5 * gu), "AUDUSD": (10, 1e5 * au), "NZDUSD": (10, 1e5 * px),
         "USDJPY": (1000 / uj, 1e5), "USDCAD": (10 / uc, 1e5), "EURJPY": (1000 / uj, 1e5 * eu), "GBPJPY": (1000 / uj, 1e5 * gu),
         "GBPAUD": (10 * au, 1e5 * gu), "XAUUSD": (10, 100 * px), "XAGUSD": (50, 5000 * px)}[sym]
    return t[0], t[1] / lev
def launchpad(B, s, V, M, goal, W, so):
    per = s * V + so * M
    maxq = math.floor(B / per * 100 + 1e-9) / 100
    pad = goal / (1 + W * V / per)
    aim = goal if B >= pad else min(2 * pad, goal)
    L = max(math.ceil((aim - B) / (W * V) * 100 - 1e-9) / 100, 0.01)
    L = min(L, maxq)
    return L if L >= 0.01 else 0.0
def replay(trades, sym, lev, so=0.5, start=30.0, goal=500.0, n=3, W=300.0):
    V, M = spec(sym, lev); res = []
    for s0 in range(len(trades) - n + 1):
        B = start
        for j in range(n):
            t = trades[s0 + j]; L = launchpad(B, t["riskPips"], V, M, goal, W, so)
            if L == 0: break
            B += L * V * t["pips"]
            if B >= goal: break
        res.append(B)
    return len(res), sum(b >= goal for b in res), sum(b < 5 for b in res)
def dp(p, q, win, loss, be, V, M, so, start=30.0, goal=500.0, n=3):
    @functools.lru_cache(maxsize=None)
    def best(k, cents):
        B = cents / 100
        if B >= goal: return 1.0
        if k == 0: return 0.0
        maxq = math.floor(B / (loss * V + so * M) * 100 + 1e-9)
        top = 0.0
        for q100 in range(1, maxq + 1):
            L = q100 / 100
            v = p * best(k - 1, round((B + L * V * win) * 100)) + q * best(k - 1, round((B + L * V * be) * 100)) \
                + (1 - p - q) * best(k - 1, round((B - L * V * loss) * 100))
            top = max(top, v)
        return top
    return best(n, round(start * 100))
if __name__ == "__main__":
    so = float(sys.argv[1]) if len(sys.argv) > 1 else 0.5
    swap = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5
    print(f"stop-out {so:.0%}, swap {swap} pips/night, spread per instrument, H4 sweep, launch-pad sizing")
    for sym in PIPS:
        ts = run_sequential(bars(sym, 14400), STRATS["A sweep reversal"](sym, 14400), PIPS[sym], spread=SPREAD[sym], swap=swap)
        if len(ts) < 10: print(sym, "too few trades", len(ts)); continue
        tp = [t for t in ts if t["why"] == "tp"]; be = [t for t in ts if t["why"] == "be"]; sl = [t for t in ts if t["why"] == "sl"]
        p, q = len(tp) / len(ts), len(be) / len(ts)
        win = statistics.mean(t["pips"] for t in tp) if tp else 300; bep = statistics.mean(t["pips"] for t in be) if be else 0
        loss = statistics.median(t["riskPips"] for t in ts)
        row = []
        for lev in (500, 1000, 3000):
            V, M = spec(sym, lev)
            n, ok, bust = replay(ts, sym, lev, so)
            row.append(f"1:{lev} DP {100*dp(p, q, win, loss, bep, V, M, so):4.1f}% replay {100*ok/n:4.1f}% bust {100*bust/n:3.0f}%")
        print(f"{sym} n={len(ts):3d} p300={p:.3f} pBE={q:.3f} stop={loss:.0f}p | " + " | ".join(row))
