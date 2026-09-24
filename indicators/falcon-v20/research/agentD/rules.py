"""Write agentD/<family>_rules.txt for each chosen config (reads results.json from run.py)."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "results.json")))["summary"]
COMMON = """
COMMON RULES (all agentD families)
- Data: sim15 bars (BID), bar time = bar open (UTC); New York time via sim.ny(). H4 = common.resample(H1, 14400).
- ATR = Wilder ATR(14) of the signal-bar timeframe, value at the signal bar (uses bars <= i only).
- Entry at the CLOSE of signal bar i (long at ask = close + spread, short at bid). Zone/level "touch" entries are
  therefore entered at the close of the first touching bar, not at the level (sim15 has no limit fills).
- Stop: structure price named below +/- 0.10 x ATR buffer; widened if needed so it is >= 0.50 x ATR from the close.
  Setup discarded if the close is already beyond the structure.
- R-multiple targets: tp = fill + dir * k * (fill-to-stop distance), fill includes spread.
- Time exit: close of the 72nd H1 bar / 18th H4 bar after entry (72 hours), if neither stop nor target hit.
- One position at a time per instrument (sim15 run_sequential semantics, cooldown 0).
- Costs (net): sim15 SPREAD per symbol, swap 0.5 pip per 17:00 NY rollover (Wed x3). Gross = same setups, spread 0, swap 0.
- Setup tuple (i, dir, sl_price, tp_price, max_bars). Regenerate: cd v15 && python3 -c "import sys; sys.path.insert(0,'agentD');
  import fam; name,gen,tf=[g for g in fam.GRIDS['<FAMILY>'] if g[0]=='<CONFIG>'][0]; print(gen('EURUSD',tf)[:5])"
- Selection: best of the family grid by min(SEEN half-1 avg R, SEEN half-2 avg R) net, n>=30 per half; UNSEEN untouched.
"""
SPEC = {
 "F1_FVG": """Fair Value Gap first retest.
- Bullish FVG at bar k: L[k] > H[k-2] and L[k]-H[k-2] >= 0.25 ATR[k]; zone [H[k-2], L[k]] (bearish mirror: H[k] < L[k-2]).
- Armed for 48 bars after k. Signal = FIRST later bar j whose low <= L[k] (bull) / high >= H[k] (bear): enter at close of j,
  in the gap's direction. Structure for the stop = gap far edge (H[k-2] bull / L[k-2] bear). Target per config
  (1R, 2R, or 'swing' = impulse extreme: highest high from bar k-1 to j-1 for longs).""",
 "F2_OB": """Order-block retest after break of structure.
- Swing pivots: fractal strength p (H[k] > max of p bars left, >= max of p bars right), usable only from bar k+p.
- Bullish BOS at bar b: close > last confirmed swing high (each swing high breaks once). Impulse origin m = lowest-low bar
  between that swing high's bar and b. Order block = last bearish candle (C<O) at or up to 5 bars before m.
  Zone = [L_ob, H_ob]. Bearish mirror (close < last swing low; last bullish candle before the highest-high origin).
- Armed 48 bars after b. Signal = first later bar touching the block (low <= H_ob for longs): enter at its close.
  Stop structure = far side of block (L_ob longs / H_ob shorts). Target per config (1R/2R, 'ext' = impulse extreme).""",
 "F3_CANDLE": """Candlestick patterns at swing extremes (N = 20 bars).
- engulf: prev bar bearish, current bullish, O<=prev C, C>=prev O, body larger; min(L[i],L[i-1]) = lowest low of last 20 bars.
  Stop structure = pattern low. Bearish mirror at 20-bar highest high.
- pin: range >= 0.5 ATR; hammer: lower wick >= 2x body and >= 60% of range, upper wick <= 25% of range, L[i] = 20-bar low;
  stop structure = pin low. Shooting star mirror at 20-bar high.
- inside: mother bar m at 20-bar low (high), bar m+1 inside it; first close above mother high (below mother low) within
  3 bars -> long (short); cancelled if a close breaks the other side first. Stop structure = mother low (high).
- Entry at the pattern / breakout bar close. Target per config (1R or 2R).""",
 "F4_FIB": """Fibonacci 61.8% retracement with the leg (pivots 5/5).
