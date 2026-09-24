"""Agent C: TREND FOLLOWING & MOMENTUM families under the V15 protocol.

Run from anywhere:  python3 agentC/trend.py
Selection rule (pre-registered, SEEN only): among a family's configs with >= 30 trades in each SEEN half,
pick the one maximising min(SEEN-half1 net avgR, SEEN-half2 net avgR). UNSEEN never used for selection.
"""
import sys, os, math, random, pickle, bisect, time as _time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); os.chdir(ROOT)
from common import PIPS, bars
from sim15 import trade, stats, SPREAD, SWAP, SEEN, UNSEEN
from sim import ny
from datetime import timedelta

ALL = SEEN + UNSEEN
WARM = 250          # bars skipped before any signal (EMA200 warm-up), same for all families
FAR = 100.0         # "no target" = 100x stop distance (used with time / opposite-signal exits)

# ---------------------------------------------------------------- indicators (causal, value at bar k uses bars <= k)
def ema(x, n):
    a, out, v = 2.0 / (n + 1), [0.0] * len(x), x[0]
    for k, xv in enumerate(x):
        v = xv if k == 0 else v + a * (xv - v); out[k] = v
    return out

def rma(x, n, start=0):
    out = [None] * len(x)
    if len(x) - start < n: return out
    v = sum(x[start:start + n]) / n; out[start + n - 1] = v
    for k in range(start + n, len(x)):
        v = (v * (n - 1) + x[k]) / n; out[k] = v
    return out

def true_range(rows):
    tr = [rows[0][2] - rows[0][3]]
    for k in range(1, len(rows)):
        h, l, pc = rows[k][2], rows[k][3], rows[k - 1][4]
        tr.append(max(h - l, abs(h - pc), abs(l - pc)))
    return tr

def atr(rows, n=14): return rma(true_range(rows), n)

def crosses(a, b):
    """indices k where a crosses above b (up) / below b (dn) at bar k."""
    up, dn = [], []
    for k in range(1, len(a)):
        if a[k] is None or a[k - 1] is None or b[k] is None or b[k - 1] is None: continue
        if a[k] > b[k] and a[k - 1] <= b[k - 1]: up.append(k)
        elif a[k] < b[k] and a[k - 1] >= b[k - 1]: dn.append(k)
    return up, dn

def supertrend(rows, n=10, m=3.0):
    A = atr(rows, n); N = len(rows)
    trend, line = [0] * N, [None] * N
    up_p = dn_p = None; tr_p = 1
    for k in range(N):
        if A[k] is None: continue
        h, l, c = rows[k][2], rows[k][3], rows[k][4]
        hl2 = (h + l) / 2; up = hl2 - m * A[k]; dn = hl2 + m * A[k]
        pc = rows[k - 1][4]
        if up_p is not None:
            up = max(up, up_p) if pc > up_p else up
            dn = min(dn, dn_p) if pc < dn_p else dn
            if tr_p == -1 and c > dn_p: tr = 1
            elif tr_p == 1 and c < up_p: tr = -1
            else: tr = tr_p
        else:
            tr = 1
        trend[k] = tr; line[k] = up if tr == 1 else dn
        up_p, dn_p, tr_p = up, dn, tr
    return trend, line, A

def dmi(rows, n=14):
    N = len(rows); pdm, mdm = [0.0] * N, [0.0] * N
    for k in range(1, N):
        u = rows[k][2] - rows[k - 1][2]; d = rows[k - 1][3] - rows[k][3]
        pdm[k] = u if (u > d and u > 0) else 0.0
        mdm[k] = d if (d > u and d > 0) else 0.0
    tr = true_range(rows)
    rt, rp, rm = rma(tr, n, 1), rma(pdm, n, 1), rma(mdm, n, 1)
    pdi, mdi, dx = [None] * N, [None] * N, [0.0] * N
    first = None
    for k in range(N):
        if rt[k] is None or rt[k] == 0: continue
        pdi[k] = 100 * rp[k] / rt[k]; mdi[k] = 100 * rm[k] / rt[k]
        s = pdi[k] + mdi[k]; dx[k] = 100 * abs(pdi[k] - mdi[k]) / s if s > 0 else 0.0
        if first is None: first = k
    adx = rma(dx, n, first)
    return pdi, mdi, adx

def boll(closes, n=20, k=2.0):
    N = len(closes); mid, upb, lob, bw = [None] * N, [None] * N, [None] * N, [None] * N
    for i in range(n - 1, N):
        w = closes[i - n + 1:i + 1]; m = sum(w) / n
        sd = math.sqrt(sum((x - m) ** 2 for x in w) / n)
        mid[i], upb[i], lob[i] = m, m + k * sd, m - k * sd
        bw[i] = (2 * k * sd) / m
    return mid, upb, lob, bw

