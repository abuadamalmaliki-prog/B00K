"""Hand-built OHLC cases for backtest.simulate. Run: python3 -m pytest test_backtest.py (or python3 test_backtest.py)."""
import numpy as np
import pandas as pd

from backtest import simulate, simulate_random

PIP = 0.10


def mk(bars, start='2025-03-04 10:00', block=None, times=None):
    """bars: list of (o,h,l,c). Weekday, 1-min spacing unless times given."""
    a = np.array(bars, dtype=float)
    idx = pd.DatetimeIndex(times) if times is not None else pd.date_range(start, periods=len(a), freq='1min')
    df = pd.DataFrame(a, index=idx, columns=['open', 'high', 'low', 'close'])
    df['block'] = np.zeros(len(a), int) if block is None else block
    return df


FLAT = (100, 100, 100, 100)


def run(df, sig, **kw):
    kw.setdefault('spread_pips', 0)
    kw.setdefault('tp_pips', 50)
    kw.setdefault('sl_pips', 50)
    return simulate(df, np.array(sig), **kw)


def one(df, sig, **kw):
    tr, _ = run(df, sig, **kw)
    assert len(tr) == 1, tr
    return tr.iloc[0]


def test_long_tp():
    df = mk([FLAT, (100, 101, 99.5, 100), (100, 105.2, 99, 104), FLAT])
    t = one(df, [1, 0, 0, 0])
    assert t.result == 'TP' and t.entry == 100 and np.isclose(t.exit, 105) and np.isclose(t.pips, 50)
    assert t.bars_held == 2 and t.entry_time == df.index[1] and t.exit_time == df.index[2]


def test_long_sl():
    t = one(mk([FLAT, (100, 101, 99.5, 100), (100, 101, 94.9, 96), FLAT]), [1, 0, 0, 0])
    assert t.result == 'SL' and np.isclose(t.pips, -50)


def test_short_tp_sl():
    t = one(mk([FLAT, FLAT, (100, 100.5, 94.9, 95)]), [-1, 0, 0])
    assert t.result == 'TP' and np.isclose(t.pips, 50) and t.dir == -1
    t = one(mk([FLAT, FLAT, (100, 105.1, 99, 104)]), [-1, 0, 0])
    assert t.result == 'SL' and np.isclose(t.pips, -50)


def test_both_same_bar_is_sl():
    t = one(mk([FLAT, FLAT, (100, 106, 94, 100)]), [1, 0, 0])
    assert t.result == 'SL' and np.isclose(t.pips, -50)
    t = one(mk([FLAT, FLAT, (100, 106, 94, 100)]), [-1, 0, 0])
    assert t.result == 'SL' and np.isclose(t.pips, -50)


def test_entry_bar_checked():
    t = one(mk([FLAT, (100, 105.5, 99.8, 105), FLAT]), [1, 0, 0])
    assert t.result == 'TP' and t.bars_held == 1
    t = one(mk([FLAT, (100, 105.5, 94.5, 100), FLAT]), [1, 0, 0])
    assert t.result == 'SL' and t.bars_held == 1


def test_gap_through_fills_at_open():
    t = one(mk([FLAT, FLAT, (93, 94, 92, 93)]), [1, 0, 0])
    assert t.result == 'SL' and np.isclose(t.exit, 93) and np.isclose(t.pips, -70)
    t = one(mk([FLAT, FLAT, (107, 108, 106, 107)]), [1, 0, 0])
    assert t.result == 'TP' and np.isclose(t.exit, 107) and np.isclose(t.pips, 70)
    t = one(mk([FLAT, FLAT, (107, 108, 106, 107)]), [-1, 0, 0])
    assert t.result == 'SL' and np.isclose(t.pips, -70)


def test_trade_survives_data_gap():
    times = ['2025-03-04 10:00', '2025-03-04 10:01', '2025-03-04 10:02', '2025-03-05 14:00', '2025-03-05 14:01']
    df = mk([FLAT, FLAT, FLAT, (93, 94, 92, 93), FLAT], block=[0, 0, 0, 1, 1], times=times)
    t = one(df, [1, 0, 0, 0, 0])
    assert t.result == 'SL' and np.isclose(t.exit, 93) and t.exit_time == df.index[3]


def test_no_entry_across_gap_or_on_last_bar():
    times = ['2025-03-04 10:00', '2025-03-04 10:01', '2025-03-05 14:00', '2025-03-05 14:01']
    df = mk([FLAT] * 4, block=[0, 0, 1, 1], times=times)
    tr, _ = run(df, [0, 1, 0, 1])
    assert len(tr) == 0
    tr, _ = run(df, [0, 1, 0, 1], allow_gap_entry=True)
    assert len(tr) == 1 and tr.entry_time.iloc[0] == df.index[2]


