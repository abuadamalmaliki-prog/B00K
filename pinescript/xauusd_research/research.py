"""Reproduce every table behind xauusd_asian_range_breakout.pine.

Run get_data.py first (same folder), then:  python3 research.py [section ...]
Sections: tz slots artifact sessions predict patterns strategies grid final   (default: all)
All times are New York local time. Costs: 1 bp of price per round trip unless stated.
"""
import itertools
import sys

import numpy as np
import pandas as pd

from arb import H, asia_breakout, load_days
from patterns import features, fwd
from sessions import load, seg_return
from sim import run_bracket, summarize


def tz():
    """The data's clock is New York local time: the break and the US data spikes do not move with DST."""
    m = pd.read_parquet("m1_raw.parquet")
    m["hr"] = m.ts.dt.hour
    for mon in (1, 7):
        sub = m[(m.ts.dt.month == mon) & (m.ts.dt.weekday < 4) & m.ts.dt.year.between(2015, 2024)]
        print(f"month {mon}: emptiest hour = {sub.groupby('hr').size().idxmin()}:00 (gold's 17:00-18:00 NY break)")
    m["ret"] = np.log(m.c).diff().abs()
    m["mod"] = m.ts.dt.hour * 60 + m.ts.dt.minute
    for mon, nm in ((1, "Jan"), (7, "Jul")):
        g = m[(m.ts.dt.month == mon) & m.ts.dt.year.between(2012, 2024)].groupby("mod")["ret"].mean()
        print(nm, "busiest minutes:", [f"{k // 60:02d}:{k % 60:02d}" for k in g.nlargest(5).index])


def slots():
    b = pd.read_parquet("m5.parquet")
    b["r"] = np.log(b.c / b.o)
    b["slot"] = (b.index.hour * 60 + b.index.minute) // 30
    rows = []
    for s in range(48):
        row = [f"{s // 2:02d}:{(s % 2) * 30:02d}"]
        for a, z in ((2009, 2014), (2015, 2019), (2020, 2026)):
            x = b[(b.slot == s) & b.index.year.isin(range(a, z + 1))]
            d = x.groupby(x.index.date)["r"].sum()
            row += [d.mean() * 1e4, d.mean() / d.std() * np.sqrt(len(d)) if len(d) > 30 else np.nan]
        rows.append(row)
    print(pd.DataFrame(rows, columns=["NY", "bp 09-14", "t", "bp 15-19", "t", "bp 20-26", "t"]).round(2).to_string(index=False))


def artifact():
    """The +bp at 18:00 sits in the first minute after the reopen: spread normalisation, not a tradable move."""
    m = pd.read_parquet("m1_raw.parquet").set_index("ts")
    m["r"] = np.log(m.c / m.o)
    m["hl"] = np.log(m.h / m.l)
    x = m[(m.index.hour == 18) & (m.index.minute < 6) & (m.index.year >= 2015)]
    print(x.groupby(x.index.minute).agg(mean_bp=("r", lambda s: s.mean() * 1e4), range_bp=("hl", lambda s: s.mean() * 1e4)).round(2))


def sessions():
    b = load()
    def sess(m):
        if 18 * 60 + 5 <= m or m < 180: return "Asia"
        if 180 <= m < 500: return "London"
        if 500 <= m < 990: return "NY"
        return None
    b["sess"] = [sess(m) for m in b["mod"]]
    b["r"] = np.log(b.c / b.o)
    d = b.dropna(subset=["sess"]).groupby(["tday", "sess"])["r"].sum().unstack()
    d = d[d.index.dayofweek < 5]
    for a, z in ((2009, 2013), (2014, 2017), (2018, 2021), (2022, 2026)):
        x = d[(d.index.year >= a) & (d.index.year <= z)]
        print(f"{a}-{z}: " + " | ".join(f"{c} {x[c].mean() * 1e4:+.2f}bp (t={x[c].mean() / x[c].std() * np.sqrt(x[c].count()):+.2f})" for c in d.columns))


def predict():
    b = load()
    s = {"Asia": seg_return(b, 1110, 180), "London": seg_return(b, 180, 500),
         "NYopen30": seg_return(b, 500, 530), "NYrest": seg_return(b, 530, 990), "NY": seg_return(b, 500, 990)}
    d = pd.DataFrame(s)
    d["prevNY"] = d["NY"].shift(1)
    d["AsiaLondon"] = d["Asia"] + d["London"]
    for p, q in (("prevNY", "Asia"), ("Asia", "London"), ("London", "NY"), ("AsiaLondon", "NY"), ("NYopen30", "NYrest")):
        for a, z in ((2009, 2017), (2018, 2026)):
            x = d[(d.index.year >= a) & (d.index.year <= z)][[p, q]].dropna()
            up, dn = x[x[p] > 0][q], x[x[p] < 0][q]
            t = (up.mean() - dn.mean()) / np.sqrt(up.var() / len(up) + dn.var() / len(dn))
            print(f"{p:>10} -> {q:<7} {a}-{z}: t={t:+.2f}")


