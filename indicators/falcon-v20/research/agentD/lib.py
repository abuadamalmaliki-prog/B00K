"""agentD shared helpers: indicators, period keys, setup construction, protocol evaluation.
Run from the v15 directory. Only closed-bar information up to the signal bar i is used."""
import sys, os, math, random, statistics
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import timedelta
from common import PIPS, bars
from sim import ny
from sim15 import SPREAD, SEEN, UNSEEN, trade, stats

ALL = SEEN + UNSEEN
WARM = 50          # bars skipped at the start (ATR / level warm-up)
BUF = 0.10         # stop buffer beyond structure, x ATR
MINR = 0.50        # minimum stop distance from the close, x ATR
MAXB = {3600: 72, 14400: 18}   # uniform time exit: 72 hours

_C = {}
def arrays(sym, tf):
    k = (sym, tf)
    if k not in _C:
        rows = bars(sym, tf)
        O = [r[1] for r in rows]; H = [r[2] for r in rows]; L = [r[3] for r in rows]; C = [r[4] for r in rows]
        A, v, prev = [], None, None          # Wilder ATR(14), value at bar i uses bars <= i
        for o, h, l, c in zip(O, H, L, C):
            tr = h - l if prev is None else max(h - l, abs(h - prev), abs(l - prev))
            v = tr if v is None else v + (tr - v) / 14
            A.append(v); prev = c
        _C[k] = dict(rows=rows, O=O, H=H, L=L, C=C, A=A, n=len(rows))
    return _C[k]

def pivots(sym, tf, n):
    """Fractal pivots: returns (ph, pl) lists of (confirm_bar, pivot_bar, price).
    Pivot high at k: H[k] > max(H[k-n:k]) and H[k] >= max(H[k+1:k+n+1]); known at bar k+n."""
    key = ("piv", sym, tf, n)
    if key not in _C:
        a = arrays(sym, tf); H, L, N = a["H"], a["L"], a["n"]
        ph, pl = [], []
        for k in range(n, N - n):
            if H[k] > max(H[k - n:k]) and H[k] >= max(H[k + 1:k + n + 1]): ph.append((k + n, k, H[k]))
            if L[k] < min(L[k - n:k]) and L[k] <= min(L[k + 1:k + n + 1]): pl.append((k + n, k, L[k]))
        _C[key] = (ph, pl)
    return _C[key]

def daykey(t):
    """NY trading day (17:00 New York rollover): shift +7h so Sun 17:00 -> Mon 00:00."""
    return (ny(t) + timedelta(hours=7)).date()

def weekkey(t):
    d = daykey(t); y, w, _ = d.isocalendar(); return (y, w)

def period_levels(sym, keyf):
    """{period_key: (prev_open... ) } -> dict key -> (H, L, C) of the PREVIOUS completed period, built from H1 bars."""
    ck = ("lvl", sym, keyf.__name__)
    if ck not in _C:
        rows = bars(sym, 3600)
        per, order = {}, []
        for t, o, h, l, c, v in rows:
            k = keyf(t)
            if k not in per: per[k] = [o, h, l, c, 0]; order.append(k)
            else:
                p = per[k]; p[1] = max(p[1], h); p[2] = min(p[2], l); p[3] = c
            per[k][4] += 1
        prev = {}
        for a, b in zip(order, order[1:]):
            prev[b] = tuple(per[a])     # (O,H,L,C,nbars) of the completed period before b
        _C[ck] = prev
    return _C[ck]

def entry_px(sym, C, i, d):
    return C[i] + SPREAD[sym] * PIPS[sym] if d == 1 else C[i]

