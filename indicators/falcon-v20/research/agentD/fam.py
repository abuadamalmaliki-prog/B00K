"""agentD families: price action, SMC and levels. Each factory returns gen(sym, tf) -> sim15 setups.
All signals use only bars <= signal bar i (pivots are used only after their confirmation bar)."""
import math, bisect
from lib import arrays, pivots, mk, daykey, weekkey, period_levels, WARM, PIPS

EXP_ZONE = 48     # bars a zone (FVG / OB / fib level) stays armed
EXP_LVL = 24      # bars a level break waits for its retest

# ------------------------------------------------ F1 Fair Value Gap first retest
def fvg(target, min_gap=0.25):
    """target: ('R',k) or 'swing' (impulse extreme between gap formation and retest)."""
    def gen(sym, tf):
        a = arrays(sym, tf); H, L, C, A, n = a["H"], a["L"], a["C"], a["A"], a["n"]
        out = []
        for k in range(WARM, n - 1):
            for d in (1, -1):
                if d == 1:
                    top, bot = L[k], H[k - 2]            # bullish gap = [H[k-2], L[k]]
                    if top - bot < min_gap * A[k]: continue
                    near, far = top, bot
                else:
                    top, bot = L[k - 2], H[k]           # bearish gap = [H[k], L[k-2]]
                    if top - bot < min_gap * A[k]: continue
                    near, far = bot, top
                ext = max(H[k - 1], H[k]) if d == 1 else min(L[k - 1], L[k])
                for j in range(k + 1, min(n, k + 1 + EXP_ZONE)):
                    touched = L[j] <= near if d == 1 else H[j] >= near
                    if touched:
                        tg = ("L", ext) if target == "swing" else target
                        s = mk(sym, a, j, d, far, tg, tf)
                        if s: out.append(s)
                        break
                    ext = max(ext, H[j]) if d == 1 else min(ext, L[j])
        return out
    return gen

# ------------------------------------------------ F2 Order block retest after BOS
def ob(pn, target):
    def gen(sym, tf):
        a = arrays(sym, tf); O, H, L, C, A, n = a["O"], a["H"], a["L"], a["C"], a["A"], a["n"]
        ph, pl = pivots(sym, tf, pn)
        phc = {c: (k, p) for c, k, p in ph}; plc = {c: (k, p) for c, k, p in pl}
        sh = sl_ = None                 # last confirmed swing high / low: [pivot_bar, price, broken]
        out = []
        for b in range(WARM, n - 1):
            if b in phc: sh = [phc[b][0], phc[b][1], False]
            if b in plc: sl_ = [plc[b][0], plc[b][1], False]
            for d, sw in ((1, sh), (-1, sl_)):
                if sw is None or sw[2]: continue
                if not (C[b] > sw[1] if d == 1 else C[b] < sw[1]): continue
                sw[2] = True
                # origin of the impulse leg: extreme bar between the broken swing and the BOS bar
                rng = range(sw[0], b + 1)
                m = min(rng, key=lambda x: L[x]) if d == 1 else max(rng, key=lambda x: H[x])
                obi = None
                for x in range(m, max(sw[0] - 1, m - 6), -1):       # last opposite candle at/before origin
                    if (C[x] < O[x]) if d == 1 else (C[x] > O[x]): obi = x; break
                if obi is None: continue
                zt, zb = H[obi], L[obi]
                near, far = (zt, zb) if d == 1 else (zb, zt)
                ext = max(H[m:b + 1]) if d == 1 else min(L[m:b + 1])
                for j in range(b + 1, min(n, b + 1 + EXP_ZONE)):
                    if (L[j] <= near) if d == 1 else (H[j] >= near):
                        tg = ("L", ext) if target == "ext" else target
                        s = mk(sym, a, j, d, far, tg, tf)
                        if s: out.append(s)
                        break
                    ext = max(ext, H[j]) if d == 1 else min(ext, L[j])
        return out
    return gen