# ---------------------------------------------------------------- setup helpers
def next_after(idx_list, i):
    j = bisect.bisect_right(idx_list, i)
    return idx_list[j] if j < len(idx_list) else None

def mk(rows, i, d, dist, tgt, mb=None):
    c = rows[i][4]
    if dist is None or dist <= 0: return None
    sl = c - d * dist
    tp = c + d * (tgt if tgt else FAR) * dist
    return (i, d, sl, tp) if mb is None else (i, d, sl, tp, mb)

def exit_bars(i, d, opp_up, opp_dn):
    """opposite-signal exit: bars until the next opposite cross (exit at that bar's close)."""
    j = next_after(opp_dn if d == 1 else opp_up, i)
    return None if j is None else j - i

# ---------------------------------------------------------------- family generators
# each returns (rows, setups, atr_ref) ; atr_ref used by the random control to rescale stops
_cache = {}
def cached(key, fn):
    if key not in _cache: _cache[key] = fn()
    return _cache[key]

def gen_ma(sym, cfg):
    tf, f, s, tgt = cfg["tf"], cfg["fast"], cfg["slow"], cfg["tgt"]
    rows = bars(sym, tf)
    def ind():
        cl = [r[4] for r in rows]
        up, dn = crosses(ema(cl, f), ema(cl, s))
        return up, dn, atr(rows, 14)
    up, dn, A = cached(("ma", sym, tf, f, s), ind)
    st = []
    for lst, d in ((up, 1), (dn, -1)):
        for i in lst:
            if i < WARM or A[i] is None: continue
            mb = exit_bars(i, d, up, dn) if tgt == "opp" else None
            x = mk(rows, i, d, 1.5 * A[i], None if tgt == "opp" else tgt, mb)
            if x: st.append(x)
    return rows, st, A

def gen_st(sym, cfg):
    tf, stop, tgt = cfg["tf"], cfg["stop"], cfg["tgt"]
    rows = bars(sym, tf)
    def ind():
        trend, line, A = supertrend(rows, 10, 3.0)
        up = [k for k in range(1, len(rows)) if trend[k] == 1 and trend[k - 1] == -1]
        dn = [k for k in range(1, len(rows)) if trend[k] == -1 and trend[k - 1] == 1]
        return up, dn, line, A
    up, dn, line, A = cached(("st", sym, tf), ind)
    st = []
    for lst, d in ((up, 1), (dn, -1)):
        for i in lst:
            if i < WARM or A[i] is None: continue
            dist = 1.5 * A[i] if stop == "atr" else d * (rows[i][4] - line[i])
            mb = exit_bars(i, d, up, dn) if tgt == "opp" else None
            x = mk(rows, i, d, dist, None if tgt == "opp" else tgt, mb)
            if x: st.append(x)
    return rows, st, A

def gen_macd(sym, cfg):
    tf, zero, tgt = cfg["tf"], cfg["zero"], cfg["tgt"]
    rows = bars(sym, tf)
    def ind():
        cl = [r[4] for r in rows]
        e12, e26 = ema(cl, 12), ema(cl, 26)
        macd = [a - b for a, b in zip(e12, e26)]; sig = ema(macd, 9)
        up, dn = crosses(macd, sig)
        return up, dn, macd, ema(cl, 200), atr(rows, 14)
    up, dn, macd, e200, A = cached(("macd", sym, tf), ind)
    st = []
    for lst, d in ((up, 1), (dn, -1)):
        for i in lst:
            if i < WARM or A[i] is None: continue
            c = rows[i][4]
            if d * (c - e200[i]) <= 0: continue
            if zero and d * macd[i] >= 0: continue   # long only when MACD < 0, short only when MACD > 0
            mb = exit_bars(i, d, up, dn) if tgt == "opp" else None
            x = mk(rows, i, d, 1.5 * A[i], None if tgt == "opp" else tgt, mb)
            if x: st.append(x)
    return rows, st, A

def gen_adx(sym, cfg):
    tf, tgt = cfg["tf"], cfg["tgt"]
    rows = bars(sym, tf)
    def ind():
        pdi, mdi, adx = dmi(rows, 14)
        up, dn = crosses(pdi, mdi)
        return up, dn, adx, atr(rows, 14)
    up, dn, adx, A = cached(("adx", sym, tf), ind)
    st = []
    for lst, d in ((up, 1), (dn, -1)):
        for i in lst:
            if i < WARM or A[i] is None or adx[i] is None or adx[i] <= 25: continue
            mb = exit_bars(i, d, up, dn) if tgt == "opp" else None
            x = mk(rows, i, d, 1.5 * A[i], None if tgt == "opp" else tgt, mb)
            if x: st.append(x)
    return rows, st, A

