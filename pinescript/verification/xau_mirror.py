"""Line-by-line Python mirror of xauusd_asian_range_breakout.pine.

Usage: python3 xau_mirror.py candles.json out.json [tpR] [costBp]
candles: list of {open, high, low, close, openTime (UTC ms)}.
Only the default session settings (18:30 / 03:00 / 08:20 / 13:30 New York) are mirrored.
"""
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")


def rel_of(h, m):
    return (h * 60 + m - 1080 + 1440) % 1440


REL_RS, REL_RE, REL_EE, REL_EX = rel_of(18, 30), rel_of(3, 0), rel_of(8, 20), rel_of(13, 30)


def run(c, tpR=3.0, costBp=1.0, tf_min=None):
    n = len(c)
    if tf_min is None:
        tf_min = (c[1]["openTime"] - c[0]["openTime"]) / 60000.0 if n > 1 else 5.0
    st = dict(rHi=None, rLo=None, rCnt=0, dayDone=False, planned=False, pos=0, entry=None, sl=None, tp=None,
              risk=None, entryBar=None, nTrades=0, nWin=0, nTP=0, nSL=0, nTime=0, sumR=0.0, peakR=0.0, maxDD=0.0)
    out = {k: [] for k in ("plan", "buy", "sell", "tp", "sl", "time", "exitPx", "exitR", "entry", "tpPx", "slPx")}
    prev_key = None
    for i, x in enumerate(c):
        t = datetime.fromtimestamp(x["openTime"] / 1000, tz=timezone.utc)
        ny = t.astimezone(NY)
        rel = rel_of(ny.hour, ny.minute)
        t6 = (t + timedelta(hours=6)).astimezone(NY)
        key = t6.year * 10000 + t6.month * 100 + t6.day
        new_day = key != prev_key
        o, h, l, cl = x["open"], x["high"], x["low"], x["close"]
        ev = dict(plan=False, buy=False, sell=False, tp=False, sl=False, time=False)
        exit_px = None
        # 1
        if new_day:
            if st["pos"] != 0:
                exit_px = c[i - 1]["close"]
                ev["time"] = True
            st.update(rHi=None, rLo=None, rCnt=0, dayDone=False, planned=False)
        # 2
        if st["pos"] != 0 and not ev["time"] and i > st["entryBar"]:
            p = st["pos"]
            if rel >= REL_EX:
                exit_px = o; ev["time"] = True
            elif (p == 1 and l <= st["sl"]) or (p == -1 and h >= st["sl"]):
                exit_px = min(o, st["sl"]) if p == 1 else max(o, st["sl"]); ev["sl"] = True
            elif (p == 1 and h >= st["tp"]) or (p == -1 and l <= st["tp"]):
                exit_px = max(o, st["tp"]) if p == 1 else min(o, st["tp"]); ev["tp"] = True
        # 3
        if REL_RS <= rel < REL_RE:
            st["rHi"] = h if st["rHi"] is None else max(st["rHi"], h)
            st["rLo"] = l if st["rLo"] is None else min(st["rLo"], l)
            st["rCnt"] += 1
        range_ok = st["rCnt"] >= 0.8 * (REL_RE - REL_RS) / tf_min and st["rHi"] is not None and st["rHi"] > st["rLo"]
        # 4
        last_range_bar = REL_RS <= rel < REL_RE and rel + tf_min >= REL_RE
        first_window_bar = REL_RE <= rel < REL_EE
        if not st["planned"] and not st["dayDone"] and range_ok and (last_range_bar or first_window_bar):
            st["planned"] = True; ev["plan"] = True
        # 5
        if not st["dayDone"] and st["pos"] == 0 and REL_RE <= rel < REL_EE and range_ok:
            up, dn = h > st["rHi"], l < st["rLo"]
            if up and dn:
                st["dayDone"] = True
            elif up or dn:
                st["dayDone"] = True
                side = 1 if up else -1
                entry = max(o, st["rHi"]) if side == 1 else min(o, st["rLo"])
                sl = st["rLo"] if side == 1 else st["rHi"]
                risk = abs(entry - sl)
                st.update(entry=entry, sl=sl, risk=risk, tp=entry + side * tpR * risk, entryBar=i)
                st["nTrades"] += 1
                ev["buy"], ev["sell"] = side == 1, side == -1
                if (side == 1 and l <= sl) or (side == -1 and h >= sl):
                    exit_px = sl; ev["sl"] = True
                elif (side == 1 and cl >= st["tp"]) or (side == -1 and cl <= st["tp"]):
                    exit_px = st["tp"]; ev["tp"] = True
                st["pos"] = side
        # 6
        exit_r = None
        if (ev["tp"] or ev["sl"] or ev["time"]) and st["pos"] != 0:
            p = st["pos"]
            exit_r = p * (exit_px - st["entry"]) / st["risk"] - costBp / 10000.0 * st["entry"] / st["risk"]
            st["sumR"] += exit_r
            st["nWin"] += exit_r > 0
            st["nTP"] += ev["tp"]; st["nSL"] += ev["sl"]; st["nTime"] += ev["time"]
            st["peakR"] = max(st["peakR"], st["sumR"])
            st["maxDD"] = max(st["maxDD"], st["peakR"] - st["sumR"])
            st["pos"] = 0
        for k in ("plan", "buy", "sell", "tp", "sl", "time"):
            out[k].append(ev[k])
        out["exitPx"].append(exit_px if exit_r is not None else None)
        out["exitR"].append(exit_r)
        on = st["pos"] != 0
        out["entry"].append(st["entry"] if on else None)
        out["tpPx"].append(st["tp"] if on else None)
        out["slPx"].append(st["sl"] if on else None)
        prev_key = key
    stats = {k: st[k] for k in ("nTrades", "nWin", "nTP", "nSL", "nTime", "sumR", "maxDD")}
    return out, stats


if __name__ == "__main__":
    candles = json.load(open(sys.argv[1]))
    tpR = float(sys.argv[3]) if len(sys.argv) > 3 else 3.0
    cost = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
    out, stats = run(candles, tpR, cost)
    json.dump({"plots": out, "stats": stats}, open(sys.argv[2], "w"))
    print(json.dumps(stats))
