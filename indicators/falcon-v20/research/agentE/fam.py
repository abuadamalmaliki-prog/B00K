"""agentE families (time/session/calendar, volatility, carry). Each cfg -> (name, gen(sym)->setups, swapf|None).
All hours are New York (sim.ny) of the H1 BAR OPEN; 'enter at HH:00' = close of the bar opening at HH-1."""
import math
from zoneinfo import ZoneInfo
from datetime import datetime, timezone
from lib import ctx, ALL
LON = ZoneInfo("Europe/London")
BIG = 50.0  # far target multiple of risk = "no target" (time/stop exits only)

def base_quote(sym): return sym[:3], sym[3:]

def atr_stop(c, i, d, n_hold, k=1.5, tp_mult=None):
    """Entry-referenced ATR stop: 1.5 * sqrt(hold hours) * ATR24(H1). tp far unless given."""
    e = c["rows"][i][4] + (c["spread"] * c["pip"] if d == 1 else 0)
    r = k * math.sqrt(n_hold) * c["atr"][i]
    return e - d * r, e + d * (tp_mult if tp_mult else BIG) * r

# ---------------- F1 time-of-day: "the currency whose market is opening" ----------------
OPENS = {3: {"EUR", "GBP"}, 8: {"USD", "CAD"}, 19: {"JPY", "AUD", "NZD"}}
def f1(H, N, sgn):
    """At H:00 NY the listed currencies' home market opens. sgn=+1: SELL the opening currency
    (home-hours depreciation, Breedon-Ranaldo); sgn=-1: BUY it (e.g. H=8,sgn=-1 = buy USD at NY open). Hold N h."""
    def gen(sym):
        c = ctx(sym); b, q = base_quote(sym); op = OPENS[H]
        v = (1 if q in op else 0) - (1 if b in op else 0)   # quote opening -> quote weakens -> long base
        if v == 0: return []
        d0 = sgn * v; out = []
        for i in range(30, len(c["rows"]) - N - 1):
            t = c["ny"][i]
            if t.hour != (H - 1) % 24 or t.weekday() == 5 or c["atr"][i] is None: continue
            if H != 19 and t.weekday() == 6: continue
            sl, tp = atr_stop(c, i, d0, N); out.append((i, d0, sl, tp, N))
        return out
    return gen

# ---------------- F2 day-of-week ----------------
def f2(kind, sgn):
    """kind: 'tue' = Monday FX-day move faded/followed over Tuesday (enter Mon 17:00 NY, hold 24 bars);
    'tuebig' = same but only if |Mon move| > 0.5*avgRange20; 'fri10'/'fri12' = week-to-date move
    (Mon FX-day open -> entry) faded/followed from Fri 10:00/12:00 NY until Friday's last bar.
    sgn=-1 fade, +1 follow."""
    def gen(sym):
        c = ctx(sym); rows, days, out = c["rows"], c["days"], []
        for j, dd in enumerate(days):
            if dd["avgR20"] is None: continue
            wd = dd["key"].weekday()
            if kind in ("tue", "tuebig") and wd == 0:
                mv = dd["c"] - dd["o"]
                if mv == 0 or (kind == "tuebig" and abs(mv) < 0.5 * dd["avgR20"]): continue
                i = dd["last"]; d = sgn * (1 if mv > 0 else -1)
                if c["atr"][i] is None: continue
                sl, tp = atr_stop(c, i, d, 24); out.append((i, d, sl, tp, 24))
            if kind in ("fri10", "fri12") and wd == 4:
                hh = 9 if kind == "fri10" else 11
                ii = [k for k in range(dd["first"], dd["last"] + 1) if c["ny"][k].hour == hh]
                if not ii: continue
                i = ii[0]; n = dd["last"] - i
                if n < 2: continue
                mon = [x for x in days[max(0, j - 5):j] if x["key"].weekday() == 0 and (dd["key"] - x["key"]).days == 4]
                if not mon: continue
                mv = rows[i][4] - mon[0]["o"]
                if mv == 0: continue
                d = sgn * (1 if mv > 0 else -1)
                sl, tp = atr_stop(c, i, d, n); out.append((i, d, sl, tp, n))
        return out
    return gen

# ---------------- F3 weekend gap fade ----------------
def f3(thr, m, tpfrac, maxb=48):
    """First bar after a >20h break (Sunday reopen in this data). gap = its open - previous close.
    If |gap| >= thr*avgRange20: fade at the first bar's close toward the Friday close
    (tpfrac=1 full fill, 0.5 half fill); stop = Sunday open + sign(gap)*m*|gap|; time exit maxb bars."""
    def gen(sym):
        c = ctx(sym); rows, out = c["rows"], []
        for k in range(30, len(rows) - 2):
            if rows[k][0] - rows[k - 1][0] < 20 * 3600: continue
            j = c["dayidx"].get(c["dkey"][k]); a20 = c["days"][j - 1]["avgR20"] if j else None
            if not a20: continue
            fc, so = rows[k - 1][4], rows[k][1]; g = so - fc
            if abs(g) < thr * a20: continue
            d = -1 if g > 0 else 1
            sl = so + (1 if g > 0 else -1) * m * abs(g)
            tp = so - tpfrac * g
            out.append((k, d, sl, tp, maxb))
        return out
    return gen

