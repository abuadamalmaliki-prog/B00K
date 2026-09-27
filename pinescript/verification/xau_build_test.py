"""Build the PineTS test copy of xauusd_asian_range_breakout.pine and real-data candle slices.
Usage: python3 xau_build_test.py <m5_utc.json> <m15_utc.json>
"""
import json, os, sys
from datetime import datetime, timezone
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, '..', 'xauusd_asian_range_breakout.pine')).read()
src = src.replace('syminfo.ticker', '"XAUUSD"')          # PineTS has no syminfo for raw candles
src += '''
plot(evPlan ? 1 : 0, "dbg_plan")
plot(evBuy ? 1 : 0, "dbg_buy")
plot(evSell ? 1 : 0, "dbg_sell")
plot(evTP ? 1 : 0, "dbg_tp")
plot(evSL ? 1 : 0, "dbg_sl")
plot(evTime ? 1 : 0, "dbg_time")
plot(exitPx, "dbg_exitPx")
plot(exitR, "dbg_exitR")
plot(nTrades, "dbg_nTrades")
plot(sumR, "dbg_sumR")
plot(maxDD, "dbg_maxDD")
'''
open(os.path.join(HERE, 'xau_test.pine'), 'w').write(src)
def ms(s): return int(datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp() * 1000)
slices = {
  'dst_spring_m5': (sys.argv[1], '2024-02-15', '2024-04-20'),
  'dst_autumn_m5': (sys.argv[1], '2024-10-10', '2024-12-10'),
  'y2025_m15':     (sys.argv[2], '2025-01-01', '2026-01-10'),
}
for name, (path, a, z) in slices.items():
    c = [x for x in json.load(open(path)) if ms(a) <= x['openTime'] < ms(z)]
    json.dump(c, open(os.path.join(HERE, f'xau_{name}.json'), 'w'))
    print(name, len(c))
