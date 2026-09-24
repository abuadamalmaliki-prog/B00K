"""Frostbite shared research engine: XAUUSD scalping on 1-minute bid/ask data.

Every team uses this file so every technique is measured the same way.

Data      data/XAUUSD_{2025,2026}_m1.csv.gz (Dukascopy, UTC epoch seconds, bid + ask OHLC).
Costs     ask = bid + SPREAD + widening, where widening = Dukascopy's spread above its own median
          for that trading day (news, rollover). SPREAD is the broker's normal spread. Longs fill at the ask and exit on the bid;
          shorts fill at the bid and exit on the ask. Optional slippage on market fills.
Signals   computed on bid bars of any timeframe (TradingView charts show bid).
          A signal on a bar is acted on at the open of the next 1-minute bar.
Orders    levels are fixed prices from the signal bar close: SL, TP1, TP2.
          Mode "split": two equal positions, same SL, one with TP1 and one with TP2 (no management).
          Mode "be":    as split, but after TP1 fills the TP2 position's SL moves to its entry price.
          Same-bar ambiguity: if a 1-minute bar touches both the stop and a target, the stop wins.
          Gaps: a bar opening beyond the stop exits at that open.
Exits     SL, TP, or a forced market exit at max hold or at 16:50 New York (before rollover).
R         result / planned risk, planned risk = |signal close - SL| (what the lot size is based on).

Periods   DISCOVERY = 2026-01..04 (tune here only)
          VALIDATION = 2026-05..08 (unseen by tuning)
          Extra unseen: YEAR2025 and HOLDOUT = 2026-09-01..23
"""
import os, math, pickle
import numpy as np
import pandas as pd
import numba as nb

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
SYMBOL = os.environ.get("FROST_SYM", "XAUUSD")   # other symbols: data/cache_<SYM>/ from fetch_dukascopy.py
_SPREADS = {"XAUUSD": 0.30, "EURUSD": 0.00012, "GBPUSD": 0.00015, "USDJPY": 0.015}
_SCALES = {"XAUUSD": 1000.0, "USDJPY": 1000.0}
SPREAD = _SPREADS.get(SYMBOL, 0.30)   # XAUUSD: JustMarkets Standard typical (USD per oz); stress test 0.45
SLIP = 0.0             # extra adverse fill per market order (USD)
PERIODS = {
    "DISC": ("2026-01-01", "2026-05-01"),
    "VAL": ("2026-05-01", "2026-09-01"),
    "Y2025": ("2025-01-01", "2026-01-01"),
    "HOLD": ("2026-09-01", "2026-09-24"),
}


def _ts(s):
    return int(pd.Timestamp(s, tz="UTC").timestamp())


# ─── data ────────────────────────────────────────────────────────────────────
_M1 = {}


def m1(spread=SPREAD):
    """1-minute frame with bid (o,h,l,c) and ask (ao,ah,al,ac) after the spread floor, plus NY clock."""
    if spread in _M1:
        return _M1[spread]
    raw = _load_raw()
    d = pd.DataFrame({"time": raw.time.values.astype(np.int64),
                      "o": raw.bo.values, "h": raw.bh.values, "l": raw.bl.values, "c": raw.bc.values, "v": raw.vol.values})
    # Broker spread model: the broker's normal spread plus any widening above Dukascopy's own
    # normal level that day (news, rollover). Dukascopy's baseline gold spread (~$0.66 median)
    # is wider than a JustMarkets Standard account, so its level is not used directly.
    sp = np.maximum(raw.ao.values - raw.bo.values, raw.ac.values - raw.bc.values)
    ny0 = pd.to_datetime(raw.time, unit="s", utc=True).dt.tz_convert("America/New_York")
    tday0 = (ny0 + pd.Timedelta(hours=7)).dt.strftime("%Y%m%d").values
    base = pd.Series(sp).groupby(tday0).transform("median").values
    d["xs"] = np.maximum(0.0, sp - base)
    for k in ("o", "h", "l", "c"):
        d["a" + k] = d[k].values + spread + d["xs"].values
    ny = pd.to_datetime(d.time, unit="s", utc=True).dt.tz_convert("America/New_York")
    d["ny_h"] = ny.dt.hour.values
    d["ny_m"] = ny.dt.minute.values
    d["ny_min"] = d.ny_h * 60 + d.ny_m
    # trading day id: 17:00 New York starts the next day
    d["tday"] = (ny + pd.Timedelta(hours=7)).dt.strftime("%Y%m%d").astype(int).values
    utc = pd.to_datetime(d.time, unit="s", utc=True)
    d["utc_h"] = utc.dt.hour.values
    d["dow"] = (ny + pd.Timedelta(hours=7)).dt.dayofweek.values  # trading-day weekday, Mon=0
    _M1[spread] = d
    return d