def gen_bb(sym, cfg):
    tf, stop, tgt = cfg["tf"], cfg["stop"], cfg["tgt"]
    rows = bars(sym, tf)
    def ind():
        cl = [r[4] for r in rows]
        mid, upb, lob, bw = boll(cl, 20, 2.0)
        sigs, armed = [], None
        for i in range(len(rows)):
            if bw[i] is None: continue
            if i >= 139:
                w = bw[i - 119:i + 1]
                if None not in w and bw[i] <= min(w): armed = i   # squeeze: bandwidth at 120-bar low
            if armed is not None and i - armed > 20: armed = None  # squeeze stays armed 20 bars
            if armed is not None and i > armed:
                if cl[i] > upb[i]: sigs.append((i, 1)); armed = None
                elif cl[i] < lob[i]: sigs.append((i, -1)); armed = None
        return sigs, mid, atr(rows, 14)
    sigs, mid, A = cached(("bb", sym, tf), ind)
    st = []
    for i, d in sigs:
        if i < WARM or A[i] is None: continue
        dist = 1.5 * A[i] if stop == "atr" else d * (rows[i][4] - mid[i])
        x = mk(rows, i, d, dist, tgt)
        if x: st.append(x)
    return rows, st, A

def nyday_ends(rows):
    """index of the last H1 bar of each New-York trading day (day ends 17:00 NY)."""
    keys = [(ny(r[0]) + timedelta(hours=7)).date() for r in rows]
    ends = [k for k in range(len(rows) - 1) if keys[k + 1] != keys[k]]
    # merge stub segments (< 12 H1 bars, e.g. the lone Friday 17:00-NY bar before the weekend) into the previous day
    out, s = [], 0
    for e in ends:
        if e - s + 1 < 12 and out: out[-1] = e
        else: out.append(e)
        s = e + 1
    return out

def gen_tsmom(sym, cfg):
    hold, sm, rnd = cfg["hold"], cfg["stop"], cfg.get("rand")
    rows = bars(sym, 3600)
    def ind():
        ends = nyday_ends(rows)
        # daily bars built from H1 over each NY day
        daily, s = [], 0
        for e in ends:
            seg = rows[s:e + 1]
            daily.append((seg[0][0], seg[0][1], max(r[2] for r in seg), min(r[3] for r in seg), seg[-1][4], 0))
            s = e + 1
        return ends, daily, atr(daily, 14)
    ends, daily, DA = cached(("tsm", sym), ind)
    rng = random.Random(rnd) if rnd is not None else None
    st, aref = [], [None] * len(rows)
    for di in range(len(ends)):
        i = ends[di]; aref[i] = DA[di]
        if di < 20 or DA[di] is None or i < WARM or di + hold >= len(ends): continue
        r20 = daily[di][4] - daily[di - 20][4]
        if r20 == 0: continue
        d = (1 if r20 > 0 else -1) if rng is None else rng.choice((1, -1))
        x = mk(rows, i, d, sm * DA[di], None, ends[di + hold] - i)
        if x: st.append(x)
    return rows, st, aref

def gen_don(sym, cfg):
    tf, sm, tgt = cfg["tf"], cfg["stop"], cfg["tgt"]
    rows = bars(sym, tf)
    def ind():
        sigs = []
        for i in range(21, len(rows)):
            hh = max(r[2] for r in rows[i - 20:i]); ll = min(r[3] for r in rows[i - 20:i])
            hh1 = max(r[2] for r in rows[i - 21:i - 1]); ll1 = min(r[3] for r in rows[i - 21:i - 1])
            c, pc = rows[i][4], rows[i - 1][4]
            if c > hh and pc <= hh1: sigs.append((i, 1))       # first close above prior 20-bar high
            elif c < ll and pc >= ll1: sigs.append((i, -1))
        return sigs, atr(rows, 14)
    sigs, A = cached(("don", sym, tf), ind)
    st = []
    for i, d in sigs:
        if i < WARM or A[i] is None: continue
        x = mk(rows, i, d, sm * A[i], tgt)
        if x: st.append(x)
    return rows, st, A

