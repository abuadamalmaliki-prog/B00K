"""Robustness for the scan's picks: unseen 2016-2020 data, spread cost, nearby parameters."""
import numpy as np
import pandas as pd

import scan


def evaluate(inst, rule, tp, sl, cost=None, window_h=24, since='2016'):
    pip, c0 = scan.SPEC[inst]
    cost = c0 if cost is None else cost
    d = scan.load(inst, since)
    o, h, l, c = (d[k].to_numpy() for k in ('open', 'high', 'low', 'close'))
    i, tday = scan.slot_entries(d)
    LT, LS, ST, SS, ML, MS = scan.first_hits(o, h, l, c, i, np.array([tp * pip]), np.array([sl * pip]),
                                             cost * pip, 30 * 288)
    keep = d.index[i] < d.index[-1] - pd.Timedelta(days=33)
    i, tday, LT, LS, ST, SS, ML, MS = (x[keep] for x in (i, tday, LT, LS, ST, SS, ML, MS))
    if rule == 'buy':
        dr = np.ones(len(i))
    elif rule == 'sell':
        dr = -np.ones(len(i))
    else:
        mean = d.close.rolling(window_h * 12).mean().to_numpy()
        dr = -np.sign(c[i - 1] - mean[i - 1])
        dr[dr == 0] = 1
    buy = dr > 0
    tpt = np.where(buy, LT[:, 0], ST[:, 0]); slt = np.where(buy, LS[:, 0], SS[:, 0])
    win = tpt < slt
    lose = (slt <= tpt) & (slt < (1 << 40))
    pnl = np.where(win, tp, np.where(lose, -sl, np.where(buy, ML, MS) / pip))
    df = pd.DataFrame({'tday': tday, 'win': win, 'pnl': pnl})
    df['per'] = pd.cut(df.tday.dt.year, [2015, 2020, 2023, 2026], labels=['C 2016-20 (unseen)', 'A 2021-23', 'B 2024-26'])
    rows = []
    for pn, g in df.groupby('per', observed=True):
        dd = g.groupby('tday'); n = dd.size(); w = dd.win.sum(); full = n[n == 20].index
        rows.append(dict(period=pn, days=len(full), win=round(g.win.mean(), 4), tp20=round(w.loc[full].mean(), 2),
                         ge18=round((w.loc[full] >= 18).mean(), 3), exp_pips=round(g.pnl.mean(), 2)))
    return pd.DataFrame(rows)


if __name__ == '__main__':
    pd.set_option('display.width', 200)
    picks = [('eurgbp', 'fade', 10, 200), ('usa500idxusd', 'buy', 20, 300), ('usdjpy', 'buy', 50, 900),
             ('eurjpy', 'buy', 30, 900), ('audnzd', 'fade', 10, 300), ('usatechidxusd', 'buy', 50, 1200)]
    for inst, rule, tp, sl in picks:
        print(f'\n## {inst} {rule} TP {tp} SL {sl} (cost {scan.SPEC[inst][1]} pips)')
        print(evaluate(inst, rule, tp, sl).to_string(index=False))
    print('\n## EURGBP fade: cost sensitivity (TP 10 / SL 200)')
    for cost in (0.8, 1.0, 1.5, 2.0, 2.5):
        r = evaluate('eurgbp', 'fade', 10, 200, cost=cost)
        print(f'cost {cost}:', r[['period', 'win', 'tp20', 'ge18', 'exp_pips']].to_dict('records'))
    print('\n## EURGBP fade: neighbours (cost 1.5)')
    for w in (12, 24, 48):
        for tp, sl in ((10, 150), (10, 200), (10, 300), (15, 300), (20, 300), (20, 450)):
            r = evaluate('eurgbp', 'fade', tp, sl, window_h=w)
            print(f'window {w}h TP {tp} SL {sl}:', ' | '.join(f"{x.period[:1]} ge18 {x.ge18:.3f} tp20 {x.tp20:.2f} exp {x.exp_pips:+.2f}" for x in r.itertuples()))
