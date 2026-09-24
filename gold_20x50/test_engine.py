"""Hand-built cases for engine rules. Run: python3 test_engine.py"""
import numpy as np
import pandas as pd

import engine


def bars(rows, start='2025-03-04 00:00'):   # Tuesday 08:00 MYT
    idx = pd.date_range(start, periods=len(rows), freq='1min')
    return pd.DataFrame(np.array(rows, float), index=idx, columns=['open', 'high', 'low', 'close'])


def run(rows, direction=1, tp=50, sl=100, spread=0.0, **kw):
    b = bars(rows)
    T = engine.backtest(b, ['08:00'], lambda b, e: np.full(len(e), direction), tp, sl, spread, **kw)
    assert len(T) == 1
    return T.iloc[0]


F = (100, 100, 100, 100)


def test_entry_at_slot_open_and_tp():
    t = run([(100, 104, 99.5, 103), (103, 105.1, 102, 105)])
    assert t.result == 'TP' and np.isclose(t.pips, 50) and t.entry_utc == pd.Timestamp('2025-03-04 00:00')


def test_sl():
    t = run([F, (100, 101, 89.9, 90)])
    assert t.result == 'SL' and np.isclose(t.pips, -100)


def test_same_bar_is_sl():
    t = run([F, (100, 106, 89, 100)])
    assert t.result == 'SL'


def test_gap_through_sl_fills_at_open():
    t = run([F, (80, 81, 79, 80)])
    assert t.result == 'SL' and np.isclose(t.pips, -200)


def test_gap_through_tp_pays_exactly_tp():
    t = run([F, (120, 121, 119, 120)])
    assert t.result == 'TP' and np.isclose(t.pips, 50)


def test_spread_raises_long_tp_level():
    t = run([(100, 105.2, 99.9, 105), F], spread=3)   # 3 pips = $0.30: fill 100.3, TP needs 105.3
    assert t.result == 'OPEN'
    t = run([(100, 105.3, 99.9, 105), F], spread=3)
    assert t.result == 'TP'


def test_short_mirror():
    t = run([(100, 100.2, 94.9, 95), F], direction=-1)
    assert t.result == 'TP' and np.isclose(t.pips, 50)
    t = run([F, (100, 110.1, 99, 100)], direction=-1, sl=100)
    assert t.result == 'SL'


def test_max_hold_closes_as_not_tp():
    t = run([F] * 5, max_hold_days=2 / 1440)
    assert t.result == 'CLOSED'


def test_slots_map_to_myt_trading_day():
    idx = pd.date_range('2025-03-04 00:00', '2025-03-05 23:59', freq='1min')
    b = pd.DataFrame(100.0, index=idx, columns=['open', 'high', 'low', 'close'])
    e = engine.slot_entries(b, ['08:00', '03:00'])
    first = e[e.tday == pd.Timestamp('2025-03-04')]
    # 08:00 MYT = 00:00 UTC same day, 03:00 MYT belongs to the same trading day = 19:00 UTC
    assert sorted(b.index[first.i].strftime('%H:%M')) == ['00:00', '19:00']


if __name__ == '__main__':
    import sys
    bad = 0
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            try:
                f(); print('PASS', k)
            except Exception as ex:
                bad += 1; print('FAIL', k, repr(ex))
    sys.exit(bad)
