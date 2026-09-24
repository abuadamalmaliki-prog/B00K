"""Bar-by-bar mirror of frostbite.pine on an M5 chart.

Everything the indicator knows is rebuilt the way Pine sees it, one closed M5 bar at a time:
  - chart indicators on M5 (EMA 34/50/200, RSI 14, ATR 14, ADX 14),
  - M15 bars aggregated from M5 bars (UTC quarter hours) with their own ATR 14 (Wilder),
  - H1 closes aggregated from M5 bars with EMA 50,
  - trading days (17:00 New York) with the prior day's high and low.
The signals must match meeting.frostbite_signals() (the research definition).
"""
import os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import frost  # noqa: E402

ICE_T1, ICE_T2 = 1.0, 2.0
AVA_T1, AVA_T2 = 1.5, 3.0


class Wilder:
    """ta.rma seeded with the simple mean of the first n values (matches frost.rma)."""

    def __init__(self, n):
        self.n, self.k, self.acc, self.v = n, 0, 0.0, np.nan

    def update(self, x):
        self.k += 1
        if self.k < self.n:
            self.acc += x
        elif self.k == self.n:
            self.acc += x; self.v = self.acc / self.n
        else:
            self.v = (self.v * (self.n - 1) + x) / self.n
        return self.v


class Ema:
    """ta.ema seeded with the simple mean of the first n values (matches frost.ema)."""

    def __init__(self, n):
        self.n, self.k, self.acc, self.v, self.a = n, 0, 0.0, np.nan, 2.0 / (n + 1)

    def update(self, x):
        self.k += 1
        if self.k < self.n:
            self.acc += x
        elif self.k == self.n:
            self.acc += x; self.v = self.acc / self.n
        else:
            self.v = self.a * x + (1 - self.a) * self.v
        return self.v


def chart_indicators(b):
    """M5 chart series exactly as TradingView defines them (ta.ema, ta.rsi, ta.atr, ta.dmi)."""
    sys.path.insert(0, os.path.join(HERE, "teamA"))
    import teamA  # Team A's ADX is the ta.dmi definition
    c = b.c.values
    out = dict(e34=frost.ema(c, 34), e50=frost.ema(c, 50), e200=frost.ema(c, 200),
               rsi=frost.rsi(c, 14), atr=frost.atr(b, 14), adx=teamA.ADX(5, 14))
    return out


