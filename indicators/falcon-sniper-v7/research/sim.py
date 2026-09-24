"""Common trade simulator with a JustMarkets-Standard-like cost model.

Chart prices are treated as BID. Ask = bid + spread.
  Long : enter at ask (close + spread); stop/target/BE judged on bid.
  Short: enter at bid (close); stop/target/BE judged on ask (bid + spread).
Stop-first when a bar touches both stop and target; gapped stops fill at the open.
Swap: `swap` pips charged per rollover (17:00 New York), Wednesday counts 3.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
NY = ZoneInfo("America/New_York")
_ny_cache = {}
def ny(t):
    v = _ny_cache.get(t)
    if v is None:
        v = datetime.fromtimestamp(t, timezone.utc).astimezone(NY); _ny_cache[t] = v
    return v

def rollovers(t0, t1):
    """Swap nights between two timestamps (rollover at 17:00 New York, Wednesday x3)."""
    n = 0
    a, b = ny(t0), ny(t1)
    from datetime import timedelta
    d = a.replace(hour=17, minute=0, second=0, microsecond=0)
    if d <= a: d += timedelta(days=1)
    while d <= b:
        wd = d.weekday()
        if wd < 5: n += 3 if wd == 2 else 1
        d += timedelta(days=1)
    return n

def walk(rows, i, d, sl, pip, target=300.0, be=150.0, spread=0.0, swap=0.0, weekend_flat=False, max_bars=None):
    """Simulate one trade entered at the close of bar i. Returns dict or None if no exit (data end)."""
    s = spread * pip
    c = rows[i][4]
    entry = c + s if d == 1 else c
    risk = (entry - sl) if d == 1 else (sl - entry)
    if risk <= 0: return None
    tp = entry + d * target * pip
    stop = sl
    be_on = False
    end = len(rows) if max_bars is None else min(len(rows), i + 1 + max_bars)
    for k in range(i + 1, end):
        t, o, h, l, cl, v = rows[k]
        if d == 1:
            if l <= stop:
                px = min(o, stop); why = "be" if be_on else "sl"; break
            if h >= tp:
                px = tp; why = "tp"; break
            if be is not None and h - entry >= be * pip and not be_on:
                stop = entry; be_on = True
        else:
            if h + s >= stop:
                px = max(o + s, stop); why = "be" if be_on else "sl"; break
            if l + s <= tp:
                px = tp; why = "tp"; break
            if be is not None and entry - (l + s) >= be * pip and not be_on:
                stop = entry; be_on = True
        if weekend_flat:
            nt = ny(t)
            # last H1/H4 bar starting on Friday at or after 12:00 New York -> flat at its close
            if nt.weekday() == 4 and nt.hour >= 12 and (k + 1 >= len(rows) or ny(rows[k + 1][0]).weekday() != 4):
                px = cl if d == 1 else cl + s; why = "wknd"; break
    else:
        return None
    pips = d * (px - entry) / pip - swap * rollovers(rows[i][0], rows[k][0])
    return dict(i=i, exit_i=k, dir=d, why=why, pips=pips, R=pips / (risk / pip), riskPips=risk / pip, time=rows[i][0])

def run_sequential(rows, setups, pip, cooldown=3, **kw):
    """Take setups one at a time (flat only), cooldown bars since the last taken entry."""
    trades, busy_until, last = [], -1, -10**9
    for (i, d, sl, rp) in setups:
        if i < busy_until or i - last < cooldown: continue
        tr = walk(rows, i, d, sl, pip, **kw)
        if tr is None: break
        trades.append(tr); busy_until = tr["exit_i"]; last = i
    return trades
