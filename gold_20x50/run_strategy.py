"""Backtest the final strategy year by year and write the trade list.

python3 run_strategy.py data/XAUUSD_1min.csv
"""
import sys

import numpy as np
import pandas as pd

import engine
import strategy


def max_dd_usd(T):
    x = T[T.result != 'OPEN'].sort_values('exit_utc')
    eq = np.cumsum(x.pips.to_numpy()) * engine.PIP
    return float((np.maximum.accumulate(np.maximum(eq, 0)) - eq).max()) if len(eq) else 0.0


def main(path):
    b = engine.load(path)
    T = engine.backtest(b, strategy.SLOTS_MYT, strategy.direction, strategy.TP_PIPS,
                        strategy.SL_PIPS, strategy.SPREAD_PIPS)
    rows = []
    for name, x in list(T.groupby(T.tday.dt.year)) + [('all', T)]:
        s = engine.summarize(x)
        rows.append(dict(period=name, days_with_20=s['days_with_20'],
                         avg_tp_per_20=round(s['avg_tp_per_20'], 2),
                         days_ge18=f"{s['days_ge18']:.1%}", days_20of20=f"{s['days_20_of_20']:.1%}",
                         win=f"{s['win_rate']:.2%}", net_usd=round(s['total_pips'] * engine.PIP),
                         max_dd_usd=round(max_dd_usd(x)),
                         worst_day_usd=round(s['worst_day_pips'] * engine.PIP),
                         max_open=s['max_open_trades'], median_hold_min=round(s['median_hold_min'])))
    print('USD figures are per 0.01 lot (1 oz) per entry.')
    print(pd.DataFrame(rows).to_string(index=False))
    s = engine.summarize(T)
    print('TP hits per 20-entry day (all):', s['tp_distribution'])
    T['slot_myt'] = T.slot
    by_slot = T[T.result != 'OPEN'].groupby('slot').result.apply(lambda r: (r == 'TP').mean())
    print('TP rate by MYT slot:', by_slot.round(4).to_dict())
    T.to_csv('trades.csv', index=False)
    print('open trades at end of data:', int((T.result == 'OPEN').sum()), '| trades.csv written')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'data/XAUUSD_1min.csv')
