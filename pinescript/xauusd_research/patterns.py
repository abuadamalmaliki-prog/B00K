import pandas as pd, numpy as np
def features(b):
    o, h, l, c = b.o.values, b.h.values, b.l.values, b.c.values
    rng = h - l
    body = c - o
    lr = np.log(c / o)
    sd = pd.Series(lr).rolling(100, min_periods=50).std().values
    atr = pd.Series(rng).rolling(20, min_periods=10).mean().values
    up_w = h - np.maximum(o, c); dn_w = np.minimum(o, c) - l
    P = {}
    # direction +1 = pattern says up, -1 = down
    P['pin_bar']   = np.where((dn_w > 2 * np.abs(body)) & (dn_w > 0.6 * rng) & (rng > atr), 1, np.where((up_w > 2 * np.abs(body)) & (up_w > 0.6 * rng) & (rng > atr), -1, 0))
    po, pc = np.roll(o, 1), np.roll(c, 1)
    P['engulfing'] = np.where((c > o) & (pc < po) & (c >= po) & (o <= pc) & (rng > atr), 1, np.where((c < o) & (pc > po) & (c <= po) & (o >= pc) & (rng > atr), -1, 0))
    ph, pl = np.roll(h, 1), np.roll(l, 1); pph, ppl = np.roll(h, 2), np.roll(l, 2)
    inside_prev = (ph <= pph) & (pl >= ppl)
    P['inside_break'] = np.where(inside_prev & (c > ph), 1, np.where(inside_prev & (c < pl), -1, 0))
    s1, s2 = np.sign(lr), np.sign(np.roll(lr, 1)); s3 = np.sign(np.roll(lr, 2))
    P['three_run'] = np.where((s1 > 0) & (s2 > 0) & (s3 > 0), 1, np.where((s1 < 0) & (s2 < 0) & (s3 < 0), -1, 0))
    P['big_bar_3sd'] = np.where(lr > 3 * sd, 1, np.where(lr < -3 * sd, -1, 0))
    for k in P: P[k][:3] = 0
    return P, lr
def fwd(c, n):
    c = np.asarray(c); out = np.full(len(c), np.nan)
    out[:-n] = np.log(c[n:] / c[:-n]); return out
