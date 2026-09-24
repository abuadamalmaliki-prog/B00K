"""Frostbite team meeting: the three near-misses side by side, their neighbourhoods, and ensembles.

Candidates (each frozen by its team on DISC = Jan-Apr 2026):
  A-F10  FA Gold Scalper (EMA34>50>200 pullback, M5, 13-17 UTC)        TP1 1.0R  TP2 2.0R  split  120 min
  C-PDHL prior-day high/low close-beyond (M15, H1 EMA50 side, first)    TP1 1.5R  TP2 3.0R  split  120 min
  D-SB   Silver Bullet FVG retest (M5, 03-04/10-11/14-15 NY, H1 side)   TP1 1.5R  TP2 3.0R  be     60 min

Out-of-tuning data for every candidate: VAL (May-Aug 2026), Y2025, HOLD (1-23 Sep 2026).
The choice between candidates below looks at that data, so the winner's figures carry selection bias.
"""
import os, sys, math
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for t in ("teamA", "teamC", "teamD"):
    sys.path.insert(0, os.path.join(HERE, t))
import frost  # noqa: E402
import teamA, teamC, teamD  # noqa: E402

OOT = ("VAL", "Y2025", "HOLD")


def cand_A(tf=5, sess="13-17", adx_min=20, t1=1.0, t2=2.0, be=False, hold=120):
    tf_, idx, d, sd, _ = teamA.build("F10", dict(tf=tf, sess=sess, adx_min=adx_min))
    return frost.levels(teamA.B(tf_), idx, d, sd, t1, t2), dict(be=be, max_hold=hold)


def cand_C(tf=15, sess="all", htf=True, first=True, t1=1.5, t2=3.0, hold=120, be=False):
    s = teamC.FAMILIES["PDHL"][1](dict(tf=tf, sess=sess, htf=htf, first=first))
    return s.sig(t1, t2, 1.0), dict(be=be, max_hold=hold)


def cand_D(tf=5, gmin=0.25, htf=1, t1=1.5, t2=3.0, be=True, hold=60):
    return teamD.make_sig("SILVER_BULLET", dict(tf=tf, gmin=gmin, htf=htf), (t1, t2, be, hold)), dict(be=be, max_hold=hold)


CANDS = {"A-F10": cand_A, "C-PDHL": cand_C, "D-SB": cand_D}


def sim(sig, kw, **extra):
    t = frost.simulate(sig, **kw, **extra)
    t["entry_i"] = t.i + 1
    return t


def period_table(t, name):
    rows = frost.by_period(t)
    oot = pd.concat([t[frost.in_period(t, p)] for p in OOT])
    s = frost.stats(oot, "OOT")
    s["t"] = round(s["avgR"] / s["se"], 2) if s.get("se") else float("nan")
    out = [dict(r, cand=name) for r in rows] + [dict(s, cand=name)]
    return out


def merge_one_at_a_time(trades):
    """Union of several candidates' trades; a trade is skipped if another is still open (first come)."""
    allt = pd.concat(trades, ignore_index=True).sort_values(["entry_i", "src"]).reset_index(drop=True)
    keep, busy = [], -1
    for k, r in allt.iterrows():
        if r.entry_i <= busy:
            continue
        keep.append(k); busy = r.exit_i
    return allt.loc[keep].reset_index(drop=True)


def neighbourhood(name):
    """Small moves around the frozen settings, scored on out-of-tuning data only (VAL + Y2025)."""
    grids = {
        "A-F10": [dict(t1=t1, t2=t2, hold=h) for t1 in (0.75, 1.0, 1.5) for t2 in (1.5, 2.0, 3.0) if t2 > t1 for h in (60, 120, 240)]
                 + [dict(adx_min=25), dict(sess="07-17"), dict(tf=15)],
        "C-PDHL": [dict(t1=t1, t2=t2, hold=h) for t1 in (1.0, 1.5) for t2 in (2.0, 3.0) for h in (60, 120, 240)]
                  + [dict(tf=5), dict(htf=False), dict(first=False)],
        "D-SB": [dict(t1=t1, t2=t2, hold=h, be=be) for t1 in (1.0, 1.5) for t2 in (2.0, 3.0) for h in (60, 120) for be in (True, False)]
                + [dict(gmin=0.5), dict(htf=0)],
    }
    rows = []
    for p in grids[name]:
        sig, kw = CANDS[name](**p)
        t = sim(sig, kw)
        m = frost.in_period(t, "VAL") | frost.in_period(t, "Y2025")
        s = frost.stats(t[m])
        rows.append(dict(p=str(p), n=s["n"], avgR=s["avgR"], t=round(s["avgR"] / s["se"], 2)))
    return pd.DataFrame(rows)


