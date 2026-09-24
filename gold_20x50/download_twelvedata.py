"""Download XAU/USD bars from Twelve Data (UTC). Usage:
    TWELVEDATA_API_KEY=... python3 download_twelvedata.py 1min 2024-01-01
Writes data/XAUUSD_<interval>.csv. Resumable. Paces requests to the Basic plan (8/min)."""
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request

KEY = os.environ.get('TWELVEDATA_API_KEY')
URL = 'https://api.twelvedata.com/time_series?'


def fetch(params, state={'last': 0.0}):
    wait = 8.0 - (time.time() - state['last'])
    if wait > 0:
        time.sleep(wait)
    state['last'] = time.time()
    for attempt in range(5):
        try:
            with urllib.request.urlopen(URL + urllib.parse.urlencode(params), timeout=60) as r:
                return json.load(r)
        except Exception as e:
            print('retry', attempt, e, flush=True)
            time.sleep(4 * 2 ** attempt)
    raise RuntimeError('request failed 5 times')


def download(interval, start, out_dir='data'):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f'XAUUSD_{interval}.csv')
    rows = {}
    if os.path.exists(path):
        rows = {r['datetime']: r for r in csv.DictReader(open(path))}
    end = min(rows) if rows else None
    while True:
        p = dict(symbol='XAU/USD', interval=interval, outputsize=5000, timezone='UTC',
                 order='desc', apikey=KEY)
        if end:
            p['end_date'] = end
        d = fetch(p)
        if d.get('status') != 'ok':
            if d.get('code') == 429:
                time.sleep(60)
                continue
            print(interval, 'stopped:', d.get('message'), flush=True)
            break
        v = d['values']
        new = sum(r['datetime'] not in rows for r in v)
        rows.update({r['datetime']: r for r in v})
        end = v[-1]['datetime']
        with open(path, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['datetime', 'open', 'high', 'low', 'close'])
            w.writeheader()
            for k in sorted(rows):
                w.writerow({c: rows[k][c] for c in w.fieldnames})
        print(interval, len(rows), end, flush=True)
        if new == 0 or end < start or len(v) < 5000:
            break


if __name__ == '__main__':
    if not KEY:
        sys.exit('set TWELVEDATA_API_KEY')
    download(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '2020-01-01')
