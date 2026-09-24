import statistics
from engine import Engine, DEFAULTS, load, resample
PIPS = {"EURUSD": 0.0001, "GBPUSD": 0.0001, "AUDUSD": 0.0001, "NZDUSD": 0.0001, "USDCAD": 0.0001, "GBPAUD": 0.0001,
        "USDJPY": 0.01, "EURJPY": 0.01, "GBPJPY": 0.01, "XAUUSD": 0.1, "XAGUSD": 0.01}
HTF = {3600: 14400, 14400: 86400}
_cache = {}
def bars(sym, tf):
    k = (sym, tf)
    if k not in _cache:
        h1 = load(f"data/{sym}_1h.csv")
        _cache[k] = h1 if tf == 3600 else resample(h1, tf)
    return _cache[k]
def run(sym, tf, **over):
    P = dict(DEFAULTS); P.update(over); P["_htf_secs"] = HTF[tf]
    rows = bars(sym, tf)
    trades, sigs, atrs = Engine(P).run(rows, resample(rows, HTF[tf]), PIPS[sym], tf)
    return rows, trades
def daily_range_pips(sym, n=260):
    d = resample(bars(sym, 3600), 86400)[-n:]
    return statistics.mean((h - l) for _, o, h, l, c, v in d) / PIPS[sym]
def path(rows, t, pip, target=300, be_at=None, max_bars=None):
    """Walk the price path after entry. Returns (outcome, mfe_pips) where outcome is
    'tp' (reached target), 'sl' (initial stop), 'be' (breakeven stop) or 'open'."""
    i0, d, e = t["i"], (1 if t["tp"][0] > t["entry"] else -1), t["entry"]
    sl = e - d * t["riskPips"] * pip
    tp = e + d * target * pip
    mfe, be_on = 0.0, False
    end = len(rows) if max_bars is None else min(len(rows), i0 + 1 + max_bars)
    for k in range(i0 + 1, end):
        _, o, h, l, c, v = rows[k]
        stop = e if be_on else sl
        if (l <= stop) if d == 1 else (h >= stop):
            return ("be" if be_on else "sl"), mfe
        fav = (h - e) / pip if d == 1 else (e - l) / pip
        mfe = max(mfe, fav)
        if fav >= target: return "tp", mfe
        if be_at is not None and fav >= be_at: be_on = True
    return "open", mfe