# ------------------------------------------------ F3 candlestick patterns at swing extremes
def candle(pattern, target, N=20):
    def gen(sym, tf):
        a = arrays(sym, tf); O, H, L, C, A, n = a["O"], a["H"], a["L"], a["C"], a["A"], a["n"]
        out = []
        for i in range(WARM, n - 1):
            lo_ext = min(L[i - N + 1:i + 1]); hi_ext = max(H[i - N + 1:i + 1])
            if pattern == "engulf":
                if C[i - 1] < O[i - 1] and C[i] > O[i] and O[i] <= C[i - 1] and C[i] >= O[i - 1] \
                        and C[i] - O[i] > O[i - 1] - C[i - 1] and min(L[i], L[i - 1]) == lo_ext:
                    s = mk(sym, a, i, 1, min(L[i], L[i - 1]), target, tf); s and out.append(s)
                if C[i - 1] > O[i - 1] and C[i] < O[i] and O[i] >= C[i - 1] and C[i] <= O[i - 1] \
                        and O[i] - C[i] > C[i - 1] - O[i - 1] and max(H[i], H[i - 1]) == hi_ext:
                    s = mk(sym, a, i, -1, max(H[i], H[i - 1]), target, tf); s and out.append(s)
            elif pattern == "pin":
                r = H[i] - L[i]
                if r < 0.5 * A[i] or r <= 0: continue
                body = abs(C[i] - O[i]); lw = min(O[i], C[i]) - L[i]; uw = H[i] - max(O[i], C[i])
                if lw >= 2 * body and lw >= 0.6 * r and uw <= 0.25 * r and L[i] == lo_ext:
                    s = mk(sym, a, i, 1, L[i], target, tf); s and out.append(s)
                if uw >= 2 * body and uw >= 0.6 * r and lw <= 0.25 * r and H[i] == hi_ext:
                    s = mk(sym, a, i, -1, H[i], target, tf); s and out.append(s)
            elif pattern == "inside":
                m = i - 1                                   # mother bar m, inside bar m+1=i
                if not (H[i] <= H[m] and L[i] >= L[m]): continue
                lo_m = min(L[m - N + 1:m + 1]); hi_m = max(H[m - N + 1:m + 1])
                for d in (1, -1):
                    if (d == 1 and L[m] != lo_m) or (d == -1 and H[m] != hi_m): continue
                    for j in range(i + 1, min(n, i + 4)):   # breakout close within 3 bars
                        if (C[j] > H[m]) if d == 1 else (C[j] < L[m]):
                            s = mk(sym, a, j, d, L[m] if d == 1 else H[m], target, tf); s and out.append(s); break
                        if (C[j] < L[m]) if d == 1 else (C[j] > H[m]): break
        return out
    return gen

# ------------------------------------------------ F4 Fibonacci 61.8% retracement (pivots 5/5)
def fib(target, min_leg, pn=5, lvl=0.618):
    def gen(sym, tf):
        a = arrays(sym, tf); H, L, C, A, n = a["H"], a["L"], a["C"], a["A"], a["n"]
        ph, pl = pivots(sym, tf, pn)
        ev = sorted([(c, k, p, 1) for c, k, p in ph] + [(c, k, p, -1) for c, k, p in pl])
        out = []
        last = {1: None, -1: None}       # last confirmed pivot high / low: (pivot_bar, price)
        for conf, k, p, typ in ev:
            last[typ] = (k, p)
            opp = last[-typ]
            if opp is None or opp[0] >= k or conf < WARM: continue
            d = typ                       # new swing high -> up leg -> long retracement; low -> short
            a0, p0 = opp
            if d == 1 and min(L[a0:k + 1]) < p0: continue       # leg origin must be the leg extreme
            if d == -1 and max(H[a0:k + 1]) > p0: continue
            leg = abs(p - p0)
            if leg < min_leg * A[conf]: continue
            level = p - d * lvl * leg
            if any((L[x] <= level) if d == 1 else (H[x] >= level) for x in range(k + 1, conf + 1)): continue
            for j in range(conf + 1, min(n, conf + 1 + EXP_ZONE)):
                if (L[j] <= level) if d == 1 else (H[j] >= level):
                    tg = ("L", p) if target == "ext" else target
                    s = mk(sym, a, j, d, p0, tg, tf); s and out.append(s); break
                if (H[j] > p) if d == 1 else (L[j] < p): break    # leg extended -> cancel
        return out
    return gen

