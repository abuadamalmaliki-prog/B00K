import json, math, sys
# Usage: python3 compare.py <config letter>  (reads pine_X.json and mirror_X.json)
def isna(x): return x is None or (isinstance(x, float) and math.isnan(x))
def as_bool(v): return (not isna(v)) and v not in (False, 0)
def close(a, b, tol):
    if isna(a) and isna(b): return True
    if isna(a) or isna(b): return False
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))
t = sys.argv[1]
P = json.load(open(f"pine_{t}.json")); M = json.load(open(f"mirror_{t}.json"))
mp, ms = M["plots"], M["stats"]
N = len(mp["BUY"])
pairs_bool = [("BUY","BUY"),("SELL","SELL"),("BUY removed by filter","BUY removed"),("SELL removed by filter","SELL removed")]
pairs_num = [("Entry","Entry",1e-9),("TP","TP",1e-9),("SL","SL",1e-9),("TP hit","TP hit",1e-9),
             ("SL hit","SL hit",1e-9),("Signal exit","Signal exit",1e-9),("dbg_gap","gap",1e-7),("dbg_conv","conv",1e-9)]
bad = 0
bad_events = 0
for pk, mk in pairs_bool:
    diff = [i for i in range(N) if as_bool(P[pk][i]) != bool(mp[mk][i])]
    cnt_p = sum(as_bool(v) for v in P[pk]); cnt_m = sum(bool(v) for v in mp[mk])
    print(f"{pk:<24} pine={cnt_p:<4} mirror={cnt_m:<4} mismatched bars={len(diff)} {diff[:5]}")
    bad += len(diff); bad_events += len(diff)
max_rel = 0.0
for pk, mk, tol in pairs_num:
    diff = [i for i in range(N) if not close(P[pk][i], mp[mk][i], tol)]
    for i in diff:
        a, b = P[pk][i], mp[mk][i]
        if not isna(a) and not isna(b):
            max_rel = max(max_rel, abs(a - b) / max(1.0, abs(a), abs(b)))
        else:
            max_rel = float("inf")
    print(f"{pk:<24} mismatched bars={len(diff)} {[(i, P[pk][i], mp[mk][i]) for i in diff[:3]]}")
    bad += len(diff)
for pk, mk in (("dbg_nTrades","nTrades"),("dbg_nTP","nTP"),("dbg_nSL","nSL"),("dbg_nExit","nExit"),("dbg_sumR","sumR")):
    ok = close(P[pk][-1], ms[mk], 1e-9)
    print(f"final {mk:<8} pine={P[pk][-1]} mirror={ms[mk]} {'OK' if ok else 'MISMATCH'}")
    bad += (not ok)
    if mk != "sumR":
        bad_events += (not ok)
print(f"== config {t}: events {'MATCH' if bad_events == 0 else f'{bad_events} MISMATCHES'}; "
      f"events + values {'MATCH' if bad == 0 else f'{bad} mismatches at 1e-9, max relative deviation {max_rel:.1e}'}")
