"""Download XAUUSD 1-minute bid and ask candles from Dukascopy's public datafeed.

Output: data/XAUUSD_m1.csv.gz with UTC time, bid OHLC, ask OHLC, and volume.
Closed-market minutes (volume 0, flat) are dropped.
"""
import concurrent.futures as cf, datetime as dt, gzip, lzma, os, struct, sys, time, urllib.request

SYM = os.environ.get("SYM", "XAUUSD")
SCALE = {"XAUUSD": 1000.0, "XAGUSD": 1000.0, "USDJPY": 1000.0, "EURJPY": 1000.0, "GBPJPY": 1000.0}.get(SYM, 100000.0)
def _d(x): return dt.date(int(x[:4]), int(x[4:6]), int(x[6:]))
START, END = (_d(sys.argv[1]), _d(sys.argv[2])) if len(sys.argv) > 2 else (dt.date(2025, 1, 1), dt.date(2026, 9, 23))
NAME = sys.argv[3] if len(sys.argv) > 3 else "XAUUSD_m1"
OUT = os.path.join(os.path.dirname(__file__), "data")
CACHE = os.path.join(OUT, "cache" if SYM == "XAUUSD" else "cache_" + SYM)
os.makedirs(CACHE, exist_ok=True)


def fetch(day, side):
    path = os.path.join(CACHE, f"{day:%Y%m%d}_{side}.bin")
    if os.path.exists(path):
        return open(path, "rb").read()
    url = f"https://datafeed.dukascopy.com/datafeed/{SYM}/{day.year}/{day.month - 1:02d}/{day.day:02d}/{side}_candles_min_1.bi5"
    for attempt in range(14):
        try:
            raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=15).read()
            data = lzma.decompress(raw) if raw else b""
            if len(data) % 24:
                raise ValueError("bad length")
            open(path, "wb").write(data)
            return data
        except Exception as e:  # 503s and resets happen; back off and retry
            time.sleep(min(8, 0.5 * 2 ** attempt))
    print("failed", url, flush=True)
    return None


def decode(day, data):
    base = int(dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc).timestamp())
    for i in range(len(data) // 24):
        t, o, c, lo, hi, v = struct.unpack(">5If", data[i * 24:(i + 1) * 24])
        yield base + t, o / SCALE, hi / SCALE, lo / SCALE, c / SCALE, v


days = [START + dt.timedelta(d) for d in range((END - START).days + 1)]
days = [d for d in days if d.weekday() != 5]  # Saturday has no trading
jobs = [(d, s) for d in days for s in ("BID", "ASK")]
with cf.ThreadPoolExecutor(6) as ex:
    res = dict(zip(jobs, ex.map(lambda j: fetch(*j), jobs)))
rows = 0
with gzip.open(os.path.join(OUT, NAME + ".csv.gz"), "wt") as f:
    f.write("time,bo,bh,bl,bc,ao,ah,al,ac,vol\n")
    for d in days:
        if res[(d, "BID")] is None or res[(d, "ASK")] is None:
            continue
        bid = {r[0]: r for r in decode(d, res[(d, "BID")])}
        ask = {r[0]: r for r in decode(d, res[(d, "ASK")])}
        for t in sorted(bid):
            b, a = bid[t], ask.get(t)
            if a is None or b[5] <= 0:
                continue
            f.write(f"{t},{b[1]:.3f},{b[2]:.3f},{b[3]:.3f},{b[4]:.3f},{a[1]:.3f},{a[2]:.3f},{a[3]:.3f},{a[4]:.3f},{b[5]:.4f}\n")
            rows += 1
print("days", len(days), "rows", rows)
