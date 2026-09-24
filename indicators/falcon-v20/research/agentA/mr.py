"""agentA: mean-reversion families on H1, evaluated with sim15 (costs: spread per symbol + 0.5 pip swap/night).

Families (each grid <= 12 configs; every config is reported):
  RSI2  : Connors RSI(2) pullback in the direction of EMA(200).
  BB    : Bollinger(20,2) close-outside -> close-back-inside fade toward the middle band.
  ASIA  : Asian-range (bars starting 19:00..01:00 NY) false-break fade during 02:00..05:00 NY bars.
  PDHL  : previous NY-day (17:00-17:00 NY) high/low false-break fade toward previous-day midpoint.

All signals use only information available at the close of the signal bar i; entry at that close (sim15).
Setup tuple: (i, dir, sl_price, tp_price, max_bars).

Pre-registered selection rule (SEEN instruments only, both halves):
  eligible = SEEN win >= 65% AND avgR > 0 in BOTH halves; pick eligible config with highest pooled SEEN avgR.
  If none eligible: pick config with highest pooled SEEN avgR among those with pooled SEEN win >= 65%;
  if still none, highest pooled SEEN avgR overall.
PASS (UNSEEN only): win >= 65% AND avgR > 0 in BOTH halves.
"""
import math, random, statistics
from datetime import timedelta
from common import PIPS, bars
from sim import ny
from sim15 import SPREAD, SEEN, UNSEEN

ALL = SEEN + UNSEEN

# ---------------------------------------------------------------- indicators
def ema(xs, n):
    out, a, v = [None] * len(xs), 2 / (n + 1), None
    for k, x in enumerate(xs):
        v = x if v is None else a * x + (1 - a) * v
        if k >= n - 1: out[k] = v
    return out

def atr(rows, n=14):
    out, v, prev = [None] * len(rows), None, None
    trs = []
    for k, (t, o, h, l, c, _) in enumerate(rows):
        tr = h - l if prev is None else max(h - l, abs(h - prev), abs(l - prev))
        prev = c
        if v is None:
            trs.append(tr)
            if len(trs) == n: v = sum(trs) / n
        else:
            v = (v * (n - 1) + tr) / n
        out[k] = v
    return out

def rsi(xs, n=2):
    out = [None] * len(xs)
    ag = al = None; g0 = []; l0 = []
    for k in range(1, len(xs)):
        ch = xs[k] - xs[k - 1]
        g, l = max(ch, 0.0), max(-ch, 0.0)
        if ag is None:
            g0.append(g); l0.append(l)
            if len(g0) == n: ag, al = sum(g0) / n, sum(l0) / n
            else: continue
        else:
            ag = (ag * (n - 1) + g) / n; al = (al * (n - 1) + l) / n
        out[k] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return out

def bollinger(xs, n=20, k=2.0):
    mid, up, lo = [None] * len(xs), [None] * len(xs), [None] * len(xs)
    for i in range(n - 1, len(xs)):
        w = xs[i - n + 1:i + 1]
        m = sum(w) / n; sd = statistics.pstdev(w)
        mid[i], up[i], lo[i] = m, m + k * sd, m - k * sd
    return mid, up, lo

_ind = {}
def ind(sym, tf=3600):
    key = (sym, tf)
    if key not in _ind:
        rows = bars(sym, tf); C = [r[4] for r in rows]
        _ind[key] = dict(rows=rows, C=C, A=atr(rows), R2=rsi(C, 2), E200=ema(C, 200), E5=ema(C, 5),
                         BB=bollinger(C), NY=[ny(r[0]) for r in rows])
    return _ind[key]

WARM = 250  # skip warm-up bars

