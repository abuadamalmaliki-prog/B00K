"""Look-ahead and sanity tests for smc.py. Run: python3 test_smc.py (pytest-compatible)."""
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smc  # noqa: E402

CSV = os.environ.get(
    "XAU_CSV",
    "/tmp/claude-0/-home-user-B00K/0fcfe737-4e2c-5a50-a490-afd9bdd38f24/scratchpad/xau.csv",
)
_CACHE = {}


def load(tf="M1"):
    if tf not in _CACHE:
        d = pd.read_csv(CSV, parse_dates=["Datetime"])
        d = d[d["Timeframe"] == tf].drop(columns="Timeframe")
        d = d.rename(columns=str.lower).set_index("datetime").sort_index()
        _CACHE[tf] = d[~d.index.duplicated()]
    return _CACHE[tf]


def _same(a, b):
    a = a.to_numpy(dtype=np.float64)
    b = b.to_numpy(dtype=np.float64)
    return (a == b) | (np.isnan(a) & np.isnan(b))


def _check_no_lookahead(df, n_cuts=12, seed=0):
    full = smc.compute_all(df)
    rng = np.random.default_rng(seed)
    cuts = sorted(set(rng.integers(50, len(df), n_cuts).tolist()) | {len(df) // 2})
    for k in cuts:
        part = smc.compute_all(df.iloc[:k])
        assert list(part.columns) == list(full.columns)
        # last row (spec) and, stronger, the whole prefix must match
        ok_last = _same(part.iloc[[-1]], full.iloc[[k - 1]])
        assert ok_last.all(), f"k={k}: last-row mismatch in {list(part.columns[~ok_last[0]])}"
        ok = _same(part, full.iloc[:k])
        bad = part.columns[~ok.all(axis=0)]
        assert ok.all(), f"k={k}: prefix mismatch in {list(bad)}"
    return cuts


def test_no_lookahead_m1():
    _check_no_lookahead(load("M1").iloc[:50_000])


def test_no_lookahead_h1():
    _check_no_lookahead(load("H1"), n_cuts=8, seed=1)


def test_basic_invariants():
    df = load("M1").iloc[:50_000]
    f = smc.compute_all(df)
    assert f.index.equals(df.index)
    p = f["pd_pos"].dropna()
    assert ((p >= 0) & (p <= 1)).all()
    assert set(np.unique(f["trend"])) <= {-1, 0, 1}
    assert not ((f["bos"] != 0) & (f["choch"] != 0)).any()
    assert (f["bull_fvg_top"] > f["bull_fvg_bot"]).where(f["bull_fvg_top"].notna(), True).all()
    assert (f["bear_fvg_top"] > f["bear_fvg_bot"]).where(f["bear_fvg_top"].notna(), True).all()
    # session levels vs an independent groupby reference
    date = df.index.normalize()
    hour = df.index.hour
    asia = df["high"][hour < 7].groupby(date[hour < 7]).max()
    today = pd.Series(date, index=df.index).map(asia)
    prev = pd.Series(date, index=df.index).map(asia.shift(1))
    m = (hour >= 7) & today.notna().to_numpy()
    assert (f["asia_high"][m] == today[m]).all()          # published after 07:00 same day
    m = (hour < 7) & prev.notna().to_numpy()
    assert (f["asia_high"][m] == prev[m]).all()           # during session: previous completed one
    dh = df["high"].groupby(date).max()
    exp_pdh = pd.Series(date, index=df.index).map(dh.shift(1))
    assert _same(f["pdh"], exp_pdh).all()


def event_frequencies(df, f):
    days = df.index.normalize().nunique()
    return {
        "days": days,
        "bos/day": (f["bos"] != 0).sum() / days,
        "choch/day": (f["choch"] != 0).sum() / days,
        "fvg/day": (f["fvg_new"] != 0).sum() / days,
        "sweep/day": (f["sweep"] != 0).sum() / days,
        "bull_ob_present": f["bull_ob_top"].notna().mean(),
        "bear_ob_present": f["bear_ob_top"].notna().mean(),
    }


if __name__ == "__main__":
    for name, fn in [("no_lookahead_m1", test_no_lookahead_m1),
                     ("no_lookahead_h1", test_no_lookahead_h1),
                     ("basic_invariants", test_basic_invariants)]:
        fn()
        print(f"PASS {name}")
    for tf in ("M1", "H1"):
        df = load(tf)
        smc.compute_all(df.iloc[:1000])  # warm numba
        t0 = time.perf_counter()
        f = smc.compute_all(df)
        dt = time.perf_counter() - t0
        print(f"{tf}: {len(df)} rows, compute_all {dt:.2f}s")
        print("  ", {k: round(v, 3) for k, v in event_frequencies(df, f).items()})