# ---------------- F4 month-end / week-end London 16:00 fix ----------------
def lon(t): return datetime.fromtimestamp(t, timezone.utc).astimezone(LON)
def f4(period, kind):
    """period 'ME' = last London weekday of each month present in data; 'WE' = every Friday.
    Bars: P = bar opening 15:00 London (pre-fix hour; fix = its close, 16:00 London).
    kind 'pre_fade'/'pre_follow': enter at P's open (close of the prior bar), direction vs/with the
      month-(week-)to-date move, exit at the fix (1 bar).
    kind 'post_rev'/'post_follow': enter at the fix (close of P), direction vs/with P's own move, hold 3 bars."""
    def gen(sym):
        c = ctx(sym); rows = c["rows"]; L = [lon(r[0]) for r in rows]; out = []
        P = [k for k in range(1, len(rows) - 5) if L[k].hour == 15 and L[k].weekday() < 5]
        if period == "WE":
            sel = [k for k in P if L[k].weekday() == 4]
        else:
            bym = {}
            for k in P: bym[(L[k].year, L[k].month)] = k   # last one wins
            sel = sorted(bym.values())[:-1]                # drop current (incomplete) month
        for k in sel:
            if c["atr"][k - 1] is None: continue
            if period == "WE":
                start = [x for x in range(k - 1, max(0, k - 140), -1) if rows[x][0] - rows[x - 1][0] > 20 * 3600]
                if not start: continue
                ref = rows[start[0]][1]
            else:
                y, mth = L[k].year, L[k].month
                first = [x for x in range(k, max(0, k - 800), -1) if (L[x].year, L[x].month) == (y, mth)]
                ref = rows[first[-1]][1]
            if kind.startswith("pre"):
                i = k - 1; mv = rows[i][4] - ref
                if mv == 0: continue
                d = (1 if mv > 0 else -1) * (-1 if kind == "pre_fade" else 1)
                sl, tp = atr_stop(c, i, d, 1); out.append((i, d, sl, tp, 1))
            else:
                i = k; mv = rows[k][4] - rows[k][1]
                if mv == 0: continue
                d = (1 if mv > 0 else -1) * (-1 if kind == "post_rev" else 1)
                sl, tp = atr_stop(c, i, d, 3); out.append((i, d, sl, tp, 3))
        return out
    return gen

# ---------------- F5 volatility regime ----------------
def f5(thr, sgn, geom):
    """Extreme FX day (range > thr*avgRange20). Enter at its close (17:00 NY). sgn -1 fade, +1 continuation
    (direction of the day's close-open). geom 'atr': ATR stop 1.5*sqrt(24)*ATR24, 24-bar time exit;
    geom 'rng': stop = 0.5*day range, target = 0.5*day range, 48-bar time exit."""
    def gen(sym):
        c = ctx(sym); out = []
        for dd in c["days"]:
            a = dd["avgR20"]; rng = dd["h"] - dd["l"]
            if a is None or rng <= thr * a or dd["c"] == dd["o"]: continue
            i = dd["last"]; d = sgn * (1 if dd["c"] > dd["o"] else -1)
            if i + 50 >= len(c["rows"]) or c["atr"][i] is None: continue
            if geom == "atr":
                sl, tp = atr_stop(c, i, d, 24); out.append((i, d, sl, tp, 24))
            else:
                e = c["rows"][i][4] + (c["spread"] * c["pip"] if d == 1 else 0)
                out.append((i, d, e - d * 0.5 * rng, e + d * 0.5 * rng, 48))
        return out
    return gen

