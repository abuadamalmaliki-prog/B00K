"""Reproduce the README results: python3 run_backtest.py path/to/XAUUSD_M1_H1.csv"""
import sys

import numpy as np
import pandas as pd

import backtest
import data
import strategy

PERIODS = {
    'train 2025 (rules chosen here)': (None, '2026-01-01'),
    'validation 2026 Jan-Apr': ('2026-01-01', '2026-05-01'),
    'TEST 2026 May-Aug (run once)': ('2026-05-01', None),
    'all': (None, None),
}


def report(m, sig, name, lo, hi):
    part = np.ones(len(m), bool)
    if lo:
        part &= m.index >= lo
    if hi:
        part &= m.index < hi
    s = sig.copy()
    s[~part] = 0
    T, S = backtest.simulate(m, s, **strategy.FINAL_SIM)
    d = T.entry_time.dt.normalize()
    per = T.groupby(d).size()
    tp = (T.result == 'TP').groupby(d).sum()
    full = tp.loc[per[per >= 20].index]
    print(f"\n== {name}")
    print(f"   trades {len(T)} | days traded {len(per)} | 20-trade days {len(full)} | "
          f"win rate {S['win_rate']:.1%} | avg TP per 20 {full.mean():.2f} | "
          f"days >=18/20 {(full >= 18).mean():.1%}")
    print(f"   expectancy {S['expectancy_pips']:+.1f} pips/trade | PF {S['profit_factor']:.2f} | "
          f"total {S['total_pips']:+.0f} pips | max DD {S['max_drawdown_pips']:.0f} pips | "
          f"worst day {T.groupby(d).pips.sum().min():+.0f} pips")
    print(f"   TP hits per 20-trade day: {full.value_counts().sort_index().to_dict()}")
    print(f"   exits: {T.result.value_counts().to_dict()}")
    return T


def main(path):
    m = data.load(path, gap=strategy.FINAL_GAP)
    feats = strategy.build_features(m, tfs=('D1',))
    sig = strategy.signals(m, feats, **strategy.FINAL)
    for name, (lo, hi) in PERIODS.items():
        T = report(m, sig, name, lo, hi)
    T.to_csv('trades_all.csv', index=False)
    print('\ntrades written to trades_all.csv')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD_M1_H1_2025-2026Aug.csv')
