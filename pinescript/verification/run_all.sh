#!/usr/bin/env bash
# Re-runs every check behind research_trend_signals.pine.
# Needs python3 with numpy + scipy, and Node 18+ (npm installs PineTS locally).
set -euo pipefail
cd "$(dirname "$0")"
echo "## 1. Math: one-sided HP Kalman vs exact HP, Avellaneda-Stoikov vs paper tables"
python3 verify_math.py
echo
echo "## 2. Run the real Pine script in PineTS and compare with the Python mirror"
echo "   Expected: events MATCH in both modes. Values match exactly only in PineTS-compat mode,"
echo "   because PineTS rounds to 10 decimals and seeds ta.rma one bar early (TradingView does neither)."
[ -d node_modules/pinets ] || npm install --silent
python3 gen_candles.py
python3 build_tests.py
for t in A B C; do
  node run_pine.mjs candles.json "test_$t.pine" "pine_$t.json" > /dev/null
  echo "-- config $t, TradingView-semantics mirror:"
  python3 mirror.py candles.json "cfg_$t.json" "mirror_$t.json" > /dev/null
  python3 compare.py "$t" | tail -1
  echo "-- config $t, PineTS-compat mirror:"
  python3 mirror.py candles.json "cfg_$t.json" "mirror_$t.json" --pinets-compat > /dev/null
  python3 compare.py "$t" | tail -1
done
