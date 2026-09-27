"""Download XAUUSD M1 (HistData.com format, 2009-2026) from the Hugging Face dataset
fokan/xauusd-2009-2026 and build m1_raw.parquet, m5.parquet, m15.parquet (New York local
time, which the data uses: the daily 17:00-18:00 break and the 08:30 / 10:00 US data
spikes sit at the same clock times in winter and summer), plus UTC candle JSON for the
indicator mirror. Needs: pandas, pyarrow. About 400 MB of downloads.
"""
import os, urllib.request
import pandas as pd
BASE = "https://huggingface.co/datasets/fokan/xauusd-2009-2026/resolve/main/"
FILES = [f"DAT_MT_XAUUSD_M1_{y}.csv" for y in list(range(2009, 2026))] + ["DAT_MT_XAUUSD_M1_202601.csv"]
os.makedirs("data", exist_ok=True)
for f in FILES:
    p = os.path.join("data", f)
    if not os.path.exists(p):
        print("downloading", f); urllib.request.urlretrieve(BASE + f, p)
df = pd.concat([pd.read_csv(os.path.join("data", f), header=None, names=["d", "t", "o", "h", "l", "c", "v"]) for f in FILES], ignore_index=True)
raw = pd.to_datetime(df["d"] + " " + df["t"], format="%Y.%m.%d %H:%M")
# The files' clock is New York local time up to 2018, but from 2019 it is London time minus
# 5 hours: it then switches daylight saving on the European dates, so for ~3 weeks in March and
# ~1 week around the end of October it is one hour behind New York (the 17:00 break shows at 16:00).
# Convert both eras to true UTC, then to New York local time.
pre = raw < pd.Timestamp("2019-01-01")
utc = pd.Series(pd.NaT, index=raw.index, dtype="datetime64[ns, UTC]")
utc[pre] = raw[pre].dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
utc[~pre] = (raw[~pre] + pd.Timedelta(hours=5)).dt.tz_localize("Europe/London", ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
df["ts"] = utc.dt.tz_convert("America/New_York").dt.tz_localize(None)
df = df.dropna(subset=["ts"]).drop(columns=["d", "t", "v"]).drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
df.to_parquet("m1_raw.parquet")
m1 = df.set_index("ts")[["o", "h", "l", "c"]]
for rule, name, step in (("5min", "m5", 300000), ("15min", "m15", 900000)):
    b = m1.resample(rule, label="left", closed="left").agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()
    b.to_parquet(f"{name}.parquet")
    idx = b.index.tz_localize("America/New_York", ambiguous="raise", nonexistent="raise").tz_convert("UTC")
    ms = ((idx - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta("1ms")).tolist()
    pd.DataFrame({"open": b.o.values, "high": b.h.values, "low": b.l.values, "close": b.c.values, "volume": 0,
                  "openTime": ms, "closeTime": [t + step - 1 for t in ms]}).to_json(f"{name}_utc.json", orient="records")
    print(name, len(b))
