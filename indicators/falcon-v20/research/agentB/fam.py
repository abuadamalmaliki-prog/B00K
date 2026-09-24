"""agentB: small-target / high-win-rate strategy families + controls.
All generators return sim15 setups (i, dir, sl_price, tp_price[, max_bars]) using closed-bar info only.
Run from the v15 directory (so `data/` and shared modules resolve)."""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import PIPS, bars
from sim import ny
import sim15
from sim15 import SPREAD, SEEN, UNSEEN, trade
from strategies import sweep as _sweep, ema
_SW = {}
def sweep(sym, tf):
    if (sym, tf) not in _SW: _SW[(sym, tf)] = _sweep(sym, tf)
    return _SW[(sym, tf)]

def atr(rows, n=14):
    out, v, prev = [], None, None
    for k, (t, o, h, l, c, _) in enumerate(rows):
        tr = h - l if prev is None else max(h - l, abs(h - prev), abs(l - prev))
        v = tr if v is None else v + (tr - v) / n
        out.append(v); prev = c
    return out

def entry_px(rows, i, d, sym):
    c = rows[i][4]
    return c + SPREAD[sym] * PIPS[sym] if d == 1 else c

def with_target(rows, sym, i, d, sl, k, max_bars=None):
    """tp at k * R where R = sim15's entry-to-stop distance (long entry at ask)."""
    e = entry_px(rows, i, d, sym)
    risk = (e - sl) if d == 1 else (sl - e)
    if risk <= 0: return None
    tp = e + d * k * risk
    return (i, d, sl, tp) if max_bars is None else (i, d, sl, tp, max_bars)

# ---------------- Family 1: sweep reversal, small targets ----------------
def f1(tf, k, tbars):
    def gen(sym, tf_):
        rows = bars(sym, tf)
        out = []
        for (i, d, sl, rp) in sweep(sym, tf):
            s = with_target(rows, sym, i, d, sl, k, tbars)
            if s: out.append(s)
        return out
    return gen, tf

# ---------------- Family 2: London-open breakout of Asian range ----------------
def _bars_until_hour(rows, i, hour):
    """max_bars so the time exit happens at the close of the last bar starting before `hour` NY
    on the entry bar's NY date (i.e. flat at `hour`)."""
    d0 = ny(rows[i][0]).date()
    for k in range(i + 1, min(len(rows), i + 30)):
        n = ny(rows[k][0])
        if n.date() != d0 or n.hour >= hour:
            return max(1, k - 1 - i)
    return None

def f2(stop_mode, tfrac, flat_hour):
    def gen(sym, tf_):
        rows, pip = bars(sym, 3600), PIPS[sym]
        out, hi, lo, cnt, taken = [], None, None, 0, True
        for i, (t, o, h, l, c, v) in enumerate(rows):
            n = ny(t); hr = n.hour
            if hr == 19:
                hi, lo, cnt, taken = h, l, 1, False
            elif hi is not None and (hr >= 20 or hr < 2):
                hi, lo, cnt = max(hi, h), min(lo, l), cnt + 1
            elif hi is not None and 2 <= hr < 6 and not taken:
                if cnt < 6 or hi <= lo: taken = True; continue
                W = hi - lo; mid = (hi + lo) / 2
                d = 1 if c > hi else -1 if c < lo else 0
                if d == 0: continue
                taken = True
                sl = (mid if stop_mode == "mid" else (lo if d == 1 else hi))
                e = entry_px(rows, i, d, sym)
                tp = e + d * tfrac * W
                mb = _bars_until_hour(rows, i, flat_hour) if flat_hour else None
                if (e - sl) * d <= 0: continue
                out.append((i, d, sl, tp) if mb is None else (i, d, sl, tp, mb))
            elif hr >= 6 and hr < 19:
                hi = None
        return out
    return gen, 3600

