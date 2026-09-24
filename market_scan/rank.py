"""Rank markets from scan_results.csv. Selection uses period A (2021-23) only; B (2024-26) is the check.

For each market: among rules and TPs, the smallest SL/TP ratio whose period-A days-with-18+-TP
is >= 90% and whose period-A expectancy is > 0. Then report that exact setting in period B.
"""
import pandas as pd

# USD value of 1 pip at 0.01 lot (approx., Sep 2026 rates). Indices depend on the broker's contract size.
PIP_USD = {'EURUSD': .10, 'GBPUSD': .10, 'AUDUSD': .10, 'NZDUSD': .10, 'XAUUSD': .10,
           'USDJPY': .067, 'EURJPY': .067, 'GBPJPY': .067, 'AUDJPY': .067, 'USDCHF': .12,
           'GBPCHF': .12, 'EURCHF': .12, 'USDCAD': .072, 'EURCAD': .072, 'AUDCAD': .072,
           'EURGBP': .13, 'AUDNZD': .058, 'EURAUD': .064}

r = pd.read_csv('scan_results.csv')
r['ratio'] = r.sl / r.tp
A = r[r.period.str.startswith('A')].set_index(['inst', 'rule', 'tp', 'sl'])
B = r[r.period.str.startswith('B')].set_index(['inst', 'rule', 'tp', 'sl'])
ok = A[(A.ge18 >= 0.90) & (A.exp_pips > 0) & (A.days >= 300)].reset_index()
pick = ok.sort_values(['ratio', 'exp_pips'], ascending=[True, False]).groupby('inst').head(1)
rows = []
for _, p in pick.iterrows():
    k = (p.inst, p.rule, p.tp, p.sl)
    b = B.loc[k] if k in B.index else None
    rows.append(dict(market=p.inst, rule=p.rule, tp=int(p.tp), sl=int(p.sl), ratio=p.ratio,
                     A_ge18=p.ge18, A_tp20=p.tp20, A_exp=p.exp_pips,
                     B_days=None if b is None else int(b.days), B_ge18=None if b is None else b.ge18,
                     B_tp20=None if b is None else b.tp20, B_exp=None if b is None else b.exp_pips,
                     usd_per_win_001=round(p.tp * PIP_USD.get(p.inst, float('nan')), 2)))
out = pd.DataFrame(rows).sort_values(['ratio', 'B_ge18'], ascending=[True, False])
pd.set_option('display.width', 250)
print(out.round(3).to_string(index=False))
missing = sorted(set(r.inst) - set(pick.inst))
print('markets with no setting reaching 90% of days in 2021-23 with positive expectancy:', missing)
