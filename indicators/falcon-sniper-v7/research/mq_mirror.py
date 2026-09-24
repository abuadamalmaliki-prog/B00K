"""Line-by-line transliteration of FalconSniperV7.mq5 EvaluateSetups(), for parity testing
against the research engine (engine.py raw setups). PD levels use previous UTC day like engine.py."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
NY = ZoneInfo("America/New_York")
def mq_setups(rows, rsi, pip, tf_sec, P):
    out = []
    shPrice = slPrice = 0.0; shBar = slBar = -1
    shBroken = slBroken = True; shSwept = slSwept = False
    lastBullSweep = lastBearSweep = -1000000
    intraday = tf_sec < 4 * 3600
    usePd = P["usePd"] and tf_sec < 86400
    L, R = P["swLeft"], P["swRight"]
    # previous UTC day high/low (same as engine.py)
    day_hl, cur, dh, dl = {}, None, None, None
    for t, o, h, l, c, v in rows:
        d = t // 86400
        if d != cur:
            if cur is not None: day_hl[cur] = (dh, dl)
            cur, dh, dl = d, h, l
        else: dh, dl = max(dh, h), min(dl, l)
    prev_day, last = {}, None
    for d in sorted(set(t // 86400 for t, *_ in rows)):
        prev_day[d] = last
        if d in day_hl: last = day_hl[d]
    for i in range(len(rows)):
        t, o, h, l, c, v = rows[i]
        if i >= L + R:
            p = i - R; isH = isL = True
            for k in range(p - L, i + 1):
                if k == p: continue
                if rows[k][2] >= rows[p][2]: isH = False
                if rows[k][3] <= rows[p][3]: isL = False
                if not (isH or isL): break
            if isH: shPrice, shBar, shBroken, shSwept = rows[p][2], p, False, False
            if isL: slPrice, slBar, slBroken, slSwept = rows[p][3], p, False, False
        if shBar >= 0 and not shBroken and c > shPrice: shBroken = True
        if slBar >= 0 and not slBroken and c < slPrice: slBroken = True
        swL = slBar >= 0 and not slBroken and not slSwept and l < slPrice and c > slPrice
        swH = shBar >= 0 and not shBroken and not shSwept and h > shPrice and c < shPrice
        if swL: slSwept = True
        if swH: shSwept = True
        pdL = pdH = False
        if usePd:
            pd = prev_day.get(t // 86400)
            if pd:
                pdh, pdl = pd
                pdL = l < pdl and c > pdl; pdH = h > pdh and c < pdh
        if swL or pdL: lastBullSweep = i
        if swH or pdH: lastBearSweep = i
        if i < 205 or i < P["mssLen"] or i < P["slLookback"] or rsi[i] is None or rsi[i] != rsi[i]: continue
        body, rng = abs(c - o), h - l
        lw, uw = min(o, c) - l, h - max(o, c)
        pinL = rng > 0 and lw >= 2 * body and lw >= 0.5 * rng and h - c <= rng / 3.0
        pinS = rng > 0 and uw >= 2 * body and uw >= 0.5 * rng and c - l <= rng / 3.0
        hh, ll = rows[i - 1][2], rows[i - 1][3]
        for k in range(i - P["mssLen"], i):
            hh = max(hh, rows[k][2]); ll = min(ll, rows[k][3])
        mssL = c > hh and c > o; mssS = c < ll and c < o
        trigL, trigS = pinL or mssL, pinS or mssS
        kzOk = True
        if P["useKz"] and intraday:
            ny = datetime.fromtimestamp(t, timezone.utc).astimezone(NY)
            kzOk = (2 <= ny.hour < 5) or (7 <= ny.hour < 10)
        if not kzOk: continue
        sweepL = i - lastBullSweep <= P["sweepWindow"]; sweepS = i - lastBearSweep <= P["sweepWindow"]
        longOk = sweepL and trigL and rsi[i] < 70; shortOk = sweepS and trigS and rsi[i] > 30
        if not longOk and not shortOk: continue
        lo, hi = l, h
        for k in range(i - P["slLookback"] + 1, i + 1):
            lo = min(lo, rows[k][3]); hi = max(hi, rows[k][2])
        rpL = max((c - (lo - P["slBufPips"] * pip)) / pip, P["minSlPips"])
        rpS = max(((hi + P["slBufPips"] * pip) - c) / pip, P["minSlPips"])
        okL = longOk and rpL <= P["maxSlPips"] and P["tp3Pips"] / rpL >= P["minRR"]
        okS = shortOk and rpS <= P["maxSlPips"] and P["tp3Pips"] / rpS >= P["minRR"]
        if okL and okS: continue   # ambiguous bar: both sides qualify
        if not okL and not okS: continue
        out.append((i, 1 if okL else -1, c - rpL * pip if okL else c + rpS * pip, rpL if okL else rpS))
    return out
