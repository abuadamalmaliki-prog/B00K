"""Hand-built price paths that check the simulator's fills and ordering rules."""
import numpy as np
from frost import _sim

S = 0.3  # spread


def run(bars, d, ref, sl, t1, t2, be=False, max_hold=100, ny=600):
    o, h, l, c = (np.array(x, float) for x in zip(*bars))
    ao, ah, al, ac = o + S, h + S, l + S, c + S
    n = len(o)
    return _sim(o, h, l, c, ao, ah, al, ac, np.full(n, ny, np.int64), np.full(n, 1, np.int64),
                np.array([0]), np.array([d]), np.array([ref]), np.array([sl]), np.array([t1]), np.array([t2]),
                max_hold, be, True, 0.0, 16 * 60 + 50)[0]


# long from 100 (fill at ask 100.3), SL 99, TP1 101, TP2 102; risk 1.0
sig = [(100, 100, 100, 100)]
r = run(sig + [(100, 100.2, 99.8, 100.1), (100.1, 101.2, 100, 101), (101, 102.5, 100.9, 102)], 1, 100, 99, 101, 102)
assert abs(r[1] - 0.7) < 1e-9 and abs(r[2] - 1.7) < 1e-9 and r[4] == 1 and r[5] == 1, r
r = run(sig + [(100, 101.5, 98.5, 100)], 1, 100, 99, 101, 102)          # same bar: stop wins
assert abs(r[1] + 1.3) < 1e-9 and abs(r[2] + 1.3) < 1e-9 and r[6] == 1, r
r = run(sig + [(100, 101.1, 99.9, 101), (101, 101, 100.0, 100.1)], 1, 100, 99, 101, 102, be=True)  # BE after TP1
assert abs(r[1] - 0.7) < 1e-9 and abs(r[2] - 0.0) < 1e-9, r
r = run(sig + [(100, 101.1, 99.9, 101), (101, 101, 100.0, 100.1), (100.1, 100.2, 98.9, 99)], 1, 100, 99, 101, 102)  # split: runner stopped
assert abs(r[1] - 0.7) < 1e-9 and abs(r[2] + 1.3) < 1e-9, r
r = run(sig + [(100, 100.5, 99.5, 100), (98.0, 98.5, 97.5, 98)], 1, 100, 99, 101, 102)  # gap through stop
assert abs(r[1] + 2.3) < 1e-9, r
# short from 100 (fill at bid 100), SL 101 (ask), TP1 99, TP2 98 (ask)
r = run(sig + [(100, 100.6, 99.5, 99.8), (99.8, 100, 98.6, 98.7), (98.7, 98.9, 97.6, 97.7)], -1, 100, 101, 99, 98)
assert abs(r[1] - 1.0) < 1e-9 and abs(r[2] - 2.0) < 1e-9, r
r = run(sig + [(100, 100.75, 99.5, 99.8)], -1, 100, 101, 99, 98)        # ask high 101.05 hits SL
assert abs(r[1] + 1.0) < 1e-9 and r[6] == 1, r
r = run(sig + [(100, 100.2, 99.9, 100)] * 5, 1, 100, 99, 101, 102, max_hold=3)  # time exit at bid close
assert abs(r[0] - (100 - 100.3)) < 1e-9 and r[3] == 4, r
print("engine tests: all passed")