def run():
    b = frost.bars(5)
    ind = chart_indicators(b)
    o, h, l, c = b.o.values, b.h.values, b.l.values, b.c.values
    t = b.time.values
    utc_h = b.utc_h.values
    tday = b.tday.values
    n = len(b)

    # M15 state
    k15_cur = None; m15 = None; atr15 = Wilder(14); prev15_close = np.nan; last15_close = np.nan
    # H1 state
    k60_cur = None; h1_close = np.nan; ema50 = Ema(50); h1_trend = 0.0
    # trading day state
    day_cur = None; day_hi = -np.inf; day_lo = np.inf; pdh = np.nan; pdl = np.nan
    first_up = first_dn = None  # trading day of the last Avalanche buy / sell

    rows = []
    for i in range(n):
        # ── trading day roll (on the bar's open time) ──
        if tday[i] != day_cur:
            if day_cur is not None:
                pdh, pdl = day_hi, day_lo
            day_cur, day_hi, day_lo = tday[i], -np.inf, np.inf
        day_hi = max(day_hi, h[i]); day_lo = min(day_lo, l[i])

        # ── M15 aggregation ──
        k15 = t[i] // 900
        if k15 != k15_cur:
            k15_cur = k15
            m15 = dict(o=o[i], h=h[i], l=l[i], c=c[i], nym=b.ny_min.values[i], tday=tday[i])
        else:
            m15["h"] = max(m15["h"], h[i]); m15["l"] = min(m15["l"], l[i]); m15["c"] = c[i]
        m15_done = (t[i] + 300) % 900 == 0

        # ── H1 aggregation (complete when this bar closes the hour) ──
        if (t[i] + 300) % 3600 == 0:
            h1_close = c[i]
            e = ema50.update(h1_close)
            h1_trend = np.sign(h1_close - e) if np.isfinite(e) else 0.0

        # ── Icicle (FA Gold Scalper, M5, 13-17 UTC) ──
        ice = 0; ice_stop = np.nan
        if i >= 5:
            e34, e50, e200 = ind["e34"][i], ind["e50"][i], ind["e200"][i]
            r, a, adx = ind["rsi"][i], ind["atr"][i], ind["adx"][i]
            if np.isfinite(e200) and np.isfinite(adx) and np.isfinite(a) and 13 <= utc_h[i] < 17:
                lo3 = l[i - 2:i + 1].min(); hi3 = h[i - 2:i + 1].max()
                L = (e34 > e50 > e200) and c[i] > e200 and lo3 <= e34 and c[i] > o[i] and c[i] > h[i - 1] \
                    and c[i] > e34 and adx > 20 and 45 < r < 70
                S = (e34 < e50 < e200) and c[i] < e200 and hi3 >= e34 and c[i] < o[i] and c[i] < l[i - 1] \
                    and c[i] < e34 and adx > 20 and 30 < r < 55
                if L != S:
                    ice = 1 if L else -1
                    if L:
                        sl = l[i - 4:i + 1].min() - 0.2 * a
                        ice_stop = min(max(c[i] - sl, 0.6 * a), 3 * a)
                    else:
                        sl = h[i - 4:i + 1].max() + 0.2 * a
                        ice_stop = min(max(sl - c[i], 0.6 * a), 3 * a)

        # ── Avalanche (prior-day high/low close-beyond on M15, H1 EMA50 side, first per side per day) ──
        ava = 0; ava_stop = np.nan
        if m15_done:
            pc = prev15_close
            tr = m15["h"] - m15["l"] if not np.isfinite(pc) else max(m15["h"] - m15["l"], abs(m15["h"] - pc), abs(m15["l"] - pc))
            a15 = atr15.update(tr)
            nym = m15["nym"]
            in_win = nym >= 18 * 60 or nym < 16 * 60
            if in_win and np.isfinite(pdh) and np.isfinite(pc) and np.isfinite(a15):
                up = m15["c"] > pdh and pc <= pdh and h1_trend > 0
                dn = m15["c"] < pdl and pc >= pdl and h1_trend < 0
                if up and first_up != m15["tday"]:
                    ava = 1; first_up = m15["tday"]
                elif dn and first_dn != m15["tday"]:
                    ava = -1; first_dn = m15["tday"]
                ava_stop = 1.5 * a15
            prev15_close = m15["c"]

        if ice != 0:
            rows.append((i, ice, c[i], ice_stop, ICE_T1, ICE_T2, 0))
        elif ava != 0:
            rows.append((i, ava, c[i], ava_stop, AVA_T1, AVA_T2, 1))
    s = pd.DataFrame(rows, columns=["bar", "d", "ref", "stop", "t1r", "t2r", "src"])
    s["i"] = b.end.values[s.bar.values]
    s["sl"] = s.ref - s.d * s.stop
    s["tp1"] = s.ref + s.d * s.stop * s.t1r
    s["tp2"] = s.ref + s.d * s.stop * s.t2r
    s["time"] = t[s.bar.values]
    return s


def compare():
    import meeting
    ref = meeting.frostbite_signals()
    mir = run()
    a = ref.set_index("i"); m = mir.set_index("i")
    both = a.index.intersection(m.index)
    only_ref = a.index.difference(m.index); only_mir = m.index.difference(a.index)
    same_dir = (a.loc[both, "d"].values == m.loc[both, "d"].values)
    dsl = np.abs(a.loc[both, "sl"].values - m.loc[both, "sl"].values)
    print(f"research signals {len(a)}, mirror signals {len(m)}, matched {len(both)}, "
          f"only research {len(only_ref)}, only mirror {len(only_mir)}")
    print(f"matched: same direction {same_dir.mean() * 100:.2f}%, same source "
          f"{(a.loc[both, 'src'].values == m.loc[both, 'src'].values).mean() * 100:.2f}%, "
          f"SL max abs diff {dsl.max():.6f}, median {np.median(dsl):.6f}")
    d1 = frost.m1()
    for lab, idx in (("only research", only_ref), ("only mirror", only_mir)):
        if len(idx):
            tt = pd.to_datetime(d1.time.values[np.asarray(idx)], unit="s")
            src = (a if lab == "only research" else m).loc[idx, "src"].values
            print(f"  {lab}: " + ", ".join(f"{x:%Y-%m-%d %H:%M} src={s}" for x, s in list(zip(tt, src))[:12]))
    # same trades when simulated?
    tm = frost.simulate(mir[["i", "d", "ref", "sl", "tp1", "tp2"]], **meeting.FROST_SIM)
    tr = frost.simulate(ref.drop(columns="src"), **meeting.FROST_SIM)
    print(f"simulated: research n={len(tr)} avgR={tr.r.mean():+.4f} | mirror n={len(tm)} avgR={tm.r.mean():+.4f}")
    return a, m




