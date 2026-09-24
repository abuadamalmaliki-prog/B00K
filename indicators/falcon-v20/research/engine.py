"""Bar-by-bar Python mirror of Falcon Sniper V2 (Pine v6) used for calibration.

Mirrors the Pine execution order on confirmed bars:
  core calcs -> trade management -> zone maintenance -> swings/structure/sweeps
  -> new zones -> factors/gates -> open trade.
"""
import csv, math
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
NA = float("nan")
def isna(x): return x is None or (isinstance(x, float) and math.isnan(x))


def load(path):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            rows.append((int(r["time"]), float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]), float(r["volume"])))
    return rows


def resample(rows, secs):
    out, cur = [], None
    for t, o, h, l, c, v in rows:
        b = t - t % secs
        if cur is None or cur[0] != b:
            if cur: out.append(tuple(cur))
            cur = [b, o, h, l, c, v]
        else:
            cur[2] = max(cur[2], h); cur[3] = min(cur[3], l); cur[4] = c; cur[5] += v
    if cur: out.append(tuple(cur))
    return out


# ── Pine-equivalent series helpers ──────────────────────────────────────────
class EMA:
    def __init__(s, n): s.n, s.a, s.buf, s.v = n, 2 / (n + 1), [], NA
    def __call__(s, x):
        if isna(s.v):
            s.buf.append(x)
            if len(s.buf) >= s.n: s.v = sum(s.buf[-s.n:]) / s.n
        else: s.v = s.a * x + (1 - s.a) * s.v
        return s.v

class RMA(EMA):
    def __init__(s, n): super().__init__(n); s.a = 1 / n


