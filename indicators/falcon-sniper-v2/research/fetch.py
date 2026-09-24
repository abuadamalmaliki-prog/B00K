import json, os, urllib.request, csv, sys, time
os.makedirs("data", exist_ok=True)
SYMS = {"EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X", "AUDUSD": "AUDUSD=X", "XAUUSD": "GC=F"}
JOBS = [("1h", "730d"), ("15m", "60d"), ("1d", "10y")]
for name, y in SYMS.items():
    for iv, rg in JOBS:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{y}?interval={iv}&range={rg}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        d = json.load(urllib.request.urlopen(req, timeout=30))["chart"]["result"][0]
        q = d["indicators"]["quote"][0]
        rows = [(t, o, h, l, c, v or 0) for t, o, h, l, c, v in zip(d["timestamp"], q["open"], q["high"], q["low"], q["close"], q["volume"]) if None not in (o, h, l, c)]
        with open(f"data/{name}_{iv}.csv", "w", newline="") as f:
            w = csv.writer(f); w.writerow(["time", "open", "high", "low", "close", "volume"]); w.writerows(rows)
        print(name, iv, len(rows))
        time.sleep(0.5)
