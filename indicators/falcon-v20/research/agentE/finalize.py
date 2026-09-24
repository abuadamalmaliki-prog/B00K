"""For each family's SEEN-selected config: ALL/SEEN/UNSEEN stats, GROSS R, trades/week, hold, random-entry
control (5 seeds, identical exit geometry, same costs), PASS flag; pickle NET trades + rules txt."""
import sys, os, pickle, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
from fam import FAMILIES, RATE
HERE = os.path.dirname(os.path.abspath(__file__))
SEL = {"F1_time_of_day": "F1 open08 N3 sellOpening", "F2_day_of_week": "F2 fri10 fade",
       "F3_weekend_gap": "F3 thr0.2 stop2xgap tp1", "F4_month_week_end_fix": "F4 WE pre_fade",
       "F5_vol_regime": "F5 thr1.5 fade atr", "F6_ny_orb": "F6 tp0.5W stopopp sig<= 12",
       "F7_carry_mom": "F7 hold1d stop2.0xADR mom20"}
COST = ("Costs (sim15): spread EURUSD1.2 GBPUSD1.5 AUDUSD1.5 NZDUSD2 USDCAD2 GBPAUD3.5 USDJPY1.5 EURJPY2 GBPJPY3 XAU3 XAG3 pips; "
        "swap 0.5 pip/night cost (Wed x3); stop-first; gapped stops at open; one position per instrument (sim15.run_sequential, cooldown 0).")