def patterns():
    for tf in ("m5", "m15"):
        b = pd.read_parquet(f"{tf}.parquet")
        b = b[~((b.index.hour == 18) & (b.index.minute < 30)) & ~((b.index.hour == 16) & (b.index.minute >= 30)) & (b.index.hour != 17)]
        P, _ = features(b)
        yr = b.index.year.values
        print(f"== {tf}: forward return in the pattern's direction, bp (cost ~1 bp)")
        for name, sig in P.items():
            line = f"{name:<13}"
            for n in (1, 3, 6):
                f = fwd(b.c.values, n) * sig
                for a, z in ((2009, 2017), (2018, 2026)):
                    x = f[(sig != 0) & (yr >= a) & (yr <= z) & ~np.isnan(f)]
                    line += f" | {n}b {a % 100:02d}-{z % 100:02d} {x.mean() * 1e4:+.2f} (t{x.mean() / x.std() * np.sqrt(len(x)):+.1f})"
            print(line)


def strategies():
    days = load_days("m5")
    def orb(name, r0, r1, e_end, x_end, tp_R):
        t = asia_breakout(days, r0=r0, r1=r1, e_end=e_end, x_end=x_end, tp_R=tp_R)
        summarize(name, list(t[["day", "side", "entry", "exit", "risk", "why"]].itertuples(index=False, name=None)))
    orb("London ORB 02:00-03:00, TP 1R ", H(2), H(3), H(6), H(8, 20), 1.0)
    orb("London ORB 02:00-03:00, TP 2R ", H(2), H(3), H(6), H(8, 20), 2.0)
    orb("COMEX ORB 08:20-08:50, TP 1R  ", H(8, 20), H(8, 50), H(11), H(16, 30), 1.0)
    orb("COMEX ORB 08:20-08:50, TP 2R  ", H(8, 20), H(8, 50), H(11), H(16, 30), 2.0)
    orb("Asia range break, exit 11:00  ", H(18, 30), H(3), H(8, 20), H(11), None)


def grid():
    days = load_days("m5")
    rows = []
    def sr(x):
        n = x.gross_bp - 1.0
        yrs = (pd.to_datetime(x.day).max() - pd.to_datetime(x.day).min()).days / 365.25
        return n.mean() / n.std() * np.sqrt(len(n) / yrs)
    for x_end, tp, slm, e_end in itertools.product([(8, 20), (10, 0), (11, 0), (12, 0), (13, 30), (16, 30)], [None, 1.0, 1.5, 2.0, 3.0], ["opposite", "mid"], [(6, 0), (8, 20)]):
        if H(*e_end) > H(*x_end): continue
        t = asia_breakout(days, x_end=H(*x_end), tp_R=tp, sl_mode=slm, e_end=H(*e_end))
        rows.append((f"{x_end[0]:02d}:{x_end[1]:02d}", tp or 0, slm, f"{e_end[0]:02d}:{e_end[1]:02d}", sr(t[t.yr <= 2017]), sr(t[t.yr >= 2018])))
    g = pd.DataFrame(rows, columns=["exit", "tpR", "sl", "entry_until", "SR_is", "SR_oos"])
    exits, tps = sorted(g.exit.unique()), sorted(g.tpR.unique())
    def nb(r):
        ei, ti = exits.index(r.exit), tps.index(r.tpR)
        return g[(g.sl == r.sl) & (g.entry_until == r.entry_until) & g.exit.isin(exits[max(0, ei - 1):ei + 2]) & g.tpR.isin(tps[max(0, ti - 1):ti + 2])].SR_is.mean()
    g["neighbour_SR_is"] = g.apply(nb, axis=1)
    print(f"{len(g)} configs; positive in-sample {100 * (g.SR_is > 0).mean():.0f}%, out of sample {100 * (g.SR_oos > 0).mean():.0f}%")
    print(g.sort_values("neighbour_SR_is", ascending=False).head(8).round(2).to_string(index=False))


def final():
    for tf, bm in (("m5", 5), ("m15", 15)):
        t = asia_breakout(load_days(tf), x_end=H(13, 30), tp_R=3.0, sl_mode="opposite", e_end=H(8, 20), bar_min=bm)
        t["Rnet"] = t.R - 1e-4 * t.entry / t.risk
        for a, z in ((2009, 2017), (2018, 2026), (2009, 2026)):
            x = t[(t.yr >= a) & (t.yr <= z)].Rnet
            print(f"{tf} {a}-{z}: n={len(x)} win={100 * (x > 0).mean():.0f}% avgR={x.mean():+.4f} t={x.mean() / x.std() * np.sqrt(len(x)):+.2f} totalR={x.sum():+.0f}")
        eq = t.Rnet.cumsum()
        print(f"{tf} max drawdown {float((eq.cummax() - eq).max()):.0f}R; by year: " + " ".join(f"{y}:{v:+.0f}" for y, v in t.groupby('yr').Rnet.sum().items()))


SECTIONS = dict(tz=tz, slots=slots, artifact=artifact, sessions=sessions, predict=predict,
                patterns=patterns, strategies=strategies, grid=grid, final=final)
if __name__ == "__main__":
    for s in (sys.argv[1:] or list(SECTIONS)):
        print(f"\n######## {s}")
        SECTIONS[s]()