# ------------------------------------------------ period helpers (H1 or H4 bars)
def _levels_per_bar(sym, tf, keyf):
    a = arrays(sym, tf); rows = a["rows"]; prev = period_levels(sym, keyf)
    keys = [keyf(r[0]) for r in rows]
    return keys, [prev.get(k) for k in keys]

# ------------------------------------------------ F5 classic floor pivots (H1)
def floor_pivot(mode, stop_atr, target):
    """mode: 'fade_touch' | 'fade_reject' | 'break_retest'; target: 'P' or ('R',k)."""
    def gen(sym, tf):
        a = arrays(sym, tf); O, H, L, C, A, n = a["O"], a["H"], a["L"], a["C"], a["A"], a["n"]
        keys, pv = _levels_per_bar(sym, tf, daykey)
        out = []
        i = WARM
        while i < n - 1:
            k = keys[i]; j = i
            while j < n and keys[j] == k: j += 1
            lv = pv[i]
            if lv and lv[4] >= 10:
                ph, pl, pc = lv[1], lv[2], lv[3]
                P = (ph + pl + pc) / 3; R1 = 2 * P - pl; S1 = 2 * P - ph
                if S1 < O[i] < R1:
                    for d, lev in ((-1, R1), (1, S1)):      # fade: short at R1, long at S1
                        if mode.startswith("fade"):
                            for x in range(i, j):
                                if (H[x] >= lev) if d == -1 else (L[x] <= lev):
                                    if mode == "fade_reject" and not ((C[x] < lev) if d == -1 else (C[x] > lev)): break
                                    struct = lev - d * stop_atr * A[x] + d * 0.1 * A[x]   # mk adds 0.1 ATR buffer
                                    struct = struct if d * (C[x] - struct) > 0 else None
                                    if struct is None: break
                                    tg = ("L", P) if target == "P" else target
                                    s = mk(sym, a, x, d, struct, tg, tf); s and out.append(s)
                                    break
                        else:                                # break of R1 -> long retest; break of S1 -> short
                            db = -d
                            for x in range(i, j):
                                if (C[x] > lev) if db == 1 else (C[x] < lev):
                                    for y in range(x + 1, min(n, x + 1 + EXP_LVL)):
                                        if (L[y] <= lev) if db == 1 else (H[y] >= lev):
                                            if (C[y] > lev) if db == 1 else (C[y] < lev):
                                                struct = lev - db * stop_atr * A[y] + db * 0.1 * A[y]
                                                s = mk(sym, a, y, db, struct, target, tf); s and out.append(s)
                                            break
                                    break
            i = j
        return out
    return gen

# ------------------------------------------------ F6 round-number (00/50) rejection fades
def round_step(sym):
    if sym == "XAUUSD": return 50.0
    if sym == "XAGUSD": return 0.50
    return 50 * PIPS[sym]                    # 0.0050 FX, 0.50 JPY crosses

def round_fade(levels, target, fresh=24):
    def gen(sym, tf):
        a = arrays(sym, tf); H, L, C, A, n = a["H"], a["L"], a["C"], a["A"], a["n"]
        st = round_step(sym) * (2 if levels == "00" else 1)
        out = []
        for i in range(WARM, n - 1):
            X = math.ceil(C[i] / st - 1e-9) * st           # level just above the close -> short rejection
            if H[i] >= X > C[i] and C[i - 1] < X and max(H[i - fresh:i]) < X:
                s = mk(sym, a, i, -1, H[i], target, tf); s and out.append(s)
            X = math.floor(C[i] / st + 1e-9) * st          # level just below -> long rejection
            if L[i] <= X < C[i] and C[i - 1] > X and min(L[i - fresh:i]) > X:
                s = mk(sym, a, i, 1, L[i], target, tf); s and out.append(s)
        return out
    return gen