ATR = "ATR24 = simple mean of the last 24 H1 true ranges incl. the signal bar. Stop distance = 1.5*sqrt(hold_hours)*ATR24 from entry (long entry = ask). Target = 50x risk (i.e. none: stop or time exit)."
RULES = {
 "F1_time_of_day": f"""F1 time-of-day, 'sell the currency whose market is opening' at the New York open.
Signal bar = H1 bar opening 07:00 New York (enter at its close = 08:00 NY), Mon-Fri. Opening currencies at 08:00 NY = USD, CAD.
Direction: sell the opening currency: long EURUSD/GBPUSD/AUDUSD/NZDUSD/XAUUSD/XAGUSD, short USDJPY/USDCAD; crosses (GBPAUD,EURJPY,GBPJPY) no trade.
Hold 3 bars (time exit at close of bar opening 10:00 NY = 11:00 NY). {ATR}
(Grid: open 03/08/19 NY x hold 3/6 x sell/buy opening ccy; 10 configs, see run_log.txt.)""",
 "F2_day_of_week": f"""F2 Friday position squaring: fade the week-to-date move on Friday.
FX day = 17:00 NY to 17:00 NY. Week move = close of Friday's bar opening 09:00 NY (entry 10:00 NY) minus the open of that week's Monday FX day (Sunday evening).
Direction = opposite the week move. Exit: time exit at the close of Friday's last FX-day bar (~16:00-17:00 NY). {ATR}""",
 "F3_weekend_gap": """F3 weekend gap fade. Reopen bar = first H1 bar after a >20h break (in this data the week starts at 00:00 UTC Monday, i.e. 19:00/20:00 NY Sunday).
gap = reopen bar open - previous (Friday) close. Trade only if |gap| >= 0.20 * avg FX-day range of the previous 20 days.
Enter at the close of the reopen bar, direction = against the gap. Target = Friday close (full fill). Stop = reopen open + sign(gap)*2*|gap| (2x gap beyond the reopen price).
Setups whose entry is already past the stop or the target are skipped (sim15 returns None). Time exit after 48 bars.""",
 "F4_month_week_end_fix": f"""F4 week-end London 16:00 fix, pre-fix fade. Every Friday: P = H1 bar opening 15:00 London (fix at its close, 16:00 London).
Enter at the close of the bar before P (15:00 London ~ 10:00 NY). Week-to-date move = entry close - open of the first bar after the weekend break.
Direction = against the week-to-date move. Exit at the fix (1-bar time exit). {ATR}""",
 "F5_vol_regime": f"""F5 volatility regime fade. FX day (17:00-17:00 NY) whose high-low range > 1.5x the average range of the previous 20 FX days.
Enter at that day's close (close of its last H1 bar = 17:00 NY), direction opposite the day's close-open sign. Hold 24 bars. {ATR}""",
 "F6_ny_orb": """F6 New York opening-range breakout, small target. OR = H1 bar opening 08:00 NY (hi, lo, W=hi-lo), Mon-Fri.
First bar opening 09:00..12:00 NY whose close > hi (long) or < lo (short) -> enter at its close (one signal/day).
Stop = opposite side of the OR. Target = entry +- 0.5*W. Time exit at the close of the bar opening 15:00 NY (16:00 NY).""",
 "F7_carry_mom": f"""F7 carry direction + 20-day momentum. Assumed avg policy rates Dec-2023..Sep-2026 (%): {RATE}.
Carry dir = sign(rate_base - rate_quote) if |diff| >= 0.5 else no trade -> short EURUSD, AUDUSD, NZDUSD, XAUUSD, XAGUSD; long USDCAD, USDJPY, EURJPY, GBPJPY, GBPAUD; GBPUSD none.
Daily at the FX-day close (close of the H1 bar opening 16:00 NY): enter in the carry direction only if the FX-day close is beyond (in carry direction) the close 20 FX days earlier.
Stop = 2.0 x avg FX-day range(20) from entry; no target; time exit after 24 bars; re-enter at the next daily close if still valid.
Swap: carry side EARNS +0.5 pip/night (Wed x3) instead of paying (sim15 trade(..., swap=-0.5)). Random control: carry side +0.5, other side -0.5.""",
}
rows_out = {}
for fam, cfgs in FAMILIES.items():
    name, gen, swapf = [c for c in cfgs if c[0] == SEL[fam]][0]
    trs = lib.evaluate(gen, swapf=swapf)
    A, S, U = lib.cell(trs), lib.cell(trs, "seen"), lib.cell(trs, "unseen")
    u1, u2 = lib.cell(trs, "unseen", 0), lib.cell(trs, "unseen", 1)
    s1, s2 = lib.cell(trs, "seen", 0), lib.cell(trs, "seen", 1)
    G = lib.gross(trs); GS = lib.gross([t for t in trs if t["grp"] == "seen"]); GU = lib.gross([t for t in trs if t["grp"] == "unseen"])
    C, cn = lib.control(trs, seeds=5, swapf=swapf)
    ok = u1["avgR"] > 0 and u2["avgR"] > 0
    r = dict(config=name, ALL=A, SEEN=S, UNSEEN=U, s1=s1, s2=s2, u1=u1, u2=u2, gross_all=G["avgR"], gross_seen=GS["avgR"],
             gross_unseen=GU["avgR"], gross_win=G["win"], tpw=lib.tpw(trs), hold=lib.hold(trs), ctl=C, ctl_n_per_seed=cn, PASS=ok,
             win60=A["win"] >= 60)
    rows_out[fam] = r
    print(f"{fam}: {name}")
    for k in ("ALL", "SEEN", "UNSEEN"): print(f"   {k:6s} {lib.fmt(r[k])}")
    print(f"   halves s1 {s1['avgR']:+.3f} s2 {s2['avgR']:+.3f} u1 {u1['avgR']:+.3f} u2 {u2['avgR']:+.3f} | PASS={ok} win>=60={r['win60']}")
    print(f"   GROSS R all {G['avgR']:+.3f} (win {G['win']:.1f}%) seen {GS['avgR']:+.3f} unseen {GU['avgR']:+.3f} | {r['tpw']:.1f} tr/wk | hold {r['hold']:.1f}h")
    print(f"   CONTROL (random bar+dir, same geometry, 5 seeds) {lib.fmt(C)} (n/seed {cn:.0f})")
    per = " ".join(f"{s}:{lib.stats([t for t in trs if t['sym']==s])['avgR']:+.2f}({sum(1 for t in trs if t['sym']==s)})" for s in lib.ALL)
    print(f"   per-sym {per}", flush=True)
    assert all("sym" in t and "setup" in t for t in trs)
    base = os.path.join(HERE, fam)
    pickle.dump(trs, open(base + ".pkl", "wb"))
    with open(base + "_rules.txt", "w") as f:
        f.write(RULES[fam] + "\n\n" + COST + "\nH1 bars, BID prices, bar time = bar open; New York time = sim.ny().\n"
                f"Selected on SEEN only by max(min(SEEN-half avg R)). Pickle: {len(trs)} NET sim15 trade dicts (all 11 instruments) with 'sym','setup'.\n"
                f"Result: UNSEEN h1 {u1['avgR']:+.3f} h2 {u2['avgR']:+.3f} -> {'PASS' if ok else 'FAIL'}.\n")
json.dump({k: {kk: vv for kk, vv in v.items()} for k, v in rows_out.items()}, open(os.path.join(HERE, "final.json"), "w"), indent=1, default=str)