H1, H4 = 3600, 14400
FAMILIES = {
    "F1_ma_cross": (gen_ma, [dict(tf=tf, fast=f, slow=s, tgt=t) for tf in (H1, H4) for f, s in ((9, 21), (20, 50)) for t in (1.0, 2.0)]
                    + [dict(tf=tf, fast=20, slow=50, tgt="opp") for tf in (H1, H4)]),
    "F2_supertrend": (gen_st, [dict(tf=tf, stop=sp, tgt=t) for tf in (H1, H4) for sp in ("atr", "line") for t in (1.0, 2.0)]
                      + [dict(tf=tf, stop="line", tgt="opp") for tf in (H1, H4)]),
    "F3_macd_ema200": (gen_macd, [dict(tf=tf, zero=z, tgt=t) for tf in (H1, H4) for z in (False, True) for t in (1.0, 2.0)]
                       + [dict(tf=tf, zero=False, tgt="opp") for tf in (H1, H4)]),
    "F4_adx_di": (gen_adx, [dict(tf=tf, tgt=t) for tf in (H1, H4) for t in (1.0, 2.0, "opp")]),
    "F5_bb_squeeze": (gen_bb, [dict(tf=tf, stop=sp, tgt=t) for tf in (H1, H4) for sp in ("atr", "mid") for t in (1.0, 2.0)]),
    "F6_tsmom_daily": (gen_tsmom, [dict(tf=H1, hold=h, stop=s) for h in (1, 3, 5) for s in (1.0, 2.0)]),
    "F7_donchian": (gen_don, [dict(tf=tf, stop=s, tgt=t) for tf in (H1, H4) for s in (1.0, 2.0) for t in (0.5, 1.0)]),
}

def cfg_name(c):
    return ",".join(f"{k}={('H1' if v == H1 else 'H4') if k == 'tf' else v}" for k, v in c.items())

# ---------------------------------------------------------------- simulation
def seq(rows, setups, pip, spread, swap):
    """= sim15.run_sequential (cooldown 0) but keeps the exact setup tuple on each trade."""
    out, busy = [], -1
    for st in sorted(setups, key=lambda x: x[0]):
        if st[0] < busy: continue
        tr = trade(rows, st, pip, spread, swap)
        if tr is None: continue
        tr["setup"] = st; out.append(tr); busy = tr["exit_i"]
    return out