_REC = np.dtype([("t", ">u4"), ("o", ">u4"), ("c", ">u4"), ("l", ">u4"), ("h", ">u4"), ("v", ">f4")])


def _load_raw():
    """Decode every cached Dukascopy day (data/cache/YYYYMMDD_BID.bin + _ASK.bin) into one frame.
    Closed-market minutes (volume 0) are dropped."""
    cdir = os.path.join(DATA, "cache" if SYMBOL == "XAUUSD" else "cache_" + SYMBOL)
    scale = _SCALES.get(SYMBOL, 100000.0)
    days = sorted({f[:8] for f in os.listdir(cdir) if f.endswith("_BID.bin")})
    parts = []
    for day in days:
        fb, fa = os.path.join(cdir, day + "_BID.bin"), os.path.join(cdir, day + "_ASK.bin")
        if not os.path.exists(fa):
            continue
        b = np.frombuffer(open(fb, "rb").read(), _REC); a = np.frombuffer(open(fa, "rb").read(), _REC)
        if len(b) == 0 or len(a) != len(b):
            continue
        base = int(pd.Timestamp(day, tz="UTC").timestamp())
        f = pd.DataFrame({"time": base + b["t"].astype(np.int64),
                          "bo": b["o"] / scale, "bh": b["h"] / scale, "bl": b["l"] / scale, "bc": b["c"] / scale,
                          "ao": a["o"] / scale, "ah": a["h"] / scale, "al": a["l"] / scale, "ac": a["c"] / scale,
                          "vol": b["v"].astype(float)})
        parts.append(f[f.vol > 0])
    return pd.concat(parts).drop_duplicates("time").sort_values("time").reset_index(drop=True)


def coverage():
    """First and last UTC day available, and the number of days loaded."""
    d = m1()
    t = pd.to_datetime(d.time, unit="s", utc=True)
    return str(t.iloc[0]), str(t.iloc[-1]), int(t.dt.date.nunique())


def bars(tf_min, spread=SPREAD):
    """Bid bars of tf_min minutes aligned to UTC clock (TradingView intraday alignment).
    Column 'end' is the 1-minute row index of the bar's last minute: a signal on this bar
    is acted on at row end+1."""
    d = m1(spread)
    if tf_min == 1:
        b = d[["time", "o", "h", "l", "c", "v", "ny_h", "ny_m", "ny_min", "tday", "utc_h", "dow"]].copy()
        b["end"] = np.arange(len(d))
        return b.reset_index(drop=True)
    key = d.time.values // (tf_min * 60)
    g = pd.DataFrame({"k": key, "i": np.arange(len(d)), "o": d.o, "h": d.h, "l": d.l, "c": d.c, "v": d.v})
    agg = g.groupby("k", sort=True).agg(o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"),
                                         v=("v", "sum"), start=("i", "first"), end=("i", "last"))
    b = agg.reset_index()
    b["time"] = b.k * tf_min * 60
    for col in ("ny_h", "ny_m", "ny_min", "tday", "utc_h", "dow"):
        b[col] = d[col].values[b.start.values]
    return b.drop(columns=["k"]).reset_index(drop=True)