class Engine:
    def __init__(s, P):
        s.P = P

    def run(s, rows, htf_rows, pip, chart_sec):
        P = s.P
        n = len(rows)
        T = [r[0] for r in rows]; O = [r[1] for r in rows]; H = [r[2] for r in rows]
        L = [r[3] for r in rows]; C = [r[4] for r in rows]; V = [r[5] for r in rows]
        has_volume = sum(1 for v in V if v > 0) > n * 0.5

        # HTF bias from previous closed HTF bar (lookahead_on + [1]).
        hf, hs = EMA(P["htfFast"]), EMA(P["htfSlow"])
        htf_bias_by_bucket = {}
        prev = 0
        htf_secs = P["_htf_secs"]
        for t, o, h, l, c, v in htf_rows:
            ef, es = hf(c), hs(c)
            b = 0
            if not isna(es):
                b = 1 if c > ef and ef > es else -1 if c < ef and ef < es else 0
            htf_bias_by_bucket[t] = prev  # value visible during bucket t = bias of previous bucket
            prev = b
        # previous day high / low (UTC days)
        day_hl, pd_by_day, cur_day, dh, dl = {}, {}, None, None, None
        for t, h, l in zip(T, H, L):
            d = t // 86400
            if d != cur_day:
                if cur_day is not None: day_hl[cur_day] = (dh, dl)
                cur_day, dh, dl = d, h, l
            else: dh, dl = max(dh, h), min(dl, l)
        days = sorted(day_hl)
        prev_day = {}
        last = None
        for d in sorted(set(t // 86400 for t in T)):
            prev_day[d] = last
            if d in day_hl: last = day_hl[d]

        emaF, emaS = EMA(P["emaFast"]), EMA(P["emaSlow"])
        rsiU, rsiD = RMA(P["rsiLen"]), RMA(P["rsiLen"])
        mF, mS, mSig = EMA(12), EMA(26), EMA(9)
        atrR = RMA(14)
        volS = []
        rsi_hist, hist_hist = [], []

        sw = dict(sh=NA, shBar=None, shBroken=True, shSwept=False, sl=NA, slBar=None, slBroken=True, slSwept=False)
        structDir = 0
        lastBullChoch = lastBearChoch = -10**9
        lastBullSweep = lastBearSweep = -10**9
        lastBullFvgT = lastBearFvgT = lastBullObT = lastBearObT = -10**9
        zones = []  # dict(dir, kind, top, bottom, born)
        lastSig = None
        trade = None
        trades = []
        signals = []
        setups = []
        atrs = []
        for i in range(n):
            o, h, l, c = O[i], H[i], L[i], C[i]
            ef, es = emaF(c), emaS(c)
            ch = c - C[i - 1] if i else 0.0
            u, d = rsiU(max(ch, 0)) if i else NA, rsiD(max(-ch, 0)) if i else NA
            rsi = NA if isna(u) or isna(d) else (100.0 if d == 0 else 100 - 100 / (1 + u / d))
            ml = mF(c) - mS(c) if True else NA
            ms = mSig(ml) if not isna(ml) else NA
            hist = ml - ms if not isna(ms) else NA
            tr = h - l if i == 0 else max(h - l, abs(h - C[i - 1]), abs(l - C[i - 1]))
            atr = atrR(tr); atrs.append(atr)
            rsi_hist.append(rsi); hist_hist.append(hist)
            volS.append(V[i])
            volAvg = sum(volS[-20:]) / 20 if len(volS) >= 20 else NA
            relVol = V[i] / volAvg if has_volume and not isna(volAvg) and volAvg > 0 else NA

            # ── trade management ──
            ev = None
            if trade and trade["dir"] != 0 and i > trade["bar"]:
                s._manage(trade, o, h, l, pip)
                if trade["dir"] == 0:
                    trades.append(trade); trade = None

            # ── zone maintenance ──
            tBF = tBO = tSF = tSO = False
            keep = []
            for z in zones:
                dead = i - z["born"] > P["zoneMaxAge"]
                if not dead:
                    if z["dir"] == 1:
                        if c < z["bottom"]: dead = True
                        elif i > z["born"] and l <= z["top"]:
                            if z["kind"] == 0: tBF = True
                            else: tBO = True
                    else:
                        if c > z["top"]: dead = True
                        elif i > z["born"] and h >= z["bottom"]:
                            if z["kind"] == 0: tSF = True
                            else: tSO = True
                if not dead: keep.append(z)
            zones = keep
            if tBF: lastBullFvgT = i
            if tBO: lastBullObT = i
            if tSF: lastBearFvgT = i
            if tSO: lastBearObT = i

            # ── swings ──
            Lb, Rb = P["swLeft"], P["swRight"]
            if i >= Lb + Rb:
                p = i - Rb
                if all(H[p] > H[k] for k in range(p - Lb, p)) and all(H[p] > H[k] for k in range(p + 1, i + 1)):
                    sw.update(sh=H[p], shBar=p, shBroken=False, shSwept=False)
                if all(L[p] < L[k] for k in range(p - Lb, p)) and all(L[p] < L[k] for k in range(p + 1, i + 1)):
                    sw.update(sl=L[p], slBar=p, slBroken=False, slSwept=False)

            # ── structure breaks ──
            bullBreak = not isna(sw["sh"]) and not sw["shBroken"] and c > sw["sh"]
            bearBreak = not isna(sw["sl"]) and not sw["slBroken"] and c < sw["sl"]
            newZones = []
            if bullBreak:
                if structDir == -1: lastBullChoch = i
                structDir = 1; sw["shBroken"] = True
                if P["useOb"]:
                    nb = max(1, min(i - sw["slBar"] if sw["slBar"] is not None else 1, P["obLookback"]))
                    idx = min(range(1, nb + 1), key=lambda k: L[i - k])
                    bot, top = L[i - idx], H[i - idx]
                    if not isna(atr) and top - bot > P["obMaxAtr"] * atr: top = bot + P["obMaxAtr"] * atr
                    newZones.append(dict(dir=1, kind=1, top=top, bottom=bot, born=i))
            if bearBreak:
                if structDir == 1: lastBearChoch = i
                structDir = -1; sw["slBroken"] = True
                if P["useOb"]:
                    nb = max(1, min(i - sw["shBar"] if sw["shBar"] is not None else 1, P["obLookback"]))
                    idx = max(range(1, nb + 1), key=lambda k: H[i - k])
                    bot, top = L[i - idx], H[i - idx]
                    if not isna(atr) and top - bot > P["obMaxAtr"] * atr: bot = top - P["obMaxAtr"] * atr
                    newZones.append(dict(dir=-1, kind=1, top=top, bottom=bot, born=i))

            # ── sweeps ──
            day = T[i] // 86400
            pd = prev_day.get(day) if chart_sec < 86400 and P["usePd"] else None
            pdh, pdl = (pd if pd else (NA, NA))
            swL = not isna(sw["sl"]) and not sw["slBroken"] and not sw["slSwept"] and l < sw["sl"] and c > sw["sl"]
            swH = not isna(sw["sh"]) and not sw["shBroken"] and not sw["shSwept"] and h > sw["sh"] and c < sw["sh"]
            if swL: sw["slSwept"] = True
            if swH: sw["shSwept"] = True
            bullSweep = swL or (not isna(pdl) and l < pdl and c > pdl)
            bearSweep = swH or (not isna(pdh) and h > pdh and c < pdh)
            if bullSweep: lastBullSweep = i
            if bearSweep: lastBearSweep = i

            # ── FVGs ──
            if P["useFvg"] and i >= 2 and not isna(atr):
                if l > H[i - 2] and l - H[i - 2] >= P["fvgMinAtr"] * atr and C[i - 1] > O[i - 1]:
                    newZones.append(dict(dir=1, kind=0, top=l, bottom=H[i - 2], born=i))
                if h < L[i - 2] and L[i - 2] - h >= P["fvgMinAtr"] * atr and C[i - 1] < O[i - 1]:
                    newZones.append(dict(dir=-1, kind=0, top=L[i - 2], bottom=h, born=i))
            zones.extend(newZones)
            # cap per side
            for dd in (1, -1):
                side = [z for z in zones if z["dir"] == dd]
                if len(side) > P["maxZones"]:
                    drop = side[: len(side) - P["maxZones"]]
                    zones = [z for z in zones if z not in drop]

            # ── factors ──
            warm = max(P["emaSlow"], 35, 14 * 2) + 5
            ready = i >= warm and not isna(es) and not isna(rsi) and not isna(hist) and not isna(atr) and atr > 0
            if not ready: continue
            bucket = T[i] - T[i] % htf_secs
            htfb = htf_bias_by_bucket.get(bucket, 0)
            rng_ok = not isna(sw["sh"]) and not isna(sw["sl"]) and sw["sh"] > sw["sl"]
            eq = (sw["sh"] + sw["sl"]) / 2 if rng_ok else NA
            rng = sw["sh"] - sw["sl"] if rng_ok else NA
            ny = datetime.fromtimestamp(T[i], timezone.utc).astimezone(NY)
            mins = ny.hour * 60 + ny.minute
            inKz = (120 <= mins < 300) or (420 <= mins < 600)
            kzOk = (not P["useKz"]) or chart_sec >= 14400 or inKz
            volOk = isna(relVol) or relVol >= P["volMult"]
            rsiLow5 = min(x for x in rsi_hist[-5:])
            rsiHigh5 = max(x for x in rsi_hist[-5:])
            body = abs(c - o)
            hhPrev = max(H[i - P["mssLen"]:i]); llPrev = min(L[i - P["mssLen"]:i])

            engL = c > o and C[i - 1] < O[i - 1] and c >= O[i - 1] and o <= C[i - 1]
            engS = c < o and C[i - 1] > O[i - 1] and c <= O[i - 1] and o >= C[i - 1]
            rngb = h - l
            lw, uw = min(o, c) - l, h - max(o, c)
            pinL = rngb > 0 and lw >= 2 * body and lw >= 0.5 * rngb and (h - c) <= rngb / 3
            pinS = rngb > 0 and uw >= 2 * body and uw >= 0.5 * rngb and (c - l) <= rngb / 3
            mssL = c > hhPrev and c > o
            mssS = c < llPrev and c < o
            tm = P.get("trigMode", "any")
            if tm == "pin": trigL, trigS = pinL, pinS
            elif tm == "pinmss": trigL, trigS = pinL or mssL, pinS or mssS
            else: trigL, trigS = engL or pinL or mssL, engS or pinS or mssS

            oteL = rng_ok and l <= sw["sh"] - 0.618 * rng
            oteS = rng_ok and h >= sw["sl"] + 0.618 * rng
            sweepRecL = i - lastBullSweep <= P["sweepWindow"]
            sweepRecS = i - lastBearSweep <= P["sweepWindow"]
            fvgRecL, fvgRecS = i - lastBullFvgT <= P["poiWindow"], i - lastBearFvgT <= P["poiWindow"]
            obRecL, obRecS = i - lastBullObT <= P["poiWindow"], i - lastBearObT <= P["poiWindow"]
            poiL = fvgRecL or obRecL or sweepRecL or oteL
            poiS = fvgRecS or obRecS or sweepRecS or oteS
            if P.get("requireSweep"): poiL, poiS = sweepRecL, sweepRecS
            if P.get("noOte"): poiL, poiS = poiL and not oteL, poiS and not oteS
            if P.get("noDisc"): poiL, poiS = poiL and not (rng_ok and c < eq), poiS and not (rng_ok and c > eq)

            fL = [htfb == 1, structDir == 1 or i - lastBullChoch <= P["chochWindow"], rng_ok and c < eq, oteL, sweepRecL, fvgRecL, obRecL,
                  body >= P["dispAtr"] * atr, rsiLow5 <= 40 and rsi > rsi_hist[-2], hist > hist_hist[-2], ef > es, kzOk, volOk]
            fS = [htfb == -1, structDir == -1 or i - lastBearChoch <= P["chochWindow"], rng_ok and c > eq, oteS, sweepRecS, fvgRecS, obRecS,
                  body >= P["dispAtr"] * atr, rsiHigh5 >= 60 and rsi < rsi_hist[-2], hist < hist_hist[-2], ef < es, kzOk, volOk]
            scL, scS = sum(fL), sum(fS)
            g = P["htfGate"]
            htfOkL = g == "Off" or (g == "Strict" and htfb == 1) or (g == "Loose" and htfb != -1)
            htfOkS = g == "Off" or (g == "Strict" and htfb == -1) or (g == "Loose" and htfb != 1)
            kzGateOk = (not P["kzGate"]) or kzOk
            cd = lastSig is None or i - lastSig >= P["cooldown"]

            # risk
            def plan(dr):
                if dr == 1:
                    raw = min(L[i - P["slLookback"] + 1: i + 1]) - P["slBufPips"] * pip
                    riskp = (c - raw) / pip
                else:
                    raw = max(H[i - P["slLookback"] + 1: i + 1]) + P["slBufPips"] * pip
                    riskp = (raw - c) / pip
                riskp = max(riskp, P["minSlPips"])
                if P["tgtMode"] == "Pips":
                    tps = [P["tp1Pips"], P["tp2Pips"], P["tp3Pips"]]
                else:
                    tps = [riskp * P["rr1"], riskp * P["rr2"], riskp * P["rr3"]]
                ok = riskp <= P["maxSlPips"] and tps[2] / riskp >= P["minRR"]
                return ok, riskp, tps

            longSig = shortSig = False
            if P.get("raw"): cd = True; trade = None
            if cd and ready:
                if htfOkL and poiL and trigL and rsi < 70 and scL >= P["minScore"] and kzGateOk and (trade is None or (trade["dir"] != 1 and not P.get("noReverse"))):
                    ok, rp, tps = plan(1)
                    longSig = ok
                if htfOkS and poiS and trigS and rsi > 30 and scS >= P["minScore"] and kzGateOk and (trade is None or (trade["dir"] != -1 and not P.get("noReverse"))):
                    ok2, rp2, tps2 = plan(-1)
                    shortSig = ok2
            if longSig and shortSig:  # both sides on one bar
                if P.get("bothSkip"): longSig = shortSig = False
                elif scS > scL: longSig = False
                else: shortSig = False
            if longSig or shortSig:
                dr = 1 if longSig else -1
                if P.get("raw"):
                    ok, rp, tps = plan(dr)
                    setups.append((i, dr, c - dr * rp * pip, rp)); continue
                if trade is not None and trade["dir"] == -dr:
                    s._close(trade, c, "rev", pip); trades.append(trade); trade = None
                ok, rp, tps = plan(dr)
                trade = dict(dir=dr, bar=i, entry=c, risk=rp * pip, sl=c - dr * rp * pip,
                             tp=[c + dr * x * pip for x in tps], hit=[False] * 3, rem=1.0, r=0.0, pips=0.0,
                             time=T[i], score=scL if dr == 1 else scS, riskPips=rp, exit=None, i=i, sweepPd=bool((not isna(pdl) and l < pdl and c > pdl) if dr == 1 else (not isna(pdh) and h > pdh and c < pdh)), fac=list(fL if dr == 1 else fS), trig=(engL, pinL, mssL) if dr == 1 else (engS, pinS, mssS), htfb=htfb)
                lastSig = i
                signals.append(i)
        if trade is not None:
            trade["open"] = True
        if P.get("raw"): return setups, signals, atrs
        return trades, signals, atrs

    def _book(s, t, k, pip):
        part = (1 / 3) if s.P["partials"] else 0.0
        tp = t["tp"][k]
        t["r"] += part * (tp - t["entry"]) / t["risk"] * t["dir"]
        t["pips"] += part * (tp - t["entry"]) * t["dir"] / pip
        t["rem"] -= part

    def _close(s, t, px, why, pip=None):
        pip = pip if pip is not None else s._pip
        t["r"] += t["rem"] * (px - t["entry"]) / t["risk"] * t["dir"]
        t["pips"] += t["rem"] * (px - t["entry"]) * t["dir"] / pip
        t["rem"] = 0.0; t["dir"] = 0; t["exit"] = why

    def _manage(s, t, o, h, l, pip):
        s._pip = pip
        d = t["dir"]
        if (l <= t["sl"]) if d == 1 else (h >= t["sl"]):
            px = min(o, t["sl"]) if d == 1 else max(o, t["sl"])
            s._close(t, px, "stop", pip); return
        for k in range(2):
            if not t["hit"][k] and ((h >= t["tp"][k]) if d == 1 else (l <= t["tp"][k])):
                t["hit"][k] = True; s._book(t, k, pip)
                if k == 0 and s.P["beAfterTp1"]: t["sl"] = t["entry"]
                if k == 1 and s.P["trailTp2"]: t["sl"] = t["tp"][0]
        if (h >= t["tp"][2]) if d == 1 else (l <= t["tp"][2]):
            t["hit"][2] = True
            s._close(t, t["tp"][2], "tp3", pip)


DEFAULTS = dict(
    htfFast=50, htfSlow=200, emaFast=50, emaSlow=200, rsiLen=14,
    swLeft=5, swRight=3, obLookback=20, obMaxAtr=1.5, useOb=True, useFvg=True, fvgMinAtr=0.25,
    zoneMaxAge=150, maxZones=8, poiWindow=3, sweepWindow=5, chochWindow=20, mssLen=3, dispAtr=0.5,
    usePd=True, useKz=True, kzGate=True, volMult=1.2,
    htfGate="Off", minScore=0, cooldown=3, requireSweep=True, trigMode="pinmss",
    tgtMode="Pips", tp1Pips=50, tp2Pips=150, tp3Pips=300, rr1=2, rr2=4, rr3=6,
    slLookback=5, slBufPips=3, minSlPips=10, maxSlPips=100, minRR=3.0,
    partials=True, beAfterTp1=True, trailTp2=True,
)
