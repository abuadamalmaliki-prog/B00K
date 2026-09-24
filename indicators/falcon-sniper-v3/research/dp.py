"""Exact dynamic programme: maximise P(balance >= goal within N trades).
Per trade the outcome is +target pips (p), breakeven 0 (q) or -stop pips (rest).
Lots are multiples of 0.01, capped so the stop fills before a 50% margin stop-out."""
import functools, math
from challenge import *
def solve(p, q, stop, V, M, start=30.0, goal=500.0, n=3, target=300):
    @functools.lru_cache(maxsize=None)
    def best(k, cents):
        B = cents / 100
        if B >= goal: return 1.0, 0.0
        if k == 0: return 0.0, 0.0
        maxq = math.floor(B / (stop * V + 0.5 * M) * 100 + 1e-9)
        top, arg = 0.0, 0.0
        for q100 in range(1, maxq + 1):
            L = q100 / 100
            win = round((B + L * V * target) * 100)
            loss = round((B - L * V * stop) * 100)
            val = p * best(k - 1, win)[0] + q * best(k - 1, cents)[0] + (1 - p - q) * best(k - 1, loss)[0]
            if val > top + 1e-12: top, arg = val, L
        return top, arg
    return best(n, round(start * 100)), best
if __name__ == "__main__":
    for sym, tf in (("EURUSD", 14400), ("GBPUSD", 14400), ("AUDUSD", 14400), ("USDJPY", 14400), ("USDCAD", 14400)):
        rows, tr = run(sym, tf, **V3)
        n = len(tr); p = sum(t["exit"] == "tp3" for t in tr) / n; q = sum(t["exit"] == "stop" and abs(t["pips"]) < 1 for t in tr) / n
        stop = statistics.median(t["riskPips"] for t in tr)
        for lev in (500, 1000):
            V, M = pip_value_and_margin(sym, lev)
            (prob, L1), best = solve(p, q, stop, V, M)
            ceiling = 30 / 500
            print(f"{sym} H4 1:{lev}  p(300)={p:.3f} p(BE)={q:.3f} stop={stop:.0f}p | optimal P={100*prob:.1f}% | trade-1 lots={L1:.2f} (risk ${L1*V*stop:.2f} = {100*L1*V*stop/30:.0f}%) | zero-edge ceiling {100*ceiling:.0f}%")