def test_spread_cost():
    # round trip on a flat market costs exactly the spread, long and short
    for d in (1, -1):
        t = one(mk([FLAT] * 3), [d, 0, 0], spread_pips=3, time_stop_bars=1)
        assert t.result == 'TIME' and np.isclose(t.pips, -3), t
    # long: entry at ask 100.3, TP needs bid 105.3
    df = mk([FLAT, FLAT, (100, 105.2, 99.9, 105)])
    t = one(df, [1, 0, 0], spread_pips=3)
    assert t.result == 'EOD' and np.isclose(t.entry, 100.3)
    t = one(mk([FLAT, FLAT, (100, 105.3, 99.9, 105)]), [1, 0, 0], spread_pips=3)
    assert t.result == 'TP' and np.isclose(t.pips, 50)
    # short: entry at bid 100, TP needs ask 95 -> bid 94.7; SL needs ask 105 -> bid 104.7
    t = one(mk([FLAT, FLAT, (100, 100, 94.8, 95)]), [-1, 0, 0], spread_pips=3)
    assert t.result == 'EOD'
    t = one(mk([FLAT, FLAT, (100, 100, 94.7, 95)]), [-1, 0, 0], spread_pips=3)
    assert t.result == 'TP' and np.isclose(t.pips, 50)
    t = one(mk([FLAT, FLAT, (100, 104.7, 99.9, 100)]), [-1, 0, 0], spread_pips=3)
    assert t.result == 'SL' and np.isclose(t.pips, -50)


def test_time_stop():
    df = mk([FLAT, FLAT, FLAT, (100, 101, 99, 101), FLAT, FLAT])
    t = one(df, [1, 0, 0, 0, 0, 0], time_stop_bars=3)
    assert t.result == 'TIME' and t.bars_held == 3 and t.exit_time == df.index[3] and np.isclose(t.pips, 10)


def test_daily_cap():
    times = list(pd.date_range('2025-03-04 10:00', periods=10, freq='1min')) + \
        list(pd.date_range('2025-03-05 10:00', periods=10, freq='1min'))
    df = mk([FLAT] * 20, times=times)          # same block: exit next bar via time stop
    tr, s = run(df, [1] * 20, max_trades_per_day=3, time_stop_bars=1)
    assert len(tr) == 6
    assert tr.groupby(tr.entry_time.dt.date).size().tolist() == [3, 3]


def test_max_open():
    df = mk([FLAT] * 10)
    tr, _ = run(df, [1] * 10)
    assert len(tr) == 1 and tr.result.iloc[0] == 'EOD'
    tr, _ = run(df, [1] * 10, max_open=3)
    assert len(tr) == 3 and list(tr.entry_time) == list(df.index[1:4])
    # signal blocked while a trade is open is dropped, not queued
    df = mk([FLAT, FLAT, (100, 106, 99.9, 105), FLAT, FLAT, FLAT])
    tr, _ = run(df, [1, 1, 0, 0, 0, 0])
    assert len(tr) == 1
    # slot freed after exit on bar 2 -> signal at close of bar 2 enters on bar 3
    tr, _ = run(df, [1, 0, 1, 0, 0, 0])
    assert len(tr) == 2 and tr.entry_time.iloc[1] == df.index[3]


def test_per_bar_tp_sl_arrays():
    df = mk([FLAT, FLAT, (100, 102.1, 99.5, 102)])
    t = one(df, [1, 0, 0], tp_pips_arr=np.array([20, 50, 50.]), sl_pips_arr=np.array([10, 50, 50.]))
    assert t.result == 'TP' and np.isclose(t.pips, 20)


def test_summary_and_random_null():
    rng = np.random.default_rng(1)
    n = 60 * 24 * 5
    idx = pd.date_range('2025-03-03', periods=n, freq='1min')   # Mon-Fri
    c = 2000 + np.cumsum(rng.normal(0, 0.3, n))
    o = np.r_[c[0], c[:-1]]
    df = pd.DataFrame({'open': o, 'high': np.maximum(o, c) + 0.1, 'low': np.minimum(o, c) - 0.1,
                       'close': c, 'block': 0}, index=idx)
    tr, s = simulate_random(df, n_per_day=20, tp_pips=50, sl_pips=50, spread_pips=0, seed=3)
    assert s['n_trades'] == 100 and s['pct_days_with_20_trades'] == 1.0
    assert 0.3 < s['win_rate'] < 0.7
    assert sum(s['tp_hits_on_20_trade_days'].values()) == 5
    assert np.isclose(s['total_pips'], tr.pips.sum())


def test_strict_tp_no_gap_bonus():
    # bar 2 gaps open far above TP: default fills at the open, strict_tp fills at exactly +50 pips
    df = mk([FLAT, FLAT, (110, 111, 109, 110), FLAT])
    assert np.isclose(one(df, [1, 0, 0, 0]).pips, 100)
    t = one(df, [1, 0, 0, 0], strict_tp=True)
    assert t.result == 'TP' and np.isclose(t.pips, 50)


def test_close_at_gap():
    # open trade on the last bar of block 0 is closed there at the close, not carried through the hole
    df = mk([FLAT, (100, 100.5, 99.5, 100.2), (90, 91, 89, 90), FLAT], block=[0, 0, 1, 1])
    assert one(df, [1, 0, 0, 0]).result == 'SL'
    t = one(df, [1, 0, 0, 0], close_at_gap=True)
    assert t.result == 'GAP' and t.exit_time == df.index[1] and np.isclose(t.pips, 2)


if __name__ == '__main__':
    import sys
    fails = 0
    for name, f in list(globals().items()):
        if name.startswith('test_'):
            try:
                f(); print('PASS', name)
            except Exception as e:
                fails += 1; print('FAIL', name, repr(e))
    sys.exit(1 if fails else 0)