# ─── indicators (TradingView-equivalent) ─────────────────────────────────────
def ema(x, n):
    x = np.asarray(x, float); out = np.full(len(x), np.nan); a = 2 / (n + 1)
    if len(x) < n: return out
    out[n - 1] = x[:n].mean()
    for i in range(n, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def rma(x, n):
    x = np.asarray(x, float); out = np.full(len(x), np.nan)
    if len(x) < n: return out
    out[n - 1] = x[:n].mean()
    for i in range(n, len(x)):
        out[i] = (out[i - 1] * (n - 1) + x[i]) / n
    return out


def sma(x, n):
    return pd.Series(x).rolling(n).mean().values


def stdev(x, n):
    return pd.Series(x).rolling(n).std(ddof=0).values


def atr(b, n=14):
    h, l, c = b.h.values, b.l.values, b.c.values
    pc = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.c_[h - l, np.abs(h - pc), np.abs(l - pc)], axis=1)
    tr[0] = h[0] - l[0]
    return rma(tr, n)


def rsi(c, n=14):
    c = np.asarray(c, float); ch = np.r_[0, np.diff(c)]
    up, dn = rma(np.maximum(ch, 0), n), rma(np.maximum(-ch, 0), n)
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.where(dn == 0, 100.0, np.where(up == 0, 0.0, 100 - 100 / (1 + up / dn)))
    r[np.isnan(up)] = np.nan
    return r


def vwap_session(b):
    """VWAP anchored at the trading-day start (17:00 New York), like ta.vwap on a TradingView forex chart."""
    tp = (b.h.values + b.l.values + b.c.values) / 3; v = np.maximum(b.v.values, 1e-9)
    day = b.tday.values
    new = np.r_[True, day[1:] != day[:-1]]
    grp = np.cumsum(new)
    pv = pd.Series(tp * v).groupby(grp).cumsum().values
    vv = pd.Series(v).groupby(grp).cumsum().values
    return pv / vv


def htf_on_ltf(b_ltf, b_htf, values):
    """Value of a higher-timeframe series as known at each lower-timeframe bar close
    (last COMPLETED higher bar, no lookahead)."""
    # an htf bar is complete at the ltf bar whose 'end' equals the htf bar's 'end'
    idx = np.searchsorted(b_htf.end.values, b_ltf.end.values, side="right") - 1
    out = np.full(len(b_ltf), np.nan)
    ok = idx >= 0
    out[ok] = np.asarray(values)[idx[ok]]
    return out