def run(gen, cfg, syms, gross=False, setups_override=None):
    res = {}
    for sym in syms:
        rows, st, _ = gen(sym, cfg)
        if setups_override is not None: st = setups_override[sym]
        trs = seq(rows, st, PIPS[sym], 0.0 if gross else SPREAD[sym], 0.0 if gross else SWAP)
        mid = rows[len(rows) // 2][0]
        for t in trs:
            t["sym"] = sym; t["half"] = int(t["time"] >= mid)
            t["grp"] = "seen" if sym in SEEN else "unseen"
        res[sym] = trs
    return res

def cells(res):
    allt = [t for v in res.values() for t in v]
    c = {"all": allt}
    for g in ("seen", "unseen"):
        c[g] = [t for t in allt if t["grp"] == g]
        for h in (0, 1): c[(g, h)] = [t for t in c[g] if t["half"] == h]
    return c

def fmt(s): return f"n={s['n']:5d} win={s['win']:5.1f}% R={s['avgR']:+.3f}±{s['se']:.3f}"

def weeks(sym):
    r = bars(sym, 3600); return (r[-1][0] - r[0][0]) / (7 * 86400)

def random_control(gen, cfg, fam, seeds=5):
    """random bars + random direction, same stop distance (in ATR units), same target multiple, same time/opp exit length."""
    pooled = []
    for seed in range(seeds):
        over = {}
        for sym in ALL:
            if fam == "F6_tsmom_daily":
                c2 = dict(cfg); c2["rand"] = 1000 * seed + ALL.index(sym)
                over[sym] = gen(sym, c2)[1]; continue
            rows, st, A = gen(sym, cfg)
            rng = random.Random(1000 * seed + ALL.index(sym))
            geo = []
            for s in st:
                i, d, sl, tp = s[:4]; c = rows[i][4]; dist = abs(c - sl)
                geo.append((dist / A[i], abs(tp - c) / dist, s[4] if len(s) > 4 else None))
            new = []
            for _ in range(len(st)):
                j = rng.randrange(WARM, len(rows) - 2)
                if A[j] is None: continue
                g = rng.choice(geo); d = rng.choice((1, -1)); c = rows[j][4]; dist = g[0] * A[j]
                x = (j, d, c - d * dist, c + d * g[1] * dist) + ((g[2],) if g[2] is not None else ())
                new.append(x)
            over[sym] = new
        res = run(gen, cfg, ALL, setups_override=over)
        pooled += [t for v in res.values() for t in v]
    return stats(pooled), len(pooled) / seeds

def main():
    t0 = _time.time()
    log = open(os.path.join(HERE, "grid_log.txt"), "w")
    def P(*a):
        s = " ".join(str(x) for x in a); print(s); log.write(s + "\n"); log.flush()
    P("Selection: max min(SEEN h1 R, SEEN h2 R), n>=30 per SEEN half. Net of costs. UNSEEN per-config lines are post-selection disclosure only.")
    summary = []
    for fam, (gen, grid) in FAMILIES.items():
        P(f"\n=== {fam} ({len(grid)} configs) ===")
        best, bestscore = None, -1e9
        for cfg in grid:
            res = run(gen, cfg, SEEN); c = cells(res)
            s0, s1, sa = stats(c[("seen", 0)]), stats(c[("seen", 1)]), stats(c["seen"])
            ok = s0["n"] >= 30 and s1["n"] >= 30
            score = min(s0["avgR"], s1["avgR"]) if ok else -1e9
            P(f"  {cfg_name(cfg):38s} SEEN {fmt(sa)} | s1 {fmt(s0)} | s2 {fmt(s1)} | score={score:+.3f}")
            if score > bestscore: best, bestscore = cfg, score
        # post-selection disclosure only (selection above is already fixed): every config on UNSEEN
        for cfg in grid:
            cu = cells(run(gen, cfg, UNSEEN))
            P(f"  [disclosure, not used] {cfg_name(cfg):38s} UNSEEN u1 {fmt(stats(cu[('unseen', 0)]))} | u2 {fmt(stats(cu[('unseen', 1)]))}")
        # chosen config: untouched on ALL 11
        res = run(gen, best, ALL); c = cells(res)
        gres = run(gen, best, ALL, gross=True); gc = cells(gres)
        ctrl, ctrl_n = random_control(gen, best, fam)
        S = {k: stats(v) for k, v in c.items()}
        tpw = sum(len(res[s]) / weeks(s) for s in ALL)
        hold = sum((t["exit_time"] - t["time"]) / 3600 for t in c["all"]) / max(1, len(c["all"]))
        passed = S[("unseen", 0)]["avgR"] > 0 and S[("unseen", 1)]["avgR"] > 0
        P(f"CHOSEN {cfg_name(best)}")
        for k in ("all", "seen", ("seen", 0), ("seen", 1), "unseen", ("unseen", 0), ("unseen", 1)):
            P(f"   {str(k):16s} {fmt(S[k])} PF={S[k]['pf']:.2f}")
        g = stats(gc["all"])
        P(f"   GROSS all {fmt(g)} | gross seen R={stats(gc['seen'])['avgR']:+.3f} unseen R={stats(gc['unseen'])['avgR']:+.3f}")
        P(f"   trades/week(11 syms)={tpw:.1f} avg hold={hold:.1f}h | CONTROL(5 seeds) {fmt(ctrl)} (~{ctrl_n:.0f} trades/seed)")
        P(f"   PASS={passed} win>=60%={'YES' if S['all']['win'] >= 60 else 'no'}")
        why = {}
        for t in c["all"]: why[t["why"]] = why.get(t["why"], 0) + 1
        P(f"   exits: {why}")
        trades = [t for s in ALL for t in res[s]]
        pickle.dump(trades, open(os.path.join(HERE, f"{fam}.pkl"), "wb"))
        summary.append(dict(fam=fam, cfg=cfg_name(best), S=S, gross=g, tpw=tpw, hold=hold, ctrl=ctrl, passed=passed))
        P(f"   [{_time.time() - t0:.0f}s]")
    pickle.dump(summary, open(os.path.join(HERE, "summary.pkl"), "wb"))
    P("\n=== SUMMARY ===")
    for s in summary:
        S = s["S"]
        P(f"{s['fam']:16s} {s['cfg']:36s} ALL {S['all']['win']:.0f}% {S['all']['avgR']:+.3f}±{S['all']['se']:.3f} | "
          f"SEEN {S['seen']['win']:.0f}% {S['seen']['avgR']:+.3f}±{S['seen']['se']:.3f} | UNSEEN {S['unseen']['win']:.0f}% "
          f"{S['unseen']['avgR']:+.3f}±{S['unseen']['se']:.3f} (u1 {S[('unseen',0)]['avgR']:+.3f}, u2 {S[('unseen',1)]['avgR']:+.3f}) | "
          f"gross {s['gross']['avgR']:+.3f} | {s['tpw']:.1f}/wk | {s['hold']:.0f}h | ctrl {s['ctrl']['avgR']:+.3f} {s['ctrl']['win']:.0f}% | PASS={s['passed']}")

if __name__ == "__main__":
    main()