# ---------------- F6 New York opening-range breakout ----------------
def f6(tpf, stop, last_sig):
    """OR = H1 bar opening 08:00 NY (hi, lo, W). First bar opening 09:00..last_sig NY whose close breaks
    the OR -> enter at close. Stop 'opp' = other side of OR, 'mid' = OR midpoint. Target = entry +- tpf*W.
    Time exit at the close of the bar opening 15:00 NY (16:00 NY)."""
    def gen(sym):
        c = ctx(sym); rows, T, out = c["rows"], c["ny"], []
        for k in range(30, len(rows) - 10):
            if T[k].hour != 8 or T[k].weekday() >= 5: continue
            hi, lo = rows[k][2], rows[k][3]; W = hi - lo
            if W <= 0: continue
            for i in range(k + 1, k + 9):
                if T[i].date() != T[k].date() or T[i].hour > last_sig: break
                cl = rows[i][4]; d = 1 if cl > hi else (-1 if cl < lo else 0)
                if d == 0: continue
                e = cl + (c["spread"] * c["pip"] if d == 1 else 0)
                sl = (lo if d == 1 else hi) if stop == "opp" else (hi + lo) / 2
                end = [x for x in range(i, i + 10) if x < len(rows) and T[x].date() == T[k].date() and T[x].hour <= 15]
                mb = max(1, end[-1] - i) if end else 1
                out.append((i, d, sl, e + d * tpf * W, mb)); break
        return out
    return gen

# ---------------- F7 carry direction + momentum ----------------
# A-priori average policy-rate assumptions for Dec-2023..Sep-2026 (%, approx): metals yield 0.
RATE = {"USD": 4.4, "GBP": 4.4, "AUD": 3.8, "NZD": 3.8, "CAD": 3.1, "EUR": 2.6, "JPY": 0.3, "XAU": 0.0, "XAG": 0.0}
def carry_dir(sym):
    b, q = base_quote(sym); df = RATE[b] - RATE[q]
    return 0 if abs(df) < 0.5 else (1 if df > 0 else -1)
def carry_swap(sym, st):
    """Carry side earns +0.5 pip/night (swap=-0.5 in sim15 terms); the other side pays 0.5."""
    return -0.5 if st[1] == carry_dir(sym) else 0.5
def f7(hold_days, stop_k, mom):
    """Daily at the FX-day close (17:00 NY): go in the carry direction if (mom=None) always, or (mom=n) if
    close > close n FX-days ago (for longs; < for shorts). Stop = stop_k * avgRange20 from entry; no target;
    time exit after 24*hold_days bars; re-enter next daily close if still valid (one position at a time)."""
    def gen(sym):
        c = ctx(sym); cd = carry_dir(sym); days, out = c["days"], []
        if cd == 0: return []
        for j, dd in enumerate(days):
            if dd["avgR20"] is None or j < 61: continue
            if mom and (dd["c"] - days[j - mom]["c"]) * cd <= 0: continue
            i = dd["last"]
            if i + 24 * hold_days + 1 >= len(c["rows"]): continue
            e = c["rows"][i][4] + (c["spread"] * c["pip"] if cd == 1 else 0)
            r = stop_k * dd["avgR20"]
            out.append((i, cd, e - cd * r, e + cd * BIG * r, 24 * hold_days))
        return out
    return gen

FAMILIES = {
    "F1_time_of_day": [(f"F1 open{H:02d} N{N} {'sellOpening' if s == 1 else 'buyOpening'}", f1(H, N, s), None)
                       for H, N in ((3, 3), (3, 6), (8, 3), (8, 6), (19, 6)) for s in (1, -1)],
    "F2_day_of_week": [(f"F2 {k} {'fade' if s == -1 else 'follow'}", f2(k, s), None)
                       for k in ("tue", "tuebig", "fri10", "fri12") for s in (-1, 1)],
    "F3_weekend_gap": [(f"F3 thr{t} stop{m}xgap tp{f}", f3(t, m, f), None)
                       for t, m, f in ((0.05, 1, 1), (0.05, 2, 1), (0.10, 1, 1), (0.10, 2, 1), (0.20, 1, 1), (0.20, 2, 1),
                                       (0.10, 1, 0.5), (0.10, 2, 0.5))],
    "F4_month_week_end_fix": [(f"F4 {p} {k}", f4(p, k), None) for p in ("ME", "WE")
                              for k in ("pre_fade", "pre_follow", "post_rev", "post_follow")],
    "F5_vol_regime": [(f"F5 thr{t} {'fade' if s == -1 else 'cont'} {g}", f5(t, s, g), None)
                      for t, s, g in ((1.5, -1, "atr"), (1.5, 1, "atr"), (2.0, -1, "atr"), (2.0, 1, "atr"),
                                      (2.5, -1, "atr"), (2.5, 1, "atr"), (2.0, -1, "rng"), (2.0, 1, "rng"))],
    "F6_ny_orb": [(f"F6 tp{tp}W stop{s} sig<= {ls:02d}", f6(tp, s, ls), None)
                  for tp in (0.5, 1.0) for s in ("opp", "mid") for ls in (10, 12)],
    "F7_carry_mom": [(f"F7 hold{h}d stop{k}xADR {'mom20' if m else 'nomom'}", f7(h, k, m), carry_swap)
                     for h in (1, 5) for k in (1.0, 2.0) for m in (20, None)],
}