def main():
    print("coverage", frost.coverage())
    trades, table = {}, []
    for name, fn in CANDS.items():
        sig, kw = fn()
        t = sim(sig, kw); t["src"] = name
        trades[name] = t
        table += period_table(t, name)
        ts = sim(sig, kw, spread=0.45, slip=0.05)
        m = frost.in_period(ts, "VAL") | frost.in_period(ts, "Y2025") | frost.in_period(ts, "HOLD")
        print(f"{name} stress (spread 0.45, slip 0.05) OOT avgR {ts[m].r.mean():+.4f} n={m.sum()}")
    cols = ["cand", "label", "n", "per_day", "win", "tp1", "tp2", "sl", "avgR", "se", "t", "pf", "maxDD", "sumR"]
    df = pd.DataFrame(table)[cols]
    print("\n== candidates by period ==\n" + df.to_string(index=False))

    # correlation of daily R between candidates (out-of-tuning days)
    daily = {}
    for name, t in trades.items():
        day = pd.to_datetime(t.time, unit="s").dt.date
        daily[name] = t.groupby(day).r.sum()
    dd = pd.DataFrame(daily).fillna(0.0)
    print("\n== daily R correlation (all days with any trade) ==\n" + dd.corr().round(3).to_string())

    # ensembles
    ens = {}
    ens["E3 one-at-a-time A+C+D"] = merge_one_at_a_time(list(trades.values()))
    ens["E2 one-at-a-time A+C"] = merge_one_at_a_time([trades["A-F10"], trades["C-PDHL"]])
    ens["E2 one-at-a-time C+D"] = merge_one_at_a_time([trades["C-PDHL"], trades["D-SB"]])
    ens["E3 concurrent A+C+D"] = pd.concat(list(trades.values()), ignore_index=True)
    rows = []
    for name, t in ens.items():
        rows += period_table(t, name)
    print("\n== ensembles by period ==\n" + pd.DataFrame(rows)[cols].to_string(index=False))
    e = ens["E3 one-at-a-time A+C+D"]
    print("\nE3 one-at-a-time share by source:", e.src.value_counts().to_dict())
    print("\n== E3 one-at-a-time monthly ==\n" + frost.monthly(e).to_string())

    for name in CANDS:
        nb_ = neighbourhood(name)
        print(f"\n== {name} neighbourhood (VAL+Y2025) == positive {int((nb_.avgR > 0).sum())}/{len(nb_)}, "
              f"median avgR {nb_.avgR.median():+.4f}\n" + nb_.to_string(index=False))




# ─── the decision: Frostbite = A-F10 (Icicle) + C-PDHL (Avalanche), one trade at a time ─────
def frostbite_signals():
    """Union of the two setups as one signal frame. If both fire on the same bar, Icicle (A) wins.
    Both use split orders and a 120-minute limit, so one simulate() call reproduces the indicator."""
    a, _ = cand_A(); c, _ = cand_C()
    a = a.assign(src=0); c = c.assign(src=1)
    u = pd.concat([a, c], ignore_index=True).sort_values(["i", "src"], kind="stable")
    return u.drop_duplicates("i", keep="first").reset_index(drop=True)


FROST_SIM = dict(be=False, max_hold=120)


def final():
    sig = frostbite_signals()
    t = frost.simulate(sig.drop(columns="src"), **FROST_SIM)
    t = t.merge(sig[["i", "src"]], on="i", how="left")
    cols = ["label", "n", "per_day", "win", "tp1", "tp2", "sl", "avgR", "se", "pf", "maxDD", "sumR"]
    rows = frost.by_period(t)
    oot = pd.concat([t[frost.in_period(t, p)] for p in OOT])
    s = frost.stats(oot, "OOT"); rows.append(s)
    print("\n== FROSTBITE (A+C, one at a time, single pass) ==\n" + pd.DataFrame(rows)[cols].to_string(index=False))
    print(f"OOT t = {s['avgR'] / s['se']:.2f}")
    for src, nm in ((0, "Icicle (A)"), (1, "Avalanche (C)")):
        x = oot[oot.src == src]
        print(f"  {nm}: OOT n={len(x)} avgR={x.r.mean():+.4f}")
    for sp, sl in ((0.45, 0.05), (0.60, 0.05)):
        ts = frost.simulate(sig.drop(columns="src"), spread=sp, slip=sl, **FROST_SIM)
        m = frost.in_period(ts, "VAL") | frost.in_period(ts, "Y2025") | frost.in_period(ts, "HOLD")
        print(f"stress spread {sp} slip {sl}: OOT avgR {ts[m].r.mean():+.4f} (n={int(m.sum())}); "
              f"VAL {ts[frost.in_period(ts, 'VAL')].r.mean():+.4f}")
    # random control over the out-of-tuning span: same count, same NY hours, 1.5 x ATR(M15) stops, TP 1.5/3
    b15 = teamC.B(15)
    m15 = frost.in_period(b15, "VAL")
    vidx = np.flatnonzero(frost.in_period(pd.DataFrame({"time": frost.m1().time.values[sig.i.values]}), "VAL").values)
    # map VAL signal rows to M15 bar indices by time for the hour profile
    idx15 = np.searchsorted(b15.end.values, sig.i.values[vidx])
    idx15 = idx15[(idx15 >= 0) & (idx15 < len(b15))]
    rc = frost.random_control(np.unique(idx15), b15, lambda b, i: 1.5 * b.atr.values[i], 1.5, 3.0, n_runs=30, **FROST_SIM)
    rc = np.array(rc)
    val = t[frost.in_period(t, "VAL")].r.mean()
    print(f"random control VAL (30 runs): median {np.median(rc):+.4f}, 5-95% [{np.percentile(rc, 5):+.4f}, "
          f"{np.percentile(rc, 95):+.4f}] vs Frostbite VAL {val:+.4f}")
    print("\n== FROSTBITE monthly ==\n" + frost.monthly(t).to_string())
    eq = t.r.cumsum().values
    print(f"\nall periods: n={len(t)}, sumR={t.r.sum():+.1f}, max drawdown {np.max(np.maximum.accumulate(eq) - eq):.1f}R, "
          f"longest losing streak {max_streak(t.r.values)}")
    return t


def max_streak(r):
    best = cur = 0
    for x in r:
        cur = cur + 1 if x < 0 else 0
        best = max(best, cur)
    return best


if __name__ == "__main__":
    main()
    final()
