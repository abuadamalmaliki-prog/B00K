"""5-day challenge simulator.

Windows: start at every weekday rollover (17:00 New York), last 5 trading days.
Portfolio: all symbols' setups merged by time; one open position at a time (phone-friendly).
Sizing: risk `f` of current balance per trade in 0.01-lot steps (JustMarkets Standard: min 0.01),
        margin at 1:3000 with x3 safety; if the 0.01-lot minimum risks more than `cap` of the
        balance the trade is skipped.
Rules: stop trading once balance >= target (goal locked) or balance <= floor.
Open trades are closed at the close of the window's last bar.
"""
import math, bisect
from datetime import datetime, timezone, timedelta
from common import PIPS, bars
from sim15 import trade, SPREAD, SWAP
from sim import ny, NY

def last(sym): return bars(sym, 3600)[-1][4]
def pip_value_margin(sym, lev=3000, safety=3.0):
    eu, gu, au, uj, uc = last("EURUSD"), last("GBPUSD"), last("AUDUSD"), last("USDJPY"), last("USDCAD")
    px = last(sym)
    v, notional = {"EURUSD": (10, 1e5 * eu), "GBPUSD": (10, 1e5 * gu), "AUDUSD": (10, 1e5 * au), "NZDUSD": (10, 1e5 * px),
                   "USDJPY": (1000 / uj, 1e5), "USDCAD": (10 / uc, 1e5), "EURJPY": (1000 / uj, 1e5 * eu),
                   "GBPJPY": (1000 / uj, 1e5 * gu), "GBPAUD": (10 * au, 1e5 * gu), "XAUUSD": (10, 100 * px),
                   "XAGUSD": (50, 5000 * px)}[sym]
    return v, notional / lev * safety

def windows(tf=3600, sym="EURUSD", days=5):
    """(start, end) unix pairs: start at each weekday 17:00 NY, end after `days` trading days."""
    rows = bars(sym, tf)
    t0, t1 = rows[0][0], rows[-1][0]
    d = datetime.fromtimestamp(t0, timezone.utc).astimezone(NY).replace(hour=17, minute=0, second=0, microsecond=0) + timedelta(days=1)
    out = []
    while True:
        start = d
        if start.weekday() in (4, 5):          # Fri/Sat 17:00 are not trading-day starts
            d += timedelta(days=1); continue
        k, e = 0, start
        while k < days:
            e += timedelta(days=1)
            if e.weekday() not in (5, 6):      # a trading day ends at 17:00 NY Mon-Fri
                k += 1
        s_ts, e_ts = int(start.timestamp()), int(e.timestamp())
        if e_ts > t1: break
        if s_ts >= t0 + 30 * 86400:            # leave indicator warm-up
            out.append((s_ts, e_ts))
        d += timedelta(days=1)
    return out

class Book:
    def __init__(s, setups_by_sym, tf=3600):
        s.rows = {sym: bars(sym, tf) for sym in setups_by_sym}
        s.times = {sym: [r[0] for r in s.rows[sym]] for sym in s.rows}
        s.events = sorted((s.rows[sym][st[0]][0], sym, st) for sym, sts in setups_by_sym.items() for st in sts)
        s.ev_times = [e[0] for e in s.events]
        s.spec = {sym: pip_value_margin(sym) for sym in s.rows}
        s.buf = 0.0
        s.ladder = None

    def run_window(s, start, end, f, target, floor=0.0, cap=0.5, start_bal=30.0, max_trades=99):
        bal, busy_until, n = start_bal, start, 0
        lo = bisect.bisect_left(s.ev_times, start)
        hi = bisect.bisect_left(s.ev_times, end)
        for t, sym, st in s.events[lo:hi]:
            if t < busy_until or bal >= target or bal <= floor or n >= max_trades: continue
            rows, pip = s.rows[sym], PIPS[sym]
            last_i = bisect.bisect_left(s.times[sym], end) - 1       # last bar that opens before the window end
            if last_i <= st[0]: continue
            cap_bars = last_i - st[0]
            mb = min(st[4], cap_bars) if len(st) > 4 and st[4] is not None else cap_bars
            tr = trade(rows, (st[0], st[1], st[2], st[3], mb), pip, SPREAD[sym], SWAP)
            if tr is None: continue
            V, M = s.spec[sym]
            per_lot_risk = tr["riskPips"] * V
            if f == "bold":
                # size so that one win (planned net of `buf` pips of costs) lands on the target
                # (or on the next ladder milestone), never risking more than `cap` of the balance
                aim = target
                if s.ladder:
                    aim = next((m for m in s.ladder if m > bal), target)
                per_lot_win = max(tr["rewardPips"] - s.buf, 0.1) * V
                lots = math.ceil((aim - bal) / per_lot_win / 0.01 - 1e-9) * 0.01
                lots = min(lots, math.floor(cap * bal / per_lot_risk / 0.01 + 1e-9) * 0.01)
                if lots < 0.01: continue
            else:
                lots = math.floor(bal * f / per_lot_risk / 0.01 + 1e-9) * 0.01
                if lots < 0.01:
                    if 0.01 * per_lot_risk <= cap * bal: lots = 0.01
                    else: continue
            lots = min(lots, math.floor(bal / M / 0.01 + 1e-9) * 0.01)
            if lots < 0.01: continue
            bal += lots * V * tr["pips"]
            n += 1
            busy_until = rows[tr["exit_i"]][0] + 1
        return bal, n

    def evaluate(s, f, target, floor=0.0, cap=0.5, start_bal=30.0, wins=None):
        wins = wins or windows()
        res = [s.run_window(a, b, f, target, floor, cap, start_bal) for a, b in wins]
        n = len(res)
        return dict(windows=n, p_goal=sum(b >= target for b, _ in res) / n, p_bust=sum(b < 0.5 * start_bal for b, _ in res) / n,
                    median=sorted(b for b, _ in res)[n // 2], mean=sum(b for b, _ in res) / n,
                    trades=sum(k for _, k in res) / n)
