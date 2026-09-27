import pandas as pd, numpy as np
from sim import day_groups, rel_mod, run_bracket
H = lambda h, m=0: rel_mod(h * 60 + m)
def load_days(tf='m5'):
    b = day_groups(pd.read_parquet(f'{tf}.parquet'))
    b = b[b.index.dayofweek.isin([0, 1, 2, 3, 4, 6])]
    return {k: {'o': g.o.values, 'h': g.h.values, 'l': g.l.values, 'c': g.c.values, 'rm': rel_mod(g['mod'].values)}
            for k, g in b.groupby('tday') if len(g) > 50}
def asia_breakout(days, r0=H(18, 30), r1=H(3), e_end=H(8, 20), x_end=H(11), tp_R=None, sl_mode='opposite', min_bars=0.8, bar_min=5):
    tr = []
    for k in sorted(days):
        d = days[k]; rm = d['rm']
        rng = (rm >= r0) & (rm < r1)
        if rng.sum() < (r1 - r0) / bar_min * min_bars: continue
        hi, lo = d['h'][rng].max(), d['l'][rng].min()
        if hi <= lo: continue
        for i in np.where((rm >= r1) & (rm < e_end))[0]:
            up, dn = d['h'][i] > hi, d['l'][i] < lo
            if up and dn: break
            if not (up or dn): continue
            side = 1 if up else -1
            entry = max(d['o'][i], hi) if side > 0 else min(d['o'][i], lo)
            sl = (lo if side > 0 else hi) if sl_mode == 'opposite' else (hi + lo) / 2
            R = abs(entry - sl)
            tp = entry + side * tp_R * R if tp_R else None
            if (side > 0 and d['l'][i] <= sl) or (side < 0 and d['h'][i] >= sl):
                tr.append((k, side, entry, sl, R, 'sl')); break
            if tp is not None and ((side > 0 and d['c'][i] >= tp) or (side < 0 and d['c'][i] <= tp)):
                tr.append((k, side, entry, tp, R, 'tp')); break
            px, why = run_bracket(d, side, entry, sl, tp, i + 1, x_end)
            tr.append((k, side, entry, px, R, why)); break
    t = pd.DataFrame(tr, columns=['day', 'side', 'entry', 'exit', 'risk', 'why'])
    t['gross_bp'] = t.side * np.log(t.exit / t.entry) * 1e4
    t['yr'] = pd.to_datetime(t.day).dt.year
    t['R'] = t.side * (t.exit - t.entry) / t.risk
    return t
def stats(x, cost=1.0, yrs=None):
    n = x.gross_bp - cost
    if len(n) < 3: return "n<3"
    yrs = yrs or max(1e-9, (pd.to_datetime(x.day).max() - pd.to_datetime(x.day).min()).days / 365.25)
    return f"n={len(n):<4} avg={n.mean():+.2f}bp t={n.mean()/n.std()*np.sqrt(len(n)):+.2f} SR={n.mean()/n.std()*np.sqrt(len(n)/yrs):+.2f}"
