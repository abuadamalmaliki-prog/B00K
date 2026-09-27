import pandas as pd, numpy as np
COST_BP = 1.0
def day_groups(b):
    b = b.copy()
    b['tday'] = (b.index + pd.Timedelta(hours=6)).normalize()
    b['mod'] = b.index.hour * 60 + b.index.minute
    return b
def rel_mod(m):  # minutes since 18:00 NY (trading-day clock)
    return (m - 18 * 60) % 1440
def run_bracket(d, side, entry_px, sl, tp, start_i, exit_mod_rel):
    """d: arrays of one trading day. Enter at entry_px at bar start_i (already filled). Walk bars from start_i+1
    (entry bar itself for stop entries is handled by caller). SL first if both touched. Time exit at close of last bar before exit."""
    for i in range(start_i, len(d['o'])):
        if d['rm'][i] >= exit_mod_rel:
            return d['o'][i], 'time'
        o, h, l = d['o'][i], d['h'][i], d['l'][i]
        if side > 0:
            if l <= sl: return min(o, sl), 'sl'
            if tp is not None and h >= tp: return max(o, tp), 'tp'
        else:
            if h >= sl: return max(o, sl), 'sl'
            if tp is not None and l <= tp: return min(o, tp), 'tp'
    return d['c'][-1], 'eod'
def summarize(name, tr, cost_bp=COST_BP):
    if len(tr) == 0: print(f"{name}: no trades"); return
    t = pd.DataFrame(tr, columns=['day', 'side', 'entry', 'exit', 'risk', 'why'])
    t['gross_bp'] = t.side * np.log(t.exit / t.entry) * 1e4
    t['net_bp'] = t.gross_bp - cost_bp
    t['yr'] = pd.to_datetime(t.day).dt.year
    out = [name]
    for a, z in ((2009, 2017), (2018, 2026)):
        x = t[(t.yr >= a) & (t.yr <= z)]
        n_yrs = z - a + 1 if z < 2026 else 8.02
        sh = x.net_bp.mean() / x.net_bp.std() * np.sqrt(len(x) / n_yrs) if len(x) > 2 else np.nan
        out.append(f"{a%100:02d}-{z%100:02d}: n={len(x)} win={100*(x.net_bp>0).mean():.0f}% avg={x.net_bp.mean():+.2f}bp t={x.net_bp.mean()/x.net_bp.std()*np.sqrt(len(x)):+.2f} bp/yr={x.net_bp.sum()/n_yrs:+.0f} SR={sh:+.2f}")
    print(" | ".join(out))
    return t
