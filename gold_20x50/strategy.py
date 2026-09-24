"""Gold 20x50: 20 fixed-time XAUUSD longs a day, TP 50 pips, SL 2500 pips.

Rules
  * Direction: BUY only. Gold's long-run drift is up, and over 2020-2026 no SMC, trend or
    ML direction filter beat buy-only out of sample (see README).
  * Entries: one market buy at each of the 20 Malaysia-time slots below, every trading day.
  * TP: 50 pips ($5.00) from the fill. SL: 2500 pips ($250.00) from the fill, placed
    beyond the range that daily liquidity sweeps reach. No time exit.

"""
import numpy as np

SLOTS_MYT = [f'{h:02d}:00' for h in list(range(8, 24)) + [0, 1, 2, 3]]
TP_PIPS = 50
SL_PIPS = 2500
SPREAD_PIPS = 3.0


def direction(bars, entries):
    return np.ones(len(entries), np.int64)
