"""Parity proofs: the MT5 EA's engine (transliterated in mq_mirror.py) and trade replay
must match the research engine exactly, and Pine's swap counter must match sim.rollovers."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from common import PIPS, bars, resample
from engine import Engine, DEFAULTS, RMA
from mq_mirror import mq_setups
from sim import walk, rollovers
from strategies import STRATS, SPREAD, V3
NY = ZoneInfo("America/New_York")
def rsi_series(rows, n=14):
    u, d, out, prev = RMA(n), RMA(n), [], None
    for r in rows:
        c = r[4]
        if prev is None: out.append(float("nan")); prev = c; continue
        ch = c - prev; prev = c
        a, b = u(max(ch, 0)), d(max(-ch, 0))
        out.append(float("nan") if a != a or b != b else (100.0 if b == 0 else 100 - 100 / (1 + a / b)))
    return out
def mq_walk(rows, s, pip, spreadPx, target=300.0, be=150.0):
    i, d, sl, rp = s
    c = rows[i][4]; entry = c + spreadPx if d > 0 else c
    tp = entry + d * target * pip; stop = sl; beOn = False
    for k in range(i + 1, len(rows)):
        o, h, l = rows[k][1], rows[k][2], rows[k][3]; why = -1; px = 0
        if d > 0:
            if l <= stop: px = min(o, stop); why = 1 if beOn else 0
            elif h >= tp: px = tp; why = 2
            elif be > 0 and not beOn and h - entry >= be * pip: stop = entry; beOn = True
        else:
            if h + spreadPx >= stop: px = max(o + spreadPx, stop); why = 1 if beOn else 0
            elif l + spreadPx <= tp: px = tp; why = 2
            elif be > 0 and not beOn and entry - (l + spreadPx) >= be * pip: stop = entry; beOn = True
        if why >= 0: return (k, why, d * (px - entry) / pip)
    return None
def pine_roll(t0, t1):
    n, lastR = 0, None
    for k in range(7):
        dt = datetime.fromtimestamp(t1 - k * 86400, timezone.utc).astimezone(NY)
        r = int(datetime(dt.year, dt.month, dt.day, 17, 0, tzinfo=NY).timestamp())
        dw = datetime.fromtimestamp(r, timezone.utc).astimezone(NY).weekday()
        if t0 < r <= t1 and (lastR is None or r != lastR) and dw not in (5, 6):
            n += 3 if dw == 2 else 1
        lastR = r
    return n
if __name__ == "__main__":
    te = ts = 0
    for tf in (14400, 3600):
        for sym in PIPS:
            rows = bars(sym, tf); pip = PIPS[sym]
            P = dict(DEFAULTS); P.update(V3); P.update(raw=True, _htf_secs={3600: 14400, 14400: 86400}[tf])
            eng, _, _ = Engine(P).run(rows, resample(rows, P["_htf_secs"]), pip, tf)
            mq = mq_setups(rows, rsi_series(rows), pip, tf, P)
            E = {(i, d): (round(sl, 8), round(rp, 6)) for i, d, sl, rp in eng}
            Q = {(i, d): (round(sl, 8), round(rp, 6)) for i, d, sl, rp in mq}
            te += len(E) + len(set(Q) - set(E)); ts += sum(1 for k in E if Q.get(k) == E[k])
    print(f"setups: {ts} of {te} identical (EA engine vs research engine)")
    n = same = 0
    names = {0: "sl", 1: "be", 2: "tp"}
    for sym in PIPS:
        rows = bars(sym, 14400); pip = PIPS[sym]
        for s in STRATS["A sweep reversal"](sym, 14400):
            a = walk(rows, s[0], s[1], s[2], pip, spread=SPREAD[sym], swap=0.0); b = mq_walk(rows, s, pip, SPREAD[sym] * pip)
            if a is None and b is None: continue
            n += 1; same += bool(a and b and a["exit_i"] == b[0] and a["why"] == names[b[1]] and abs(a["pips"] - b[2]) < 1e-6)
    print(f"trade replays: {same} of {n} identical (EA Walk vs research sim)")
    tot = bad = 0
    for sym in PIPS:
        for tf in (3600, 14400):
            rows = bars(sym, tf)
            for a, b in zip(rows, rows[1:]):
                tot += 1; bad += pine_roll(a[0], b[0]) != rollovers(a[0], b[0])
    print(f"swap-night counts: {tot - bad} of {tot} identical (Pine f_roll vs research)")