# ---------------------------------------------------------------- family 1: RSI(2)
def g_rsi2(thr, stop_atr, exit_kind):
    """Long: RSI2 < thr and close > EMA200. Short: RSI2 > 100-thr and close < EMA200.
    stop = entry close -/+ stop_atr*ATR14. exit_kind: ('atr', m, mb) target = close +/- m*ATR, time cap mb bars;
    ('ema5', mb) target = EMA(5) value at the signal bar, time cap mb bars."""
    def gen(sym, tf):
        D = ind(sym, tf); C, A, R, E, E5 = D['C'], D['A'], D['R2'], D['E200'], D['E5']
        out = []
        for i in range(WARM, len(C) - 1):
            if R[i] is None or E[i] is None: continue
            d = 1 if (R[i] < thr and C[i] > E[i]) else (-1 if (R[i] > 100 - thr and C[i] < E[i]) else 0)
            if not d: continue
            sl = C[i] - d * stop_atr * A[i]
            if exit_kind[0] == 'atr':
                tp = C[i] + d * exit_kind[1] * A[i]; mb = exit_kind[2]
            else:
                tp = E5[i]; mb = exit_kind[1]
                if d * (tp - C[i]) <= 0: continue
            out.append((i, d, sl, tp, mb))
        return out
    return gen

RSI2_GRID = []
for thr in (5, 10):
    for sa in (1.5, 2.5):
        for ex in (('atr', 0.5, 10), ('atr', 1.0, 10), ('ema5', 5)):
            nm = f"RSI2 thr{thr} sl{sa}ATR " + (f"tp{ex[1]}ATR/{ex[2]}b" if ex[0] == 'atr' else f"tpEMA5/{ex[1]}b")
            RSI2_GRID.append((nm, g_rsi2(thr, sa, ex), dict(thr=thr, stop_atr=sa, exit=ex)))

# ---------------------------------------------------------------- family 2: Bollinger fade
def g_bb(tgt, buf, mb):
    """Short when close[i-1] > upper[i-1] and close[i] <= upper[i] (and close[i] > mid[i]);
    stop = highest high of the excursion (consecutive closes above the band ending at i-1, plus bar i) + buf*ATR;
    target = mid[i] ('mid') or close - 0.5*(close-mid) ('half'); time exit after mb bars. Long mirror."""
    def gen(sym, tf):
        D = ind(sym, tf); rows, C, A = D['rows'], D['C'], D['A']; M, U, L = D['BB']
        out = []
        for i in range(WARM, len(C) - 1):
            if U[i - 1] is None: continue
            for d in (-1, 1):
                if d == -1: outside = C[i - 1] > U[i - 1] and C[i] <= U[i] and C[i] > M[i]
                else: outside = C[i - 1] < L[i - 1] and C[i] >= L[i] and C[i] < M[i]
                if not outside: continue
                j = i - 1
                while j - 1 >= 0 and U[j - 1] is not None and ((C[j - 1] > U[j - 1]) if d == -1 else (C[j - 1] < L[j - 1])):
                    j -= 1
                if d == -1: ext = max(r[2] for r in rows[j:i + 1]); sl = ext + buf * A[i]
                else: ext = min(r[3] for r in rows[j:i + 1]); sl = ext - buf * A[i]
                tp = M[i] if tgt == 'mid' else C[i] + 0.5 * (M[i] - C[i])
                out.append((i, d, sl, tp, mb))
        return out
    return gen

BB_GRID = []
for tgt in ('mid', 'half'):
    for buf in (0.25, 1.0):
        for mb in (10, 30):
            BB_GRID.append((f"BB {tgt} buf{buf}ATR {mb}b", g_bb(tgt, buf, mb), dict(target=tgt, buf_atr=buf, max_bars=mb)))

# ---------------------------------------------------------------- family 3: Asian-range fade
def g_asia(tgt, buf, mb):
    """Asian range = high/low of bars whose NY start hour is 19,20,...,23,0,1 (session starting 19:00 NY).
    On bars starting 02:00..05:00 NY: if high > rangeHigh and close < rangeHigh (and close > rangeLow) -> short;
    stop = highest high since 02:00 + buf*ATR; target = range midpoint ('mid') or range low ('opp'). Mirror for lows.
    One signal per session per symbol (first one). Time exit after mb bars."""
    def gen(sym, tf):
        if tf != 3600: return []
        D = ind(sym, tf); rows, C, A, N = D['rows'], D['C'], D['A'], D['NY']
        out, hi, lo, taken, sh, sl_ = [], None, None, True, None, None
        for i in range(len(rows)):
            t, o, h, l, c, v = rows[i]; hr = N[i].hour
            if hr == 19:
                hi, lo, taken, sh, sl_ = h, l, False, None, None
            elif hi is not None and (hr >= 20 or hr < 2) and sh is None:
                hi, lo = max(hi, h), min(lo, l)
            elif hi is not None and 2 <= hr < 6 and not taken and i >= WARM and i < len(rows) - 1:
                sh = h if sh is None else max(sh, h); sl_ = l if sl_ is None else min(sl_, l)
                mid = (hi + lo) / 2
                if h > hi and lo < c < hi:
                    tp = mid if tgt == 'mid' else lo
                    out.append((i, -1, sh + buf * A[i], tp, mb)); taken = True
                elif l < lo and lo < c < hi:
                    tp = mid if tgt == 'mid' else hi
                    out.append((i, 1, sl_ - buf * A[i], tp, mb)); taken = True
            elif hi is not None and 6 <= hr < 19:
                hi = None
        return out
    return gen

