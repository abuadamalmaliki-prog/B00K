import json, math, random
random.seed(11)
N = 3000
c = []
px = 100.0
t0 = 1262304000000  # 2010-01-01
drift = 0.0
for i in range(N):
    if i % 150 == 0:
        drift = random.choice([-0.003, -0.001, 0.0, 0.001, 0.003])
    if 1800 <= i < 2100: drift = 0.004          # bubble
    if 2100 <= i < 2200: drift = -0.010         # crash
    vol = 0.012 * (1.8 if 2100 <= i < 2300 else 1.0)
    gap = random.gauss(0, vol * 0.3) + (random.choice([-1, 1]) * 3 * vol if random.random() < 0.02 else 0.0)
    o = px * math.exp(gap)
    cl = o * math.exp(drift + random.gauss(0, vol))
    hi = max(o, cl) * math.exp(abs(random.gauss(0, vol * 0.6)))
    lo = min(o, cl) * math.exp(-abs(random.gauss(0, vol * 0.6)))
    c.append({"open": round(o, 6), "high": round(hi, 6), "low": round(lo, 6), "close": round(cl, 6),
              "volume": 1000, "openTime": t0 + i * 86400000, "closeTime": t0 + (i + 1) * 86400000 - 1})
    px = cl
json.dump(c, open("candles.json", "w"))
print(len(c), c[0], c[-1]["close"])
