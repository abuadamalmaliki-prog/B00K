"""Line-by-line Python transliteration of f_engine() in falcon_v20.pine, for parity testing
against the research (combos.c3 setups + sim15 scorecard). Indicators use the research's own
implementations so that only the logic is compared."""
import sys
sys.path.insert(0, "agentC")
import trend
from sim import rollovers
from engine import RMA
def rsi_series(rows, n=14):
    """RSI exactly as the research engine computes it (Wilder RMA seeded with an SMA)."""
    u, d, out, prev = RMA(n), RMA(n), [], None
    for r in rows:
        c = r[4]
        if prev is None: out.append(float("nan")); prev = c; continue
        ch = c - prev; prev = c
        a, b = u(max(ch, 0)), d(max(-ch, 0))
        out.append(float("nan") if a != a or b != b else (100.0 if b == 0 else 100 - 100 / (1 + a / b)))
    return out
def v20_engine(rows, pipS, spr, swp):
    n = len(rows); C = [r[4] for r in rows]
    r14 = rsi_series(rows); e9 = trend.ema(C, 9); e21 = trend.ema(C, 21); atr = trend.atr(rows, 14)
    shP = slP = None; shB = slB = -1; shBr = slBr = True; shSw = slSw = False
    lastBull = lastBear = lastSetL = lastSetS = -1000000
    curDay, curH, curL, pdh, pdl = -1, None, None, None, None
    sigs = []
    tDir, tEntry, tSL, tTP, tRisk, tNights = 0, None, None, None, None, 0
    nT = nW = 0; sumR = 0.0
    s = spr * pipS
    for i in range(n):
        t, o, h, l, c, v = rows[i]
        dayIdx = t // 86400
        if dayIdx != curDay:
            if curDay >= 0: pdh, pdl = curH, curL
            curDay, curH, curL = dayIdx, h, l
        else:
            curH, curL = max(curH, h), min(curL, l)
        if i >= 8:
            isH = isL = True
            for k in range(0, 9):
                if k != 3:
                    if rows[i - k][2] >= rows[i - 3][2]: isH = False
                    if rows[i - k][3] <= rows[i - 3][3]: isL = False
            if isH: shP, shB, shBr, shSw = rows[i - 3][2], i - 3, False, False
            if isL: slP, slB, slBr, slSw = rows[i - 3][3], i - 3, False, False
        if shB >= 0 and not shBr and c > shP: shBr = True
        if slB >= 0 and not slBr and c < slP: slBr = True
        swL = slB >= 0 and not slBr and not slSw and l < slP and c > slP
        swH = shB >= 0 and not shBr and not shSw and h > shP and c < shP
        if swL: slSw = True
        if swH: shSw = True
        pdL = pdl is not None and l < pdl and c > pdl
        pdH = pdh is not None and h > pdh and c < pdh
        if swL or pdL: lastBull = i
        if swH or pdH: lastBear = i
        hh = max(rows[k][2] for k in range(i - 3, i)) if i >= 3 else float("nan")
        ll = min(rows[k][3] for k in range(i - 3, i)) if i >= 3 else float("nan")
        lo5 = min(rows[k][3] for k in range(max(0, i - 4), i + 1)); hi5 = max(rows[k][2] for k in range(max(0, i - 4), i + 1))
        body, rng = abs(c - o), h - l
        lw, uw = min(o, c) - l, h - max(o, c)
        pinL = rng > 0 and lw >= 2 * body and lw >= 0.5 * rng and h - c <= rng / 3.0
        pinS = rng > 0 and uw >= 2 * body and uw >= 0.5 * rng and c - l <= rng / 3.0
        mssL = c > hh and c > o; mssS = c < ll and c < o
        rv = r14[i]
        ready = i >= 205 and rv == rv
        longOk = i - lastBull <= 5 and (pinL or mssL) and (rv < 70 if rv == rv else False)
        shortOk = i - lastBear <= 5 and (pinS or mssS) and (rv > 30 if rv == rv else False)
        rpL = max((c - (lo5 - 3 * pipS)) / pipS, 10); rpS = max(((hi5 + 3 * pipS) - c) / pipS, 10)
        okL = ready and longOk and rpL <= 100 and 300 / rpL >= 3
        okS = ready and shortOk and rpS <= 100 and 300 / rpS >= 3
        if okL and not okS: lastSetL = i
        if okS and not okL: lastSetS = i
        xUp = i >= 1 and e9[i] > e21[i] and e9[i - 1] <= e21[i - 1]
        xDn = i >= 1 and e9[i] < e21[i] and e9[i - 1] >= e21[i - 1]
        sig = 0
        if i >= 250 and atr[i] is not None and atr[i] > 0:
            if xUp and lastSetL >= i - 6: sig = 1
            elif xDn and lastSetS >= i - 6: sig = -1
        dist = 1.5 * atr[i] if atr[i] is not None else None
        sigSL = c - sig * dist if sig else None; sigTP = c + sig * 2.0 * dist if sig else None
        if tDir != 0:
            tNights += rollovers(rows[i - 1][0], t)
            px = None
            if tDir == 1:
                if l <= tSL: px = min(o, tSL)
                elif h >= tTP: px = tTP
            else:
                if h + s >= tSL: px = max(o + s, tSL)
                elif l + s <= tTP: px = tTP
            if px is not None:
                pips = tDir * (px - tEntry) / pipS - swp * tNights
                nT += 1; nW += pips > 0; sumR += pips / (tRisk / pipS); tDir = 0
        if tDir == 0 and sig != 0:
            tDir = sig; tEntry = c + s if sig == 1 else c; tSL, tTP = sigSL, sigTP
            tRisk = abs(tEntry - tSL); tNights = 0
        if sig: sigs.append((i, sig, sigSL, sigTP))
    return sigs, (nT, nW, sumR)
if __name__ == "__main__":
    import combos, sim15
    from common import PIPS, bars
    from sim15 import SPREAD
    tot_s = same_s = 0; rows_out = []
    for sym in PIPS:
        rows = bars(sym, 14400); pip = PIPS[sym]
        sigs, (nT, nW, sR) = v20_engine(rows, pip, SPREAD[sym], 0.5)
        ref = combos.c3(sym, 14400)
        A = {(i, d): (round(sl, 8), round(tp, 8)) for i, d, sl, tp in sigs}
        B = {(st[0], st[1]): (round(st[2], 8), round(st[3], 8)) for st in ref}
        same = sum(1 for k in A if B.get(k) == A[k]); tot_s += max(len(A), len(B)); same_s += same
        tr = sim15.run_sequential(rows, ref, pip, spread=SPREAD[sym], swap=0.5)
        rn, rw, rR = len(tr), sum(t["pips"] > 0 for t in tr), sum(t["R"] for t in tr)
        rows_out.append(f"{sym}: signals v20={len(A)} research={len(B)} identical={same} | scorecard v20 n={nT} w={nW} sumR={sR:+.4f} vs research n={rn} w={rw} sumR={rR:+.4f}")
    print("\n".join(rows_out)); print(f"TOTAL signals identical {same_s} of {tot_s}")