# ─── simulator ───────────────────────────────────────────────────────────────
@nb.njit(cache=True)
def _sim(o, h, l, c, ao, ah, al, ac, ny_min, tday, sig_i, sig_d, sig_ref, sig_sl, sig_t1, sig_t2,
         max_hold, be, one_at_a_time, slip, flat_min):
    n = len(sig_i)
    out = np.full((n, 8), np.nan)  # r, r1, r2, exit_i, hit_t1, hit_t2, hit_sl, entry_fill
    busy_until = -1
    N = len(o)
    for k in range(n):
        i = sig_i[k] + 1
        if i >= N:
            continue
        if one_at_a_time and i <= busy_until:
            continue
        if ny_min[i] >= flat_min and ny_min[i] < 18 * 60:
            continue  # no entries from the pre-rollover flat time until the 18:00 reopen
        d = sig_d[k]; ref = sig_ref[k]; sl = sig_sl[k]; t1 = sig_t1[k]; t2 = sig_t2[k]
        risk = abs(ref - sl)
        if risk <= 0:
            continue
        # entry at next 1m open
        fill = (ao[i] + slip) if d == 1 else (o[i] - slip)
        # skip if the next open is already beyond a level (stale signal after a gap)
        if d == 1 and (o[i] <= sl or o[i] >= t1):
            continue
        if d == -1 and (ao[i] >= sl or ao[i] <= t1):
            continue
        open1 = True; open2 = True; stop2 = sl
        r1 = 0.0; r2 = 0.0; h1 = 0; h2 = 0; hs = 0
        last = min(N - 1, i + max_hold)
        j = i
        day0 = tday[i]
        while True:
            # forced exit: max hold, new trading day, or flat time
            force = (j >= last) or (tday[j] != day0) or (ny_min[j] >= flat_min and ny_min[j] < 17 * 60)
            if d == 1:
                # gap/open beyond stop
                if open1 and o[j] <= sl:
                    r1 = (o[j] - fill) / risk; open1 = False; hs = 1
                if open2 and o[j] <= stop2:
                    r2 = (o[j] - fill) / risk; open2 = False; hs = hs if stop2 != sl else 1
                if open1 or open2:
                    s_hit1 = open1 and l[j] <= sl
                    s_hit2 = open2 and l[j] <= stop2
                    if s_hit1:
                        r1 = (sl - fill) / risk; open1 = False; hs = 1
                    if s_hit2:
                        r2 = (stop2 - fill) / risk; open2 = False
                        if stop2 == sl: hs = 1
                    if open1 and h[j] >= t1:
                        r1 = (t1 - fill) / risk; open1 = False; h1 = 1
                        if be: stop2 = max(stop2, fill)
                    if open2 and h[j] >= t2:
                        r2 = (t2 - fill) / risk; open2 = False; h2 = 1
            else:
                if open1 and ao[j] >= sl:
                    r1 = (fill - ao[j]) / risk; open1 = False; hs = 1
                if open2 and ao[j] >= stop2:
                    r2 = (fill - ao[j]) / risk; open2 = False; hs = hs if stop2 != sl else 1
                if open1 or open2:
                    s_hit1 = open1 and ah[j] >= sl
                    s_hit2 = open2 and ah[j] >= stop2
                    if s_hit1:
                        r1 = (fill - sl) / risk; open1 = False; hs = 1
                    if s_hit2:
                        r2 = (fill - stop2) / risk; open2 = False
                        if stop2 == sl: hs = 1
                    if open1 and al[j] <= t1:
                        r1 = (fill - t1) / risk; open1 = False; h1 = 1
                        if be: stop2 = min(stop2, fill)
                    if open2 and al[j] <= t2:
                        r2 = (fill - t2) / risk; open2 = False; h2 = 1
            if not (open1 or open2):
                break
            if force:
                px = (c[j] - slip) if d == 1 else (ac[j] + slip)
                if open1:
                    r1 = ((px - fill) if d == 1 else (fill - px)) / risk; open1 = False
                if open2:
                    r2 = ((px - fill) if d == 1 else (fill - px)) / risk; open2 = False
                break
            j += 1
        out[k, 0] = 0.5 * (r1 + r2); out[k, 1] = r1; out[k, 2] = r2; out[k, 3] = j
        out[k, 4] = h1; out[k, 5] = h2; out[k, 6] = hs; out[k, 7] = fill
        busy_until = j
    return out


def simulate(sig, spread=SPREAD, max_hold=240, be=False, one_at_a_time=True, slip=SLIP, flat_min=16 * 60 + 50):
    """sig: DataFrame with columns i (1m row index of the signal bar's LAST minute), d (+1/-1),
    ref (signal close, bid), sl, tp1, tp2 (absolute prices). Returns trades DataFrame."""
    d = m1(spread)
    if len(sig) == 0:
        return pd.DataFrame(columns=["time", "d", "r", "r1", "r2", "hit_t1", "hit_t2", "hit_sl", "hold"])
    sig = sig.sort_values("i").reset_index(drop=True)
    res = _sim(d.o.values, d.h.values, d.l.values, d.c.values, d.ao.values, d.ah.values, d.al.values, d.ac.values,
               d.ny_min.values.astype(np.int64), d.tday.values.astype(np.int64),
               sig.i.values.astype(np.int64), sig.d.values.astype(np.int64), sig.ref.values.astype(float),
               sig.sl.values.astype(float), sig.tp1.values.astype(float), sig.tp2.values.astype(float),
               int(max_hold), bool(be), bool(one_at_a_time), float(slip), int(flat_min))
    t = pd.DataFrame(res, columns=["r", "r1", "r2", "exit_i", "hit_t1", "hit_t2", "hit_sl", "fill"])
    t["i"] = sig.i.values; t["d"] = sig.d.values
    t = t.dropna(subset=["r"]).reset_index(drop=True)
    t["time"] = d.time.values[t.i.values + 1]
    t["hold"] = t.exit_i.values - t.i.values - 1
    for c_ in ("hit_t1", "hit_t2", "hit_sl"):
        t[c_] = t[c_].astype(int)
    return t