- Leg up: most recent confirmed swing low (a) -> newly confirmed swing high (b), L[a] must be the leg's lowest low,
  leg >= min_leg x ATR at confirmation bar (b+5). Level = H[b] - 0.618 x leg. Skipped if the level was already hit
  between b and b+5. Armed 48 bars after confirmation; cancelled if price makes a new high above H[b] first.
- Signal = first bar touching the level: long at its close. Stop structure = leg origin L[a] (100%).
  Target 'ext' = H[b] or 1R. Leg down: mirror (short).""",
 "F5_PIVOT": """Classic floor pivots (H1). Day = New York 17:00 rollover day. From the previous completed day (>= 10 H1 bars):
  P = (H+L+C)/3, R1 = 2P - L, S1 = 2P - H. Only days whose first bar opens between S1 and R1.
- fade_touch: first bar of the day with high >= R1 -> short at its close (low <= S1 -> long). fade_reject: same first touch,
  but only if that bar closes back below R1 (above S1); otherwise no trade that day at that level.
  Stop = level +/- stop_atr x ATR. Target 'P' (pivot) or 1R.
- break_retest: first close above R1 in the day, then the first later bar (<= 24 bars) with low <= R1: long at its close if it
  closes above R1, otherwise cancelled (mirror at S1 for shorts). Stop = R1 - stop_atr x ATR (S1 + ... for shorts). Target 1R/2R.""",
 "F6_ROUND": """Round-number rejection fades. Level grid: '00+50' = every 50 pips (FX, JPY 0.50), XAGUSD $0.50, XAUUSD $50;
  '00' = every 100 pips (1.0800, 150.00), XAGUSD $1, XAUUSD $100.
- Short: X = nearest grid level above the close; bar high >= X > close, previous close < X, and no high >= X in the prior 24 bars
  (first touch from below). Stop structure = the bar's high. Long mirror at the level below the close (bar low).
- Entry at the rejection bar close. Target per config (1R / 2R).""",
 "F7_PDPW": """Prior-day / prior-week high-low break-and-retest continuation.
- Levels from H1 bars: previous New York day (17:00 rollover, >= 10 bars) or previous NY week (>= 50 bars) high and low.
  Period of a bar = period of its open time (H4 bars too).
- Break: first bar of the period that closes above the prior high with the previous close at/below it (long side);
  mirror below the prior low. Retest: first later bar (<= 24 bars) with low <= level; long at its close if it closes above the
  level, else cancelled. Stop structure = retest bar low (high for shorts). Target per config (1R / 2R).""",
}
def c(s): return f"win {s['win']:.1f}%  avgR {s['avgR']:+.3f} +/- {s['se']:.3f}  (n={s['n']})"
for f, r in R.items():
    txt = f"""{f}  chosen config: {r['config']}   (agentD)
Pickle: agentD/{f}.pkl = list of {r['ALL']['n']} NET sim15 trade dicts (all 11 instruments), each with 'sym' and 'setup'.

{SPEC[f]}
{COMMON.replace('<FAMILY>', f).replace('<CONFIG>', r['config'])}
RESULTS (net unless stated)
  ALL    {c(r['ALL'])}
  SEEN   {c(r['SEEN'])}   halves: {c(r['seen_h1'])} | {c(r['seen_h2'])}
  UNSEEN {c(r['UNSEEN'])}   halves: {c(r['unseen_h1'])} | {c(r['unseen_h2'])}
  GROSS avg R: ALL {r['gross_all']['avgR']:+.3f}  SEEN {r['gross_seen']['avgR']:+.3f}  UNSEEN {r['gross_unseen']['avgR']:+.3f}
  trades/week (11 instruments) {r['tpw']:.1f}; average hold {r['hold']:.1f} h
  Random-entry control (random bar & direction, same ATR-scaled stop/target, same time exit, 10 seeds): {c(r['control'])}
  PASS (UNSEEN avg R > 0 in both halves): {r['PASS']}    win>=60%: {r['win60']}
"""
    open(os.path.join(HERE, f"{f}_rules.txt"), "w").write(txt)
    print("wrote", f"{f}_rules.txt")
