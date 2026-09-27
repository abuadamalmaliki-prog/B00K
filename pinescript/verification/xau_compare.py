"""Compare the PineTS run of the indicator with xau_mirror.py, bar by bar.
Usage: python3 xau_compare.py <slice name> <timeframe minutes>
"""
import json, math, sys
from xau_mirror import run
name, tf = sys.argv[1], float(sys.argv[2])
c = json.load(open(f'xau_{name}.json'))
P = json.load(open(f'xau_pine_{name}.json'))
M, st = run(c, 3.0, 1.0, tf_min=tf)
def na(v): return v is None or (isinstance(v, float) and math.isnan(v))
def same(a, b, tol=1e-9):
    if na(a) and na(b): return True
    if na(a) or na(b): return False
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))
bad = 0
for pk, mk in (('dbg_plan','plan'),('dbg_buy','buy'),('dbg_sell','sell'),('dbg_tp','tp'),('dbg_sl','sl'),('dbg_time','time')):
    d = [i for i in range(len(c)) if bool(P[pk][i]) != bool(M[mk][i])]
    print(f"{mk:<5} pine={sum(1 for v in P[pk] if v):<4} mirror={sum(M[mk]):<4} mismatched bars={len(d)} {d[:5]}")
    bad += len(d)
for pk, mk in (('Entry','entry'),('TP','tpPx'),('SL','slPx'),('dbg_exitPx','exitPx'),('dbg_exitR','exitR')):
    d = [i for i in range(len(c)) if not same(P[pk][i], M[mk][i])]
    print(f"{mk:<7} mismatched bars={len(d)} {[(i, P[pk][i], M[mk][i]) for i in d[:3]]}")
    bad += len(d)
for pk, mk in (('dbg_nTrades','nTrades'),('dbg_sumR','sumR'),('dbg_maxDD','maxDD')):
    ok = same(P[pk][-1], st[mk]); bad += not ok
    print(f"final {mk:<8} pine={P[pk][-1]} mirror={st[mk]} {'OK' if ok else 'MISMATCH'}")
print(f"== {name}: {'ALL MATCH' if bad == 0 else str(bad) + ' MISMATCHES'}")
