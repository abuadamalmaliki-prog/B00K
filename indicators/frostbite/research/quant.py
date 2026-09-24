"""Frostbite v2 research: quantitative signal families on XAUUSD M5 (no SMC, no sessions boxes).

Families (all on closed M5 bars, stops in ATR(14) of M5):
  KPB   Kalman trend + pullback: 2-state Kalman filter (level, slope). In a trend (|slope|/ATR above s),
        buy when the residual z-score (close - level) / stdev crosses back up through -z (sell mirrored).
  KFLIP Kalman slope flip: normalised slope crosses +s from below (buy) / -s from above (sell).
  FISH  Ehlers Fisher transform turn from an extreme, in the direction of the Ehlers SuperSmoother slope.
  REGT  Linear-regression slope t-statistic > T, entry when price crosses back over the regression line.
Protocol as before: tune on DISC (Jan-Apr 2026) only, report VAL, Y2025 and HOLD unchanged.
"""
import os, sys, math, itertools
import numpy as np
import pandas as pd
import numba as nb

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import frost  # noqa: E402

B5 = frost.bars(5)
C = B5.c.values; H = B5.h.values; L = B5.l.values; O = B5.o.values
ATR = frost.atr(B5, 14)
UTC_H = B5.utc_h.values
N = len(B5)


# ─── math ────────────────────────────────────────────────────────────────────
@nb.njit(cache=True)
def kalman(y, q_level, q_slope, r):
    """Local linear trend Kalman filter. Returns filtered level and slope (after the update at each bar)."""
    n = len(y); lv = np.empty(n); sl = np.empty(n)
    x1 = y[0]; x2 = 0.0; p11 = 1.0; p12 = 0.0; p22 = 1.0
    lv[0] = x1; sl[0] = x2
    for t in range(1, n):
        # predict
        x1 = x1 + x2
        p11 = p11 + 2.0 * p12 + p22 + q_level
        p12 = p12 + p22
        p22 = p22 + q_slope
        # update
        s = p11 + r
        k1 = p11 / s; k2 = p12 / s
        e = y[t] - x1
        x1 = x1 + k1 * e; x2 = x2 + k2 * e
        p22 = p22 - k2 * p12
        p12 = (1.0 - k1) * p12
        p11 = (1.0 - k1) * p11
        lv[t] = x1; sl[t] = x2
    return lv, sl


def rolling_std(x, n):
    return pd.Series(x).rolling(n).std(ddof=0).values


@nb.njit(cache=True)
def supersmoother(x, period):
    a1 = math.exp(-1.414 * math.pi / period); b1 = 2 * a1 * math.cos(1.414 * math.pi / period)
    c2 = b1; c3 = -a1 * a1; c1 = 1 - c2 - c3
    out = np.empty(len(x)); out[0] = x[0]; out[1] = x[1]
    for i in range(2, len(x)):
        out[i] = c1 * (x[i] + x[i - 1]) / 2 + c2 * out[i - 1] + c3 * out[i - 2]
    return out


@nb.njit(cache=True)
def fisher(h, l, n):
    m = len(h); v = np.zeros(m); f = np.zeros(m)
    for i in range(m):
        if i < n - 1:
            continue
        hh = h[i - n + 1:i + 1].max(); ll = l[i - n + 1:i + 1].min()
        mid = (h[i] + l[i]) / 2
        x = 0.0 if hh == ll else 0.66 * ((mid - ll) / (hh - ll) - 0.5) + 0.67 * v[i - 1]
        x = min(max(x, -0.999), 0.999); v[i] = x
        f[i] = 0.5 * math.log((1 + x) / (1 - x)) + 0.5 * f[i - 1]
    return f


def regression(y, n):
    """Rolling OLS over n bars: slope, t-stat of the slope, fitted value at the newest bar, residual stdev."""
    y = pd.Series(y)
    x = np.arange(n, dtype=float); xm = x.mean(); sxx = ((x - xm) ** 2).sum()
    ym = y.rolling(n).mean()
    sxy = y.rolling(n).apply(lambda w: ((x - xm) * (w - w.mean())).sum(), raw=True)
    slope = sxy / sxx
    fit_last = ym + slope * (n - 1 - xm)
    resid_var = y.rolling(n).var(ddof=0) * n - slope ** 2 * sxx
    se = np.sqrt(np.maximum(resid_var, 1e-12) / (n - 2) / sxx)
    sd = np.sqrt(np.maximum(resid_var, 1e-12) / n)
    return slope.values, (slope / se).values, fit_last.values, sd.values


def cross_up(a, lvl):
    a1 = np.r_[np.nan, a[:-1]]
    return (a1 < lvl) & (a >= lvl)


def cross_dn(a, lvl):
    a1 = np.r_[np.nan, a[:-1]]
    return (a1 > lvl) & (a <= lvl)


def session(sess):
    if sess == "all":
        return np.ones(N, bool)
    a, z = sess
    return (UTC_H >= a) & (UTC_H < z)


# ─── families: each returns (long mask, short mask) ─────────────────────────
_K = {}


def kal(ql, qs):
    if (ql, qs) not in _K:
        _K[(ql, qs)] = kalman(C.astype(float), ql, qs, 1.0)
    return _K[(ql, qs)]


def fam_kpb(p):
    lv, sl = kal(p["ql"], p["qs"])
    slope = sl / ATR
    res = C - lv
    z = res / rolling_std(res, p["zn"])
    Lm = (slope > p["s"]) & cross_up(z, -p["z"])
    Sm = (slope < -p["s"]) & cross_dn(z, p["z"])
    return Lm, Sm


