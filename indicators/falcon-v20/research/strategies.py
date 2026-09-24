"""Setup generators. Each returns [(i, dir, sl_price, risk_pips)] sorted by i (chart prices = bid)."""
import random
from common import PIPS, bars, run, resample
from engine import DEFAULTS
from sim import ny

# Assumed JustMarkets-Standard-like typical spreads in pips (verify in MT5 Market Watch).
SPREAD = {"EURUSD": 1.2, "GBPUSD": 1.5, "AUDUSD": 1.5, "NZDUSD": 2.0, "USDCAD": 2.0, "GBPAUD": 3.5,
          "USDJPY": 1.5, "EURJPY": 2.0, "GBPJPY": 3.0, "XAUUSD": 3.0, "XAGUSD": 3.0}
MIN_SL, MAX_SL, BUF = 10.0, 100.0, 3.0

def ema(xs, n):
    out, a, v = [], 2 / (n + 1), None
    for k, x in enumerate(xs):
        v = x if v is None else a * x + (1 - a) * v
        out.append(v if k >= n - 1 else None)
    return out

def _fit(i, d, c, sl, pip):
    rp = (c - sl) / pip if d == 1 else (sl - c) / pip
    if rp < MIN_SL:
        sl = c - d * MIN_SL * pip; rp = MIN_SL
    return (i, d, sl, rp) if rp <= MAX_SL else None

V3 = dict(partials=False, beAfterTp1=True, trailTp2=False, tp1Pips=150, tp2Pips=200, noReverse=True, bothSkip=True)

def sweep(sym, tf):
    setups, _, _ = run(sym, tf, raw=True, **V3)[1], None, None
    return setups

def london_breakout(sym, tf):
    if tf != 3600: return []
    rows, pip = bars(sym, 3600), PIPS[sym]
    out, day, hi, lo, taken = [], None, None, None, False
    for i, (t, o, h, l, c, v) in enumerate(rows):
        n = ny(t)
        key = (n.date() if n.hour >= 19 else None)
        if n.hour == 19:                                   # Asian session starts 19:00 NY
            day, hi, lo, taken = n.date(), h, l, False
        elif hi is not None and (n.hour >= 20 or n.hour < 2):
            hi, lo = max(hi, h), min(lo, l)
        elif hi is not None and 2 <= n.hour < 6 and not taken:
            if c > hi:
                s = _fit(i, 1, c, lo - BUF * pip, pip); taken = True
                if s: out.append(s)
            elif c < lo:
                s = _fit(i, -1, c, hi + BUF * pip, pip); taken = True
                if s: out.append(s)
    return out

def donchian(sym, tf, n_break=55, n_stop=10):
    rows, pip = bars(sym, tf), PIPS[sym]
    H = [r[2] for r in rows]; L = [r[3] for r in rows]; C = [r[4] for r in rows]
    out = []
    for i in range(n_break, len(rows)):
        if C[i] > max(H[i - n_break:i]) and C[i - 1] <= max(H[i - 1 - n_break:i - 1]):
            s = _fit(i, 1, C[i], min(L[i - n_stop + 1:i + 1]) - BUF * pip, pip)
            if s: out.append(s)
        elif C[i] < min(L[i - n_break:i]) and C[i - 1] >= min(L[i - 1 - n_break:i - 1]):
            s = _fit(i, -1, C[i], max(H[i - n_stop + 1:i + 1]) + BUF * pip, pip)
            if s: out.append(s)
    return out

def trend_pullback(sym, tf):
    if tf != 14400: return []
    rows, pip = bars(sym, 14400), PIPS[sym]
    daily = resample(bars(sym, 3600), 86400)
    dc = [r[4] for r in daily]; e50, e200 = ema(dc, 50), ema(dc, 200)
    bias = {}
    prev = 0
    for k, r in enumerate(daily):
        bias[r[0]] = prev                                   # bias visible during day = previous closed day
        if e200[k] is not None:
            prev = 1 if dc[k] > e50[k] > e200[k] else -1 if dc[k] < e50[k] < e200[k] else 0
    H = [r[2] for r in rows]; L = [r[3] for r in rows]; C = [r[4] for r in rows]; O = [r[1] for r in rows]
    e20 = ema(C, 20); out = []
    for i in range(25, len(rows)):
        b = bias.get(rows[i][0] - rows[i][0] % 86400, 0)
        if e20[i] is None or b == 0: continue
        if b == 1 and min(L[i - 2:i + 1]) <= e20[i] and C[i] > e20[i] and C[i] > H[i - 1] and C[i] > O[i]:
            s = _fit(i, 1, C[i], min(L[i - 4:i + 1]) - BUF * pip, pip)
            if s: out.append(s)
        elif b == -1 and max(H[i - 2:i + 1]) >= e20[i] and C[i] < e20[i] and C[i] < L[i - 1] and C[i] < O[i]:
            s = _fit(i, -1, C[i], max(H[i - 4:i + 1]) + BUF * pip, pip)
            if s: out.append(s)
    return out

def nr7(sym, tf):
    rows, pip = bars(sym, tf), PIPS[sym]
    H = [r[2] for r in rows]; L = [r[3] for r in rows]; C = [r[4] for r in rows]
    out = []
    for i in range(8, len(rows)):
        j = i - 1
        if H[j] - L[j] > 0 and H[j] - L[j] <= min(H[k] - L[k] for k in range(j - 6, j + 1)):
            if C[i] > H[j]:
                s = _fit(i, 1, C[i], L[j] - BUF * pip, pip)
                if s: out.append(s)
            elif C[i] < L[j]:
                s = _fit(i, -1, C[i], H[j] + BUF * pip, pip)
                if s: out.append(s)
    return out

def random_entries(sym, tf, every=12, seed=7):
    rows, pip = bars(sym, tf), PIPS[sym]
    rng = random.Random(hash((sym, tf, seed)) & 0xffffffff)
    H = [r[2] for r in rows]; L = [r[3] for r in rows]; C = [r[4] for r in rows]
    out = []
    for i in range(10, len(rows)):
        if rng.random() < 1 / every:
            d = 1 if rng.random() < 0.5 else -1
            sl = min(L[i - 4:i + 1]) - BUF * pip if d == 1 else max(H[i - 4:i + 1]) + BUF * pip
            s = _fit(i, d, C[i], sl, pip)
            if s: out.append(s)
    return out

STRATS = {"A sweep reversal": sweep, "B London breakout": london_breakout, "C Donchian 55/10": donchian,
          "D daily-trend pullback": trend_pullback, "E NR7 breakout": nr7, "F RANDOM (control)": random_entries}
