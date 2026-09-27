import pandas as pd, numpy as np
def load(tf='m5'):
    b = pd.read_parquet(f'{tf}.parquet')
    b['tday'] = (b.index + pd.Timedelta(hours=6)).normalize()   # trading day starts 18:00 NY
    b['mod'] = b.index.hour * 60 + b.index.minute
    return b
def seg_return(b, start, end):
    """log return from open of first bar >= start to close of last bar < end (NY minutes; start may be > end = crosses midnight)."""
    if start < end: m = (b['mod'] >= start) & (b['mod'] < end)
    else: m = (b['mod'] >= start) | (b['mod'] < end)
    x = b[m]
    g = x.groupby('tday').agg(o=('o', 'first'), c=('c', 'last'), n=('o', 'size'))
    g = g[g.n >= 0.8 * ((end - start) % 1440) / 5]
    return np.log(g.c / g.o)