def track(sig, spread=frost.SPREAD, max_hold=120, be=False, flat=True):
    """The Pine trade tracker on M5 bars (what the panel's 'This chart' row counts).
    Same order of checks as frostbite.pine: fill at the next bar open, gap, stop, TP1, TP2, time/rollover exit."""
    b = frost.bars(5)
    o, h, l, c, t = b.o.values, b.h.values, b.l.values, b.c.values, b.time.values
    nym = b.ny_min.values
    nym_close = ((b.ny_min.values + 5) % 1440)
    sig_at = {int(r.bar): r for r in sig.itertuples()}
    out = []
    tdir = 0; pend = False
    for i in range(len(b)):
        if pend:
            pend = False
            stale = (o[i] <= tsl or o[i] >= tt1) if tdir == 1 else (o[i] + spread >= tsl or o[i] + spread <= tt1)
            if stale:
                tdir = 0
            else:
                fill = o[i] + spread if tdir == 1 else o[i]
                entry_t = t[i]; leg1 = leg2 = True; stop2 = tsl; r1 = r2 = 0.0; g1 = g2 = gs = False
        if tdir != 0 and not pend and (leg1 or leg2):
            risk = abs(tref - tsl)
            if tdir == 1:
                lo_, hi_, op_ = l[i], h[i], o[i]
                if leg1 and op_ <= tsl: r1 = (op_ - fill) / risk; leg1 = False; gs = True
                if leg2 and op_ <= stop2: r2 = (op_ - fill) / risk; leg2 = False; gs = gs or stop2 == tsl
                if leg1 and lo_ <= tsl: r1 = (tsl - fill) / risk; leg1 = False; gs = True
                if leg2 and lo_ <= stop2: r2 = (stop2 - fill) / risk; leg2 = False; gs = gs or stop2 == tsl
                if leg1 and hi_ >= tt1:
                    r1 = (tt1 - fill) / risk; leg1 = False; g1 = True
                    if be: stop2 = max(stop2, fill)
                if leg2 and hi_ >= tt2: r2 = (tt2 - fill) / risk; leg2 = False; g2 = True
            else:
                aO, aH, aL = o[i] + spread, h[i] + spread, l[i] + spread
                if leg1 and aO >= tsl: r1 = (fill - aO) / risk; leg1 = False; gs = True
                if leg2 and aO >= stop2: r2 = (fill - aO) / risk; leg2 = False; gs = gs or stop2 == tsl
                if leg1 and aH >= tsl: r1 = (fill - tsl) / risk; leg1 = False; gs = True
                if leg2 and aH >= stop2: r2 = (fill - stop2) / risk; leg2 = False; gs = gs or stop2 == tsl
                if leg1 and aL <= tt1:
                    r1 = (fill - tt1) / risk; leg1 = False; g1 = True
                    if be: stop2 = min(stop2, fill)
                if leg2 and aL <= tt2: r2 = (fill - tt2) / risk; leg2 = False; g2 = True
            time_up = (t[i] + 300 - entry_t) >= max_hold * 60
            flat_now = flat and nym_close[i] >= 16 * 60 + 50 and nym[i] < 17 * 60
            if (leg1 or leg2) and (time_up or flat_now):
                px = c[i] if tdir == 1 else c[i] + spread
                if leg1: r1 = (px - fill if tdir == 1 else fill - px) / risk; leg1 = False
                if leg2: r2 = (px - fill if tdir == 1 else fill - px) / risk; leg2 = False
            if not leg1 and not leg2:
                out.append((t_sig, tdir, 0.5 * (r1 + r2), int(g1), int(g2), int(gs)))
                tdir = 0
        s = sig_at.get(i)
        roll = 16 * 60 + 50 <= nym_close[i] < 18 * 60
        if s is not None and tdir == 0 and not roll:
            tdir = s.d; pend = True; tref = s.ref; tsl = s.sl; tt1 = s.tp1; tt2 = s.tp2; t_sig = t[i] + 300
    return pd.DataFrame(out, columns=["time", "d", "r", "hit_t1", "hit_t2", "hit_sl"])


def chart_vs_engine():
    import meeting
    mir = run()
    tc = track(mir)
    te = frost.simulate(mir[["i", "d", "ref", "sl", "tp1", "tp2"]], **meeting.FROST_SIM)
    rows = []
    for name, tt in (("engine (M1)", te), ("chart tracker (M5)", tc)):
        for p in ("VAL", "Y2025", "HOLD"):
            s = frost.stats(tt[frost.in_period(tt, p)], p)
            rows.append(dict(model=name, **{k: s.get(k) for k in ("label", "n", "win", "tp1", "tp2", "sl", "avgR")}))
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    compare()
    chart_vs_engine()
