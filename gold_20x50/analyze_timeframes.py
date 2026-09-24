"""Run the same strategy on every downloaded timeframe and compare.

python3 analyze_timeframes.py data/   (expects data/XAUUSD_<tf>.csv from download_twelvedata.py)
"""
import os
import sys

import pandas as pd

import engine
import strategy

TFS = ['1min', '5min', '15min', '1h', '4h']


def main(folder, start='2024-01-01'):
    rows = []
    for tf in TFS:
        p = os.path.join(folder, f'XAUUSD_{tf}.csv')
        if not os.path.exists(p):
            continue
        b = engine.load(p)
        b = b[b.index >= start]
        T = engine.backtest(b, strategy.SLOTS_MYT, strategy.direction, strategy.TP_PIPS,
                            strategy.SL_PIPS, strategy.SPREAD_PIPS)
        T = T[T.tday < b.index[-1].normalize() - pd.Timedelta(days=1)]
        s = engine.summarize(T)
        rows.append(dict(tf=tf, bars=len(b), days=s['trading_days'], days_with_20=s['days_with_20'],
                         avg_tp_per_20=round(s['avg_tp_per_20'], 2),
                         days_ge18=round(s['days_ge18'], 3), win=round(s['win_rate'], 4),
                         total_usd_per_001lot=round(s['total_pips'] * engine.PIP),
                         worst_day_usd=round(s['worst_day_pips'] * engine.PIP)))
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'data')
