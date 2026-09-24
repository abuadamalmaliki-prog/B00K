"""agentD grid run: every config of every family, net of costs; select per family on SEEN only
(score = min SEEN-half net avg R, n>=30 per half), then report the chosen config untouched on UNSEEN.
Usage (from v15/): python3 agentD/run.py"""
import sys, os, time, json, pickle
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fam, lib
from sim15 import report, stats, SEEN, UNSEEN

def cell(s): return f"{s['win']:.1f}% {s['avgR']:+.3f}±{s['se']:.3f} (n={s['n']})"

t0 = time.time()
chosen, grid_rows = {}, []
for fname, grid in fam.GRIDS.items():
    print(f"\n=== {fname} ({len(grid)} configs) ===", flush=True)
    best = None
    for name, gen, tf in grid:
        res = lib.evaluate(gen, tf)
        allt = lib.flat(res)
        gr = stats(lib.flat(lib.evaluate(gen, tf, gross=True)))
        sc = lib.score(res)
        rk = sum(t["riskPips"] for t in allt) / max(1, len(allt))
        print(report(name, res) + f" | GROSS R={gr['avgR']:+.3f} | score={sc:+.3f}", flush=True)
        grid_rows.append(dict(family=fname, config=name, score=sc, gross=gr["avgR"],
                              **{f"{g}{h+1}": stats(res[(g, h)]) for g in ("seen", "unseen") for h in (0, 1)}))
        if best is None or sc > best[0]: best = (sc, name, gen, tf, res)
    chosen[fname] = best
    print(f"--> chosen on SEEN: {best[1]} (score {best[0]:+.3f})  [{time.time()-t0:.0f}s]", flush=True)

print("\n\n=========== CHOSEN CONFIGS (selected on SEEN only) ===========")
summary = {}
for fname, (sc, name, gen, tf, res) in chosen.items():
    allt, seen, uns = lib.flat(res), lib.flat(res, "seen"), lib.flat(res, "unseen")
    setups = {s: gen(s, tf) for s in lib.ALL}
    gres = lib.evaluate(None, tf, gross=True, setups=setups)
    g_all, g_seen, g_uns = stats(lib.flat(gres)), stats(lib.flat(gres, "seen")), stats(lib.flat(gres, "unseen"))
    ctl = stats(lib.control(setups, tf))
    u1, u2 = stats(res[("unseen", 0)]), stats(res[("unseen", 1)])
    passed = u1["avgR"] > 0 and u2["avgR"] > 0 and u1["n"] > 0 and u2["n"] > 0
    A, S, U = stats(allt), stats(seen), stats(uns)
    row = dict(family=fname, config=name, tf=tf, ALL=A, SEEN=S, UNSEEN=U, unseen_h1=u1, unseen_h2=u2,
               seen_h1=stats(res[("seen", 0)]), seen_h2=stats(res[("seen", 1)]),
               gross_all=g_all, gross_seen=g_seen, gross_unseen=g_uns, tpw=lib.tpw(allt), hold=lib.hold(allt),
               control=ctl, PASS=passed, win60=A["win"] >= 60 or U["win"] >= 60,
               avg_risk_atr=None)
    summary[fname] = row
    print(f"\n{fname}: {name}")
    print(f"  ALL    {cell(A)}   SEEN {cell(S)}   UNSEEN {cell(U)}")
    print(f"  SEEN halves  {cell(row['seen_h1'])} | {cell(row['seen_h2'])}")
    print(f"  UNSEEN halves {cell(u1)} | {cell(u2)}   PASS={passed}  win>=60%={row['win60']}")
    print(f"  GROSS  ALL {g_all['avgR']:+.3f}±{g_all['se']:.3f} win {g_all['win']:.1f}% | SEEN {g_seen['avgR']:+.3f} | UNSEEN {g_uns['avgR']:+.3f}")
    print(f"  trades/week (11 instr) {row['tpw']:.1f}   avg hold {row['hold']:.1f} h")
    print(f"  CONTROL random entry, same geometry: {cell(ctl)}")
    for sym in lib.ALL:
        s = stats([t for t in allt if t["sym"] == sym])
        print(f"    {sym} n={s['n']} win={s['win']:.1f}% R={s['avgR']:+.3f}±{s['se']:.3f}")
    assert all("sym" in t and "setup" in t for t in allt)
    pickle.dump(allt, open(os.path.join(HERE, f"{fname}.pkl"), "wb"))

json.dump(dict(summary=summary, grid=grid_rows), open(os.path.join(HERE, "results.json"), "w"), indent=1, default=str)
print(f"\ndone in {time.time()-t0:.0f}s")
