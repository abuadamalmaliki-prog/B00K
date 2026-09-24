"""Reverse-engineering SMC: does any SMC concept predict a +50-pip move before a -SL move?

GOLD_DATA=data python3 smc_edge_study.py
Base timeframe M15 (2020-2026), features from M15/H1/H4/D1 SMC (structure, BOS/CHoCH,
FVG, order blocks, liquidity sweeps, premium/discount, sessions) plus price context.
Train 2020-2023, test 2024-2026.
"""
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from features import build, label

b, F = build('15min')
o, h, l = (b[c].to_numpy() for c in ('open', 'high', 'low'))
t = b.index.values.astype('datetime64[ns]').astype(np.int64)
yr = b.index.year.to_numpy()
tr, te = yr <= 2023, yr >= 2024
c = b.close.to_numpy()
for sl in (450, 1200):
    rl, rs, *_ = label(o, h, l, t, 5.0, sl / 10, 0.3, np.int64(2 ** 62))
    print(f'\n=== TP 50 / SL {sl} pips: TP rate  train | test')
    concepts = {
        'all longs': (np.ones(len(b), bool), None),
        'all shorts': (None, np.ones(len(b), bool)),
        'H4 structure (BOS/CHoCH trend)': (F.h4_trend == 1, F.h4_trend == -1),
        'H1 liquidity sweep (last 6 bars)': (F.h1_sweep_recent > 0, F.h1_sweep_recent < 0),
        'M15 liquidity sweep': (F.b_sweep > 0, F.b_sweep < 0),
        'M15 CHoCH': (F.b_choch > 0, F.b_choch < 0),
        'price in H1 FVG': (F.h1_in_bfvg == 1, F.h1_in_sfvg == 1),
        'price in H1 order block': (F.h1_in_bob == 1, F.h1_in_sob == 1),
        'H4 discount/premium': (F.h4_pd_pos < 0.3, F.h4_pd_pos > 0.7),
        'D1 structure': (F.d1_trend == 1, F.d1_trend == -1),
    }
    for name, (lm, sm) in concepts.items():
        out = []
        for part in (tr, te):
            w = []
            if lm is not None:
                w.append(rl[np.asarray(lm) & part] == 1)
            if sm is not None:
                w.append(rs[np.asarray(sm) & part] == 1)
            w = np.concatenate(w)
            out.append(f'{w.mean():.3f} (n={len(w)})')
        print(f'  {name:34s} {out[0]} | {out[1]}')
    for side, y in (('long', rl == 1), ('short', rs == 1)):
        m = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.03, min_child_samples=500,
                               subsample=0.7, subsample_freq=1, colsample_bytree=0.7, verbose=-1)
        m.fit(F[tr], y[tr])
        p = m.predict_proba(F[te])[:, 1]
        top = y[te][p >= np.quantile(p, 0.9)].mean()
        print(f'  GBM on all features, {side}: test AUC {roc_auc_score(y[te], p):.3f}, '
              f'base {y[te].mean():.3f}, top-10% {top:.3f}')