def mk(sym, a, i, d, struct, target, tf, level_tp=None):
    """Build a setup at bar i. struct = protective structure price (stop goes BUF*ATR beyond it,
    at least MINR*ATR from the close). Invalid if the close is already beyond the structure.
    target: ('R', k) -> k x risk measured from the actual fill; ('L', price) -> fixed level."""
    C, A = a["C"], a["A"]
    c, at = C[i], A[i]
    if d * (c - struct) <= 0: return None
    sl = struct - d * BUF * at
    if d * (c - sl) < MINR * at: sl = c - d * MINR * at
    e = entry_px(sym, C, i, d)
    risk = d * (e - sl)
    if risk <= 0: return None
    if target[0] == "R": tp = e + d * target[1] * risk
    else:
        tp = target[1]
        if d * (tp - e) <= 0: return None
    return (i, d, sl, tp, MAXB[tf])

# ---------------------------------------------------------------- protocol
def run_seq(rows, setups, pip, spread, swap=None):
    """Identical to sim15.run_sequential (cooldown 0) but keeps the setup on each trade."""
    kw = {} if swap is None else {"swap": swap}
    out, busy = [], -1
    for st in sorted(setups, key=lambda x: x[0]):
        if st[0] < busy: continue
        tr = trade(rows, st, pip, spread, **kw)
        if tr is None: continue
        tr["setup"] = st
        out.append(tr); busy = tr["exit_i"]
    return out

def evaluate(gen, tf, syms=ALL, gross=False, setups=None):
    """-> {(group, half): trades}; same split as sim15.evaluate."""
    res = {(g, h): [] for g in ("seen", "unseen") for h in (0, 1)}
    for sym in syms:
        grp = "seen" if sym in SEEN else "unseen"
        rows = bars(sym, tf)
        st = setups[sym] if setups is not None else gen(sym, tf)
        trs = run_seq(rows, st, PIPS[sym], 0.0 if gross else SPREAD[sym], 0.0 if gross else None)
        mid = rows[len(rows) // 2][0]
        for t in trs:
            t["sym"] = sym
            res[(grp, int(t["time"] >= mid))].append(t)
    return res

def flat(res, grp=None):
    return [t for (g, h), v in res.items() if grp is None or g == grp for t in v]

def score(res):
    """Pre-registered selection score, SEEN only: min of the two SEEN half avg R (needs n>=30 each)."""
    s1, s2 = stats(res[("seen", 0)]), stats(res[("seen", 1)])
    if s1["n"] < 30 or s2["n"] < 30: return -9.0
    return min(s1["avgR"], s2["avgR"])

def weeks(sym):
    r = bars(sym, 3600); return (r[-1][0] - r[0][0]) / 604800

def tpw(trs):
    by = {}
    for t in trs: by[t["sym"]] = by.get(t["sym"], 0) + 1
    return sum(n / weeks(s) for s, n in by.items())

def hold(trs):
    return statistics.mean((t["exit_time"] - t["time"]) / 3600 for t in trs) if trs else 0.0

def control(setups_by_sym, tf, seeds=10):
    """Random-entry control: same number of setups per instrument, uniformly random bar and random
    direction, identical exit geometry (stop and target distances in ATR units of the original setup,
    same time exit), same costs and one-position-at-a-time rule. Pooled over `seeds`."""
    pooled = []
    for seed in range(seeds):
        rng = random.Random(1000 + seed)
        for sym in ALL:
            a = arrays(sym, tf); C, A, n = a["C"], a["A"], a["n"]
            rs = []
            for st in setups_by_sym[sym]:
                i, d, sl, tp = st[:4]
                e = entry_px(sym, C, i, d)
                sk, tk = abs(C[i] - sl) / A[i], abs(tp - e) / A[i]
                j = rng.randrange(WARM, n - 2); dd = rng.choice((1, -1))
                ej = entry_px(sym, C, j, dd)
                rs.append((j, dd, C[j] - dd * sk * A[j], ej + dd * tk * A[j]) + tuple(st[4:]))
            for t in run_seq(a["rows"], rs, PIPS[sym], SPREAD[sym]):
                t["sym"] = sym; pooled.append(t)
    return pooled
