"""Run every config of every family, select on SEEN, validate on UNSEEN, random-entry control, save pickles."""
import sys, os, json, pickle, time, statistics
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim15 import evaluate, stats, report, SEEN, UNSEEN
from common import bars
from agentA.mr import FAMILIES, random_control, ALL

T0 = time.time()
first = min(bars(s, 3600)[0][0] for s in ALL); last = max(bars(s, 3600)[-1][0] for s in ALL)
WEEKS = (last - first) / (7 * 86400)
SYM_WEEKS = {s: (bars(s, 3600)[-1][0] - bars(s, 3600)[0][0]) / (7 * 86400) for s in ALL}
import sim15

def gross(gen):
    """diagnostic only: same rules with zero spread and zero swap"""
    saved = dict(sim15.SPREAD)
    for k in sim15.SPREAD: sim15.SPREAD[k] = 0.0
    try: return evaluate(gen, 3600, swap=0.0)
    finally: sim15.SPREAD.update(saved)

def control(gen, res, seeds=5):
    setups = {}
    for ts in res.values():
        for t in ts:
            if t['sym'] not in setups: setups[t['sym']] = {st[0]: st for st in gen(t['sym'], 3600)}
    taken = {}
    for ts in res.values():
        for t in ts: taken.setdefault(t['sym'], []).append(setups[t['sym']][t['i']])
    cs = [summ(evaluate(random_control(gen, taken, sd), 3600)) for sd in range(seeds)]
    return {g: dict(win=statistics.mean(c[g]['win'] for c in cs), avgR=statistics.mean(c[g]['avgR'] for c in cs),
                    n=statistics.mean(c[g]['n'] for c in cs)) for g in ('all', 'seen', 'unseen')}

def summ(res):
    seen = res[('seen', 0)] + res[('seen', 1)]; uns = res[('unseen', 0)] + res[('unseen', 1)]
    allt = seen + uns
    d = dict(all=stats(allt), seen=stats(seen), unseen=stats(uns),
             cells={f"{g}{h+1}": stats(res[(g, h)]) for g in ('seen', 'unseen') for h in (0, 1)})
    d['tpw'] = sum(sum(1 for t in allt if t['sym'] == sy) / SYM_WEEKS[sy] for sy in ALL)
    d['hold_h'] = statistics.mean((t['exit_time'] - t['time']) / 3600 for t in allt) if allt else 0
    d['rr'] = statistics.mean(t['rewardPips'] / t['riskPips'] for t in allt) if allt else 0
    d['exits'] = {w: sum(1 for t in allt if t['why'] == w) for w in ('tp', 'sl', 'time')}
    return d

def seen_ok(d):
    c = d['cells']
    return all(c[k]['win'] >= 65 and c[k]['avgR'] > 0 for k in ('seen1', 'seen2'))

def passes(d):
    c = d['cells']
    return all(c[k]['win'] >= 65 and c[k]['avgR'] > 0 for k in ('unseen1', 'unseen2'))

def select(rows):
    el = [r for r in rows if seen_ok(r[2])]
    if el: return max(el, key=lambda r: r[2]['seen']['avgR']), 'eligible'
    el = [r for r in rows if r[2]['seen']['win'] >= 65]
    if el: return max(el, key=lambda r: r[2]['seen']['avgR']), 'fallback(win>=65 pooled)'
    return max(rows, key=lambda r: r[2]['seen']['avgR']), 'fallback(best avgR)'

def with_setups(gen, res):
    """attach 'setup' (exact tuple) and 'sym' to each trade dict"""
    cache = {}
    for k, ts in res.items():
        for t in ts:
            s = t['sym']
            if s not in cache: cache[s] = {st[0]: st for st in gen(s, 3600)}
            t['setup'] = cache[s][t['i']]
    return res

out = {}
lines = []
for fam, grid in FAMILIES:
    rows = []
    for name, gen, params in grid:
        res = evaluate(gen, 3600)
        d = summ(res)
        ctl = control(gen, res); gr = summ(gross(gen))
        d['control'] = ctl; d['gross'] = {g: gr[g] for g in ('all', 'seen', 'unseen')}
        rows.append((name, gen, d, params, res, ctl))
        lines.append(report(name, res) + f" | RR={d['rr']:.2f} tpw={d['tpw']:.1f} hold={d['hold_h']:.1f}h exits={d['exits']}"
                     f" | CONTROL win={ctl['all']['win']:.1f}% R={ctl['all']['avgR']:+.3f} (n={ctl['all']['n']:.0f})"
                     f" | GROSS win={gr['all']['win']:.1f}% R={gr['all']['avgR']:+.3f}")
        print(lines[-1], flush=True)
    (bname, bgen, bd, bparams, bres, _c), how = select(rows)
    ctl = next(r for r in rows if r[0] == bname)[5]
    cw = {g: ctl[g]['win'] for g in ctl}; cr = {g: ctl[g]['avgR'] for g in ctl}; cn = ctl['all']['n']
    out[fam] = dict(configs=[(r[0], r[3], {k: v for k, v in r[2].items()}) for r in rows],
                    chosen=bname, how=how, passed=passes(bd), chosen_stats=bd,
                    control=dict(win=cw, avgR=cr, n=cn))
    out[fam]['_res'] = with_setups(bgen, bres)
    out[fam]['_params'] = bparams
    print(f"== {fam}: chosen [{how}] {bname} -> PASS={passes(bd)}; control win={cw} avgR={cr} n={cn:.0f}", flush=True)

print(f"weeks={WEEKS:.1f} elapsed={time.time()-T0:.0f}s")
pickle.dump({k: {kk: vv for kk, vv in v.items()} for k, v in out.items()}, open('agentA/all_results.pkl', 'wb'))
open('agentA/grid_report.txt', 'w').write("\n".join(lines) + "\n")
