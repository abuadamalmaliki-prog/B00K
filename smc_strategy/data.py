"""Load and clean the mixed M1/H1 XAUUSD CSV (Datetime,Timeframe,Open,High,Low,Close)."""
import numpy as np
import pandas as pd

GAP = {'M1': pd.Timedelta('5min'), 'H1': pd.Timedelta('2h')}


def _raw(path):
    r = pd.read_csv(path)
    r['Datetime'] = pd.to_datetime(r['Datetime'], errors='coerce')
    return r


def _clean(r, tf, drop_weekends=True, gap=None):
    """Clean one timeframe slice of the raw frame. Returns (df, counts)."""
    d = r[r['Timeframe'] == tf].rename(columns=str.lower)
    d = d.set_index('datetime')[['open', 'high', 'low', 'close']].astype('float64')
    d.index.name = 'time'
    rep = {'raw': len(d)}
    bad = d.index.isna() | d.isna().any(axis=1).values | (d <= 0).any(axis=1).values
    rep['dropped_nan_or_nonpos'] = int(bad.sum())
    d = d[~bad].round(5).sort_index()          # round away float32 noise
    dup = d.index.duplicated(keep='first')
    rep['dropped_dup_ts'] = int(dup.sum())
    d = d[~dup]
    swap = d['high'] < d['low']
    rep['fixed_high_lt_low'] = int(swap.sum())
    if swap.any():
        d.loc[swap, ['high', 'low']] = d.loc[swap, ['low', 'high']].values
    oc_hi = d[['open', 'close']].max(axis=1)
    oc_lo = d[['open', 'close']].min(axis=1)
    fix = (d['high'] < oc_hi) | (d['low'] > oc_lo)
    rep['fixed_ohlc_inconsistent'] = int(fix.sum())
    d['high'] = np.maximum(d['high'], oc_hi)
    d['low'] = np.minimum(d['low'], oc_lo)
    wk = d.index.dayofweek >= 5
    rep['weekend_bars'] = int(wk.sum())
    if drop_weekends:
        d = d[~wk]
        rep['dropped_weekend'] = int(wk.sum())
    gap = d.index.to_series().diff() > (pd.Timedelta(gap) if gap is not None else GAP[tf])
    d['block'] = gap.cumsum().astype('int64').values
    rep['kept'] = len(d)
    rep['blocks'] = int(d['block'].iloc[-1]) + 1 if len(d) else 0
    return d, rep


def load(path, tf='M1', drop_weekends=True, verbose=False, gap=None):
    """DataFrame indexed by time with open/high/low/close/block.

    'block' increments when the gap to the previous bar exceeds 5 min (M1) / 2 h (H1),
    or `gap` (e.g. '3h') when given.
    Cleaning counts are in df.attrs['clean_report'].
    """
    d, rep = _clean(_raw(path), tf, drop_weekends, gap)
    d.attrs['clean_report'] = rep
    if verbose:
        print(tf, rep)
    return d


def quality_report(path):
    """Print per-month bar counts/days/weekend bars for M1 and H1 plus the M1-vs-H1 mismatch."""
    r = _raw(path)
    out = {}
    for tf in ('M1', 'H1'):
        d, rep = _clean(r, tf, drop_weekends=False)
        print(tf, rep)
        m = d.index.to_period('M')
        g = pd.DataFrame({
            'bars': d.groupby(m).size(),
            'days': d.groupby(m).apply(lambda x: x.index.normalize().nunique()),
            'weekend_bars': d.groupby(m).apply(lambda x: int((x.index.dayofweek >= 5).sum())),
        })
        out[tf] = g
    print(pd.concat(out, axis=1).fillna(0).astype(int).to_string())

    m1 = load(path, 'M1', drop_weekends=False)
    h1 = load(path, 'H1', drop_weekends=False)
    gap = m1.index.to_series().diff()
    print('M1 gaps >5min: %d, >1h: %d, >1d: %d' % ((gap > GAP['M1']).sum(),
          (gap > pd.Timedelta('1h')).sum(), (gap > pd.Timedelta('1D')).sum()))
    jump = (m1['open'] / m1['close'].shift() - 1).abs()
    same = m1['block'].diff() == 0
    print('M1 intra-block open-vs-prev-close jumps >0.5%%: %d' % int(((jump > 0.005) & same).sum()))
    rs = m1.resample('1h').agg({'open': 'first', 'high': 'max', 'low': 'min',
                                'close': 'last', 'block': 'size'})
    rs = rs[rs['block'] >= 55]                  # nearly complete hours only
    j = rs.join(h1, rsuffix='_h1', how='inner')
    dc = (j['close'] - j['close_h1']).abs()
    print('M1->H1 vs H1 (%d matched hours, >=55 M1 bars): |close diff| median %.2f, mean %.2f, '
          'p90 %.2f; frac within $1: %.3f' % (len(j), dc.median(), dc.mean(), dc.quantile(.9),
                                              (dc <= 1).mean()))
    for sh in (-3, -2, -1, 1, 2, 3):
        jj = rs.shift(sh, freq='1h').join(h1, rsuffix='_h1', how='inner')
        print('  shift %+dh: median |close diff| %.2f' % (sh, (jj['close'] - jj['close_h1']).abs().median()))
    return out


if __name__ == '__main__':
    import sys
    quality_report(sys.argv[1])