# ------------------------------------------------ F7 prior-day / prior-week high-low break & retest
def prior_hl(period, target):
    keyf = daykey if period == "day" else weekkey
    def gen(sym, tf):
        a = arrays(sym, tf); H, L, C, A, n = a["H"], a["L"], a["C"], a["A"], a["n"]
        keys, pv = _levels_per_bar(sym, tf, keyf)
        out, done = [], set()
        for b in range(WARM, n - 1):
            lv = pv[b]
            if not lv or lv[4] < (10 if period == "day" else 50): continue
            for d, lev in ((1, lv[1]), (-1, lv[2])):
                if (keys[b], d) in done: continue
                if not ((C[b] > lev >= C[b - 1]) if d == 1 else (C[b] < lev <= C[b - 1])): continue
                done.add((keys[b], d))                      # first break per period and side
                for y in range(b + 1, min(n, b + 1 + EXP_LVL)):
                    if (L[y] <= lev) if d == 1 else (H[y] >= lev):
                        if (C[y] > lev) if d == 1 else (C[y] < lev):
                            s = mk(sym, a, y, d, L[y] if d == 1 else H[y], target, tf); s and out.append(s)
                        break
        return out
    return gen

H1, H4 = 3600, 14400
GRIDS = {
  "F1_FVG": [(f"FVG {tfn} tp={tg}", fvg(t), tf) for tf, tfn in ((H1, "H1"), (H4, "H4"))
             for tg, t in (("1R", ("R", 1.0)), ("2R", ("R", 2.0)), ("swing", "swing"))],
  "F2_OB": [(f"OB p{pn} {tfn} tp={tg}", ob(pn, t), tf) for tf, tfn in ((H1, "H1"), (H4, "H4"))
            for pn in (3, 5) for tg, t in (("1R", ("R", 1.0)), ("2R", ("R", 2.0)))] +
           [(f"OB p5 {tfn} tp=ext", ob(5, "ext"), tf) for tf, tfn in ((H1, "H1"), (H4, "H4"))],
  "F3_CANDLE": [(f"{p} {tfn} tp={tg}", candle(p, t), tf) for p in ("engulf", "pin") for tf, tfn in ((H1, "H1"), (H4, "H4"))
                for tg, t in (("1R", ("R", 1.0)), ("2R", ("R", 2.0)))] +
               [(f"inside {tfn} tp=1R", candle("inside", ("R", 1.0)), tf) for tf, tfn in ((H1, "H1"), (H4, "H4"))],
  "F4_FIB": [(f"fib618 {tfn} leg>={ml}ATR tp={tg}", fib(t, ml), tf) for tf, tfn in ((H1, "H1"), (H4, "H4"))
             for ml in (2.0, 4.0) for tg, t in (("ext", "ext"), ("1R", ("R", 1.0)))],
  "F5_PIVOT": [(f"pivot {m} stop{sa}ATR tp=P", floor_pivot(m, sa, "P"), H1) for m in ("fade_touch", "fade_reject") for sa in (0.5, 1.0)] +
              [(f"pivot fade_reject stop{sa}ATR tp=1R", floor_pivot("fade_reject", sa, ("R", 1.0)), H1) for sa in (0.5, 1.0)] +
              [(f"pivot break_retest stop{sa}ATR tp={tg}", floor_pivot("break_retest", sa, t), H1) for sa in (0.5, 1.0)
               for tg, t in (("1R", ("R", 1.0)), ("2R", ("R", 2.0)))],
  "F6_ROUND": [(f"round {lv} {tfn} tp={tg}", round_fade(lv, t), tf) for lv in ("00+50", "00") for tf, tfn in ((H1, "H1"), (H4, "H4"))
               for tg, t in (("1R", ("R", 1.0)), ("2R", ("R", 2.0)))],
  "F7_PDPW": [(f"prior-{p} {tfn} tp={tg}", prior_hl(p, t), tf) for p in ("day", "week") for tf, tfn in ((H1, "H1"), (H4, "H4"))
              for tg, t in (("1R", ("R", 1.0)), ("2R", ("R", 2.0)))],
}