def fam_kflip(p):
    lv, sl = kal(p["ql"], p["qs"])
    slope = sl / ATR
    return cross_up(slope, p["s"]), cross_dn(slope, -p["s"])


def fam_fish(p):
    ss = supersmoother(C.astype(float), p["ssp"])
    ssl = ss - np.r_[np.nan, ss[:-1]]
    f = fisher(H, L, p["fn"])
    f1 = np.r_[np.nan, f[:-1]]
    Lm = (f1 < -p["f"]) & (f > f1) & (ssl > 0)
    Sm = (f1 > p["f"]) & (f < f1) & (ssl < 0)
    return Lm, Sm


_R = {}


def fam_regt(p):
    if p["n"] not in _R:
        _R[p["n"]] = regression(C, p["n"])
    slope, t, fit, sd = _R[p["n"]]
    dev = (C - fit) / sd
    Lm = (t > p["T"]) & cross_up(dev, -p["d"])
    Sm = (t < -p["T"]) & cross_dn(dev, p["d"])
    return Lm, Sm


FAMS = {
    "KPB": (fam_kpb, [dict(ql=ql, qs=qs, s=s, z=z, zn=100) for ql, qs in ((0.01, 1e-4), (0.05, 1e-3), (0.2, 1e-2))
                      for s in (0.02, 0.05, 0.1) for z in (1.0, 1.5, 2.0)]),
    "KFLIP": (fam_kflip, [dict(ql=ql, qs=qs, s=s) for ql, qs in ((0.01, 1e-4), (0.05, 1e-3), (0.2, 1e-2))
                          for s in (0.02, 0.05, 0.1, 0.2)]),
    "FISH": (fam_fish, [dict(ssp=sp, fn=fn, f=f) for sp in (20, 40) for fn in (10, 20) for f in (1.0, 1.5, 2.0)]),
    "REGT": (fam_regt, [dict(n=n, T=T, d=d) for n in (50, 100) for T in (3.0, 6.0, 10.0) for d in (0.5, 1.0, 1.5)]),
}
SESSIONS = ["all", (7, 20)]
STOPS = [1.5, 2.5]
EXITS = [(1.0, 2.0), (0.75, 1.5), (1.5, 3.0)]
HOLD = 120


def make_sig(fam, p, sess, k, t1, t2):
    Lm, Sm = FAMS[fam][0](p)
    ok = session(sess) & np.isfinite(ATR) & (np.arange(N) > 300)
    Lm = np.nan_to_num(Lm & ok).astype(bool); Sm = np.nan_to_num(Sm & ok).astype(bool)
    both = Lm & Sm; Lm &= ~both; Sm &= ~both
    idx = np.flatnonzero(Lm | Sm)
    d = np.where(Lm[idx], 1, -1)
    return frost.levels(B5, idx, d, k * ATR[idx], t1, t2), idx


_DAYS = {k: frost.trading_days(frost._ts(a), frost._ts(z)) for k, (a, z) in frost.PERIODS.items()}


def evaluate(sig, period, **kw):
    t = frost.simulate(sig, be=False, max_hold=HOLD, **kw)
    t = t[frost.in_period(t, period)]
    return frost.stats(t, period, _DAYS[period])


def search(fam, min_per_day=2.0):
    """Stage 1: signal params x session x stop at TP 1/2. Stage 2: exits on the winner. DISC only."""
    tried = 0; best = None
    for p in FAMS[fam][1]:
        for sess in SESSIONS:
            for k in STOPS:
                sig, _ = make_sig(fam, p, sess, k, 1.0, 2.0)
                sig = sig[frost.in_period(pd.DataFrame({"time": frost.m1().time.values[sig.i.values]}), "DISC").values]
                s = evaluate(sig, "DISC"); tried += 1
                if s["n"] and s["per_day"] >= min_per_day and (best is None or s["avgR"] > best[0]["avgR"]):
                    best = (s, p, sess, k, 1.0, 2.0)
    if best is None:
        return None, tried
    _, p, sess, k, _, _ = best
    for t1, t2 in EXITS[1:]:
        sig, _ = make_sig(fam, p, sess, k, t1, t2)
        s = evaluate(sig, "DISC"); tried += 1
        if s["avgR"] > best[0]["avgR"]:
            best = (s, p, sess, k, t1, t2)
    return best, tried


def report(fam, best, tried):
    s, p, sess, k, t1, t2 = best
    sig, idx = make_sig(fam, p, sess, k, t1, t2)
    row = dict(fam=fam, params=f"{p} sess={sess} stop={k}ATR TP{t1}/{t2}", combos=tried,
               disc=f"{s['avgR']:+.3f}/{s['n']} ({s['per_day']}/d)")
    for per in ("VAL", "Y2025", "HOLD"):
        e = evaluate(sig, per)
        row[per] = f"{e['avgR']:+.3f}±{e['se']:.3f} n={e['n']} {e['per_day']}/d win{e['win']} tp1 {e['tp1']} tp2 {e['tp2']}"
    st = evaluate(sig, "VAL", spread=0.45, slip=0.05)
    row["stress VAL"] = f"{st['avgR']:+.3f}"
    return row, sig


def main():
    print("coverage", frost.coverage())
    rows = []
    for fam in FAMS:
        best, tried = search(fam)
        if best is None:
            print(fam, "no variant with >= 2 trades/day"); continue
        row, _ = report(fam, best, tried)
        rows.append(row)
        print(pd.Series(row).to_string(), "\n", flush=True)


if __name__ == "__main__":
    main()
