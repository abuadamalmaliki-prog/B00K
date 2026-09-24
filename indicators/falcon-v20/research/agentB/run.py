"""agentB runner: grids for 4 families, SEEN-only selection, UNSEEN validation, random controls, pickles."""
import sys, os, json, pickle, statistics, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fam
from sim15 import stats

GRIDS = {
 "F1_sweep": [(f"F1 {'H1' if tf==3600 else 'H4'} tp{k}R {'T'+str(tb) if tb else 'noT'}", fam.f1(tf, k, tb))
              for tf, tb0 in ((3600, 24), (14400, 12)) for k in (0.5, 0.75, 1.0) for tb in (None, tb0)],
 "F2_london": [(f"F2 stop={sm} tp{tf_}W {'flat12' if fh else 'noT'}", fam.f2(sm, tf_, fh))
               for sm in ("mid", "opp") for tf_ in (0.5, 1.0) for fh in (None, 12)],
 "F3_nymom": [(f"F3 tp{k}R {'strong' if st else 'weak'} {'flat16' if fh else 'noT'}", fam.f3(k, st, fh))
              for k in (0.5, 0.75, 1.0) for st in (False, True) for fh in (None, 16)],
 "F4_trendpb": [(f"F4 tp{k}R stop={sm} {'T24' if tb else 'noT'}", fam.f4(k, sm, tb))
                for k in (0.5, 0.75, 1.0) for sm in ("swing", "atr") for tb in (None, 24)],
}

def summarize(res, weeks):
    allt = [t for v in res.values() for t in v]
    seen = res[("seen", 0)] + res[("seen", 1)]; uns = res[("unseen", 0)] + res[("unseen", 1)]
    out = {"ALL": stats(allt), "seen": stats(seen), "unseen": stats(uns)}
    for g in ("seen", "unseen"):
        for h in (0, 1): out[f"{g}{h+1}"] = stats(res[(g, h)])
    out["tpw"] = sum(sum(1 for t in allt if t["sym"] == s) / w for s, w in weeks.items())  # portfolio trades/week (11 instr.)
    out["hold_h"] = statistics.mean((t["exit_time"] - t["time"]) / 3600 for t in allt) if allt else 0
    out["why"] = {w: sum(1 for t in allt if t["why"] == w) for w in ("tp", "sl", "time")}
    return out

def fmt(s):
    return f"{s['win']:5.1f}% {s['avgR']:+.3f}±{s['se']:.3f} (n={s['n']})"

def line(name, S):
    return (f"{name:34s} ALL {fmt(S['ALL'])} | SEEN {fmt(S['seen'])} [h1 {S['seen1']['win']:.1f}%/{S['seen1']['avgR']:+.3f} h2 {S['seen2']['win']:.1f}%/{S['seen2']['avgR']:+.3f}]"
            f" | UNSEEN {fmt(S['unseen'])} [h1 {S['unseen1']['win']:.1f}%/{S['unseen1']['avgR']:+.3f} h2 {S['unseen2']['win']:.1f}%/{S['unseen2']['avgR']:+.3f}]"
            f" | {S['tpw']:.1f}/wk hold {S['hold_h']:.1f}h {S['why']}")

def select(rows):
    """Pre-declared SEEN-only rule: among configs with SEEN pooled win >= 65%, maximise
    min(seen-h1 avgR, seen-h2 avgR); if none reach 65%, maximise that over all configs."""
    key = lambda r: min(r[1]["seen1"]["avgR"], r[1]["seen2"]["avgR"])
    elig = [r for r in rows if r[1]["seen"]["win"] >= 65]
    return max(elig or rows, key=key)

def passes(S):
    return all(S[c]["win"] >= 65 and S[c]["avgR"] > 0 for c in ("unseen1", "unseen2"))

if __name__ == "__main__":
    allres, chosen = {}, {}
    for fname, grid in GRIDS.items():
        rows = []
        print(f"\n=== {fname} ({len(grid)} configs) ===", flush=True)
        for name, (gen, tf) in grid:
            res, weeks = fam.evaluate(gen, tf)
            S = summarize(res, weeks); rows.append((name, S, res, gen, tf))
            print(line(name, S), flush=True)
            allres[name] = S
        name, S, res, gen, tf = select(rows)
        # controls: same geometry, random entries (random bar+dir) and same-bar random direction, 10 seeds each
        ctl = {}
        for mode in ("rand", "dir"):
            pooled, wk = [], None
            for seed in range(10):
                r2, wk = fam.evaluate(fam.control(gen, tf, mode, seed), tf)
                pooled += [t for v in r2.values() for t in v]
            cs = stats(pooled); cs["tpw"] = sum(sum(1 for t in pooled if t["sym"] == s) / w for s, w in wk.items()) / 10
            ctl[mode] = cs
        chosen[fname] = dict(name=name, S=S, passed=passes(S), ctl=ctl)
        print(f"--> SELECTED (seen-only): {name}   UNSEEN PASS={passes(S)}")
        for mode, cs in ctl.items():
            print(f"    control[{mode}] win={cs['win']:.1f}% avgR={cs['avgR']:+.3f}±{cs['se']:.3f} n/seed={cs['n']/10:.0f} ({cs['tpw']:.1f}/wk)")
    json.dump(dict(all=allres, chosen=chosen), open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.json"), "w"), indent=1, default=str)
