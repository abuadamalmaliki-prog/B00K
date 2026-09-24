import pickle, os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from common import *
NY = ZoneInfo("America/New_York")
def build(tfs=(3600, 14400), **over):
    pool = []
    for tf in tfs:
        for sym in PIPS:
            rows, tr = run(sym, tf, **over)
            pip = PIPS[sym]
            mid = rows[len(rows) // 2][0]
            # daily ranges for "room" features (previous 20 completed UTC days)
            days = resample(rows if tf == 3600 else bars(sym, 3600), 86400)
            dr = {}
            acc = []
            for t0, o, h, l, c, v in days:
                dr[t0] = sum(acc[-20:]) / len(acc[-20:]) if acc else None
                acc.append((h - l) / pip)
            for t in tr:
                out, mfe = path(rows, t, pip)
                d = 1 if t["tp"][0] > t["entry"] else -1
                ny = datetime.fromtimestamp(t["time"], timezone.utc).astimezone(NY)
                adr = dr.get(t["time"] - t["time"] % 86400)
                R = (300 / t["riskPips"]) if out == "tp" else (-1.0 if out == "sl" else 0.0)
                f = t["fac"]
                pool.append(dict(sym=sym, tf=tf, half=int(t["time"] >= mid), dir=d, out=out, R=R, mfe=mfe, sl=t["riskPips"],
                                 adr=adr, reach=(300 / adr if adr else None), slAdr=(t["riskPips"] / adr if adr else None),
                                 htf=f[0], struct=f[1], disc=f[2], ote=f[3], fvg=f[5], ob=f[6], disp=f[7], rsiT=f[8], macd=f[9], ema=f[10],
                                 score=t["score"], pin=t["trig"][1], mss=t["trig"][2], pd=t["sweepPd"], hour=ny.hour, dow=ny.weekday(),
                                 htfb=t["htfb"] * d))
    return pool
if __name__ == "__main__":
    pool = build()
    pickle.dump(pool, open("pool.pkl", "wb"))
    print("pool", len(pool))
