"""Look-ahead test for the full signal pipeline. Run: python3 test_strategy.py path/to/csv"""
import sys

import numpy as np

import data
import strategy


def test_signals_causal(path, cuts=8, seed=1):
    m = data.load(path, gap=strategy.FINAL_GAP)
    full = strategy.signals(m, strategy.build_features(m, tfs=('D1',)), **strategy.FINAL)
    rng = np.random.default_rng(seed)
    for k in sorted(rng.integers(20_000, len(m), cuts)):
        p = m.iloc[:k]
        part = strategy.signals(p, strategy.build_features(p, tfs=('D1',)), **strategy.FINAL)
        # the last bar is excluded: whether a next bar exists is unknown in the prefix
        assert np.array_equal(part[:-1], full[:k - 1]), f'look-ahead at cut {k}'
    print(f'PASS test_signals_causal ({cuts} cuts, {int((full != 0).sum())} signals)')


if __name__ == '__main__':
    test_signals_causal(sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD_M1_H1_2025-2026Aug.csv')