ASIA_GRID = []
for tgt in ('mid', 'opp'):
    for buf in (0.1, 0.5):
        for mb in (6, 16):
            ASIA_GRID.append((f"ASIA {tgt} buf{buf}ATR {mb}b", g_asia(tgt, buf, mb), dict(target=tgt, buf_atr=buf, max_bars=mb)))

# ---------------------------------------------------------------- family 4: previous-day high/low fade
def trade_day(n):
    return (n + timedelta(hours=7)).date()  # NY day 17:00 -> 17:00, labelled by the date it ends

def g_pdhl(tgt, buf, mb):
    """NY trading day = 17:00-17:00 New York (weekday-labelled days only). For bars of day D with previous full
    weekday day P: if high > P.high and close < P.high and close > P.mid -> short, stop = bar high + buf*ATR,
    target = P.mid ('mid') or halfway from close to P.mid ('half'); mirror at P.low. First signal per day only.
    Time exit after mb bars."""
    def gen(sym, tf):
        if tf != 3600: return []
        D = ind(sym, tf); rows, C, A, N = D['rows'], D['C'], D['A'], D['NY']
        days = {}
        order = []
        for i, r in enumerate(rows):
            k = trade_day(N[i])
            if k.weekday() >= 5: continue
            if k not in days: days[k] = [r[2], r[3]]; order.append(k)
            else: days[k][0] = max(days[k][0], r[2]); days[k][1] = min(days[k][1], r[3])
        prev = {order[j]: order[j - 1] for j in range(1, len(order))}
        out, done = [], set()
        for i in range(WARM, len(rows) - 1):
            k = trade_day(N[i])
            if k.weekday() >= 5 or k in done or k not in prev: continue
            ph, pl = days[prev[k]]; pm = (ph + pl) / 2
            t, o, h, l, c, v = rows[i]
            if h > ph and pm < c < ph:
                tp = pm if tgt == 'mid' else c + 0.5 * (pm - c)
                out.append((i, -1, h + buf * A[i], tp, mb)); done.add(k)
            elif l < pl and pl < c < pm:
                tp = pm if tgt == 'mid' else c + 0.5 * (pm - c)
                out.append((i, 1, l - buf * A[i], tp, mb)); done.add(k)
        return out
    return gen

PDHL_GRID = []
for tgt in ('mid', 'half'):
    for buf in (0.1, 0.5):
        for mb in (12, 48):
            PDHL_GRID.append((f"PDHL {tgt} buf{buf}ATR {mb}b", g_pdhl(tgt, buf, mb), dict(target=tgt, buf_atr=buf, max_bars=mb)))

FAMILIES = [("RSI2", RSI2_GRID), ("BB", BB_GRID), ("ASIA", ASIA_GRID), ("PDHL", PDHL_GRID)]

# ---------------------------------------------------------------- random-entry control
def random_control(gen, taken_setups, seed):
    """Same exit geometry (stop & target distance from the signal close, same time cap) as each executed setup,
    placed on a random bar with a random direction; one random setup per executed trade."""
    rng = random.Random(seed)
    def rgen(sym, tf):
        D = ind(sym, tf); C = D['C']
        out = []
        for (i, d, sl, tp, *mb) in taken_setups.get(sym, []):
            rd, rw = abs(C[i] - sl), abs(tp - C[i])
            j = rng.randrange(WARM, len(C) - 1); dd = rng.choice((-1, 1))
            out.append((j, dd, C[j] - dd * rd, C[j] + dd * rw, *mb))
        return out
    return rgen