# ---------------- Family 3: NY session momentum pullback ----------------
def f3(k, strong, flat_hour, mom_atr=0.5):
    def gen(sym, tf_):
        rows, pip = bars(sym, 3600), PIPS[sym]
        A = atr(rows); buf = SPREAD[sym] * pip
        out = []; day = None; o8 = None; dirn = 0; pb_start = None; done = True
        for i, (t, o, h, l, c, v) in enumerate(rows):
            n = ny(t); hr = n.hour
            if n.date() != day:
                day, o8, dirn, pb_start, done = n.date(), None, 0, None, n.weekday() >= 5
            if done: continue
            if hr == 8: o8 = o
            elif hr == 9 and o8 is not None:
                mv = c - o8
                dirn = (1 if mv > 0 else -1) if abs(mv) >= mom_atr * A[i] else 0
                if dirn == 0: done = True
            elif 10 <= hr <= 13 and dirn != 0:
                if pb_start is None:
                    if (c - o) * dirn < 0: pb_start = i          # first counter-trend bar
                    continue
                ok = (c - o) * dirn > 0 and (not strong or (c > rows[i-1][2] if dirn == 1 else c < rows[i-1][3]))
                if (c - o) * dirn < 0 or not ok:                    # still pulling back / not confirmed
                    continue
                ext = min(r[3] for r in rows[pb_start:i+1]) if dirn == 1 else max(r[2] for r in rows[pb_start:i+1])
                sl = ext - dirn * buf
                e = entry_px(rows, i, dirn, sym)
                if (e - sl) * dirn < 0.25 * A[i]: sl = e - dirn * 0.25 * A[i]
                mb = _bars_until_hour(rows, i, flat_hour) if flat_hour else None
                s = with_target(rows, sym, i, dirn, sl, k, mb)
                if s: out.append(s)
                done = True
            elif hr >= 14: done = True
        return out
    return gen, 3600

# ---------------- Family 4: H1 trend pullback to EMA20 ----------------
def f4(k, stop_mode, tbars, slope_lb=10):
    def gen(sym, tf_):
        rows, pip = bars(sym, 3600), PIPS[sym]
        O = [r[1] for r in rows]; H = [r[2] for r in rows]; L = [r[3] for r in rows]; C = [r[4] for r in rows]
        e50, e20, A = ema(C, 50), ema(C, 20), atr(rows); buf = SPREAD[sym] * pip
        out = []
        for i in range(60, len(rows)):
            if e50[i - slope_lb] is None: continue
            up = C[i] > e50[i] and e50[i] > e50[i - slope_lb]
            dn = C[i] < e50[i] and e50[i] < e50[i - slope_lb]
            if up and min(L[i-2:i+1]) <= e20[i] and C[i] > e20[i] and C[i] > O[i] and C[i] > H[i-1]:
                d = 1
            elif dn and max(H[i-2:i+1]) >= e20[i] and C[i] < e20[i] and C[i] < O[i] and C[i] < L[i-1]:
                d = -1
            else: continue
            e = entry_px(rows, i, d, sym)
            if stop_mode == "swing":
                sl = (min(L[i-4:i+1]) - buf) if d == 1 else (max(H[i-4:i+1]) + buf)
            else:
                sl = e - d * 1.0 * A[i]
            r = (e - sl) * d
            if r < 0.25 * A[i]: sl = e - d * 0.25 * A[i]
            elif r > 3 * A[i]: continue
            s = with_target(rows, sym, i, d, sl, k, tbars)
            if s: out.append(s)
        return out
    return gen, 3600

# ---------------- controls ----------------
def control(gen, tf, mode, seed):
    """Same exit geometry (stop distance, target distance, max_bars) per real setup, but
    mode='rand': random bar + random direction; mode='dir': same bar, random direction."""
    def g(sym, tf_):
        rows = bars(sym, tf)
        rng = random.Random(f"{sym}-{tf}-{mode}-{seed}")
        out = []
        for st in gen(sym, tf):
            i, d, sl, tp = st[:4]
            e = entry_px(rows, i, d, sym)
            risk, rew = abs(e - sl), abs(tp - e)
            j = rng.randrange(60, len(rows) - 2) if mode == "rand" else i
            dj = rng.choice((1, -1))
            ej = entry_px(rows, j, dj, sym)
            out.append((j, dj, ej - dj * risk, ej + dj * rew) + tuple(st[4:]))
        return out
    return g

# ---------------- evaluation (mirror of sim15.evaluate/run_sequential, plus 'setup' key) ----------------
def run_seq(rows, setups, pip, spread, cooldown=0):
    out, busy, last = [], -1, -10**9
    for st in sorted(setups, key=lambda x: x[0]):
        if st[0] < busy or st[0] - last < cooldown: continue
        tr = trade(rows, st, pip, spread)
        if tr is None: continue
        tr["setup"] = tuple(st)
        out.append(tr); busy = tr["exit_i"]; last = st[0]
    return out

def evaluate(gen, tf):
    res, weeks = {}, {}
    for grp, group in (("seen", SEEN), ("unseen", UNSEEN)):
        for h in (0, 1): res[(grp, h)] = []
        for sym in group:
            rows = bars(sym, tf)
            trs = run_seq(rows, gen(sym, tf), PIPS[sym], SPREAD[sym])
            mid = rows[len(rows) // 2][0]
            weeks[sym] = (rows[-1][0] - rows[0][0]) / 604800
            for t in trs:
                t["sym"] = sym
                res[(grp, int(t["time"] >= mid))].append(t)
    return res, weeks