def levels(b, idx, d, stop_dist, t1_r=1.0, t2_r=2.0):
    """Build the signal frame from bar indices, directions and stop distances (price units)."""
    idx = np.asarray(idx); d = np.asarray(d); sd = np.asarray(stop_dist, float)
    ref = b.c.values[idx]
    return pd.DataFrame({"i": b.end.values[idx], "d": d, "ref": ref, "sl": ref - d * sd,
                         "tp1": ref + d * sd * t1_r, "tp2": ref + d * sd * t2_r})


# ─── statistics ──────────────────────────────────────────────────────────────
def trading_days(a_ts, z_ts):
    d = m1()
    m = (d.time.values >= a_ts) & (d.time.values < z_ts)
    return max(1, len(np.unique(d.tday.values[m])))


def stats(t, label="", days=None):
    if len(t) == 0:
        return {"label": label, "n": 0}
    r = t.r.values
    if days is None:
        days = trading_days(int(t.time.min()), int(t.time.max()) + 1)
    eq = np.cumsum(r); dd = float(np.max(np.maximum.accumulate(eq) - eq)) if len(eq) else 0.0
    gp, gl = r[r > 0].sum(), -r[r < 0].sum()
    return {"label": label, "n": len(r), "per_day": round(len(r) / days, 2),
            "win": round(100 * np.mean(r > 0), 1), "tp1": round(100 * t.hit_t1.mean(), 1),
            "tp2": round(100 * t.hit_t2.mean(), 1), "sl": round(100 * t.hit_sl.mean(), 1),
            "avgR": round(float(r.mean()), 4), "se": round(float(r.std(ddof=1) / math.sqrt(len(r))) if len(r) > 1 else float("nan"), 4),
            "pf": round(float(gp / gl), 2) if gl > 0 else float("inf"), "maxDD": round(dd, 1), "sumR": round(float(r.sum()), 1)}


def by_period(t):
    rows = []
    for name, (a, z) in PERIODS.items():
        m = (t.time >= _ts(a)) & (t.time < _ts(z))
        rows.append(stats(t[m], name, trading_days(_ts(a), _ts(z))))
    return rows


def monthly(t):
    m = pd.to_datetime(t.time, unit="s").dt.strftime("%Y-%m")
    return t.groupby(m).r.agg(["count", "mean"]).round(3)


def random_control(sig_bar_idx, b, stop_fn, t1_r=1.0, t2_r=2.0, n_runs=20, seed=7, **simkw):
    """Random entries: same number of signals, drawn from bars in the same New York hours as the
    real signals, random direction, same stop rule and targets. Returns the list of avg R per run."""
    rng = np.random.default_rng(seed)
    sig_bar_idx = np.asarray(sig_bar_idx)
    if len(sig_bar_idx) == 0:
        return []
    hours = np.unique(b.ny_h.values[sig_bar_idx])
    lo, hi = sig_bar_idx.min(), sig_bar_idx.max()
    pool = np.arange(max(300, lo), hi + 1)
    pool = pool[np.isin(b.ny_h.values[pool], hours)]
    out = []
    for _ in range(n_runs):
        idx = np.sort(rng.choice(pool, size=min(len(pool), len(sig_bar_idx)), replace=False))
        d = rng.choice([-1, 1], size=len(idx))
        sd = np.asarray(stop_fn(b, idx), float)
        ok = np.isfinite(sd) & (sd > 0)
        t = simulate(levels(b, idx[ok], d[ok], sd[ok], t1_r, t2_r), **simkw)
        out.append(float(t.r.mean()) if len(t) else float("nan"))
    return out


def fmt(rows):
    cols = ["label", "n", "per_day", "win", "tp1", "tp2", "sl", "avgR", "se", "pf", "maxDD", "sumR"]
    lines = [" | ".join(cols)]
    for r in rows:
        lines.append(" | ".join(str(r.get(c, "")) for c in cols))
    return "\n".join(lines)


def in_period(b_or_t, name, col="time"):
    a, z = PERIODS[name]
    return (b_or_t[col] >= _ts(a)) & (b_or_t[col] < _ts(z))
