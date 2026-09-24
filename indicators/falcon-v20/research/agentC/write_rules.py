import pickle, os
HERE = os.path.dirname(os.path.abspath(__file__))
COMMON = """Common: entry at the CLOSE of signal bar i (long at ask = close+spread, short at bid). One position per instrument
(sim15-style sequential; a new setup is taken once flat, including on the exit bar). Stop/target prices are anchored on the
signal-bar close: long SL = close - dist, TP = close + m*dist (short mirrored). ATR = Wilder ATR(14) of the same timeframe.
Signals only from bar index >= 250 (warm-up). Costs: sim15 SPREAD per symbol + 0.5 pip swap per 17:00 NY rollover (Wed x3).
Setup tuple in pickle: (i, dir, sl_price, tp_price[, max_bars]) on the stated timeframe (H1 = bars(sym,3600), H4 = bars(sym,14400)).
Selection (pre-registered): max over grid of min(SEEN half-1 net avgR, SEEN half-2 net avgR), n>=30 per half; UNSEEN untouched.
Code: agentC/trend.py ; full grid in agentC/grid_log.txt
"""
RULES = {
 "F1_ma_cross": "Timeframe H4. EMA(9) and EMA(21) of close. Long when EMA9 crosses above EMA21 at bar i (EMA9[i]>EMA21[i] and EMA9[i-1]<=EMA21[i-1]); short on the opposite cross. Stop = 1.5*ATR(14). Target = 2R (2 x stop distance). No time exit.",
 "F2_supertrend": "Timeframe H4. Supertrend(ATR period 10, multiplier 3, TradingView formulation, Wilder ATR). Long on the bar the trend flips from down to up; short on flip up->down. Stop = 1.5*ATR(10). Target = 2R. No time exit.",
 "F3_macd_ema200": "Timeframe H4. MACD(12,26,9) on close. Long when MACD line crosses above signal line and close > EMA(200); short when MACD crosses below signal and close < EMA(200). No zero-line filter. Stop = 1.5*ATR(14). Exit on the close of the next opposite MACD/signal cross (encoded as max_bars = bars to that cross; target set at 100R i.e. none); stop always active. Reversal: the opposite cross is itself a new setup if it passes the EMA200 filter.",
 "F4_adx_di": "Timeframe H4. Wilder DMI/ADX(14). Long when +DI crosses above -DI and ADX > 25 at bar i; short when -DI crosses above +DI and ADX > 25. Stop = 1.5*ATR(14). Exit on the close of the next opposite DI cross (max_bars encoding, target 100R = none); stop always active.",
 "F5_bb_squeeze": "Timeframe H4. Bollinger(20, 2 population sd). Bandwidth = 4*sd/SMA20. Squeeze when bandwidth[i] <= min(bandwidth over last 120 bars incl. i); the squeeze stays armed for 20 bars. First close above the upper band -> long, first close below the lower band -> short (disarms). Stop at the middle band (SMA20) at the signal bar. Target = 2R. No time exit.",
 "F6_tsmom_daily": "Signal daily, executed on H1. New-York trading days (17:00 NY boundary; stub segments <12 H1 bars merged into the previous day). At each day's last H1 bar close: direction = sign(daily close today - daily close 20 days ago). Stop = 2.0 x daily Wilder ATR(14). No target (100R). Time exit at the close of the 5th following NY day (max_bars = H1 bars to that day end). Sequential: next entry is taken at the day-end on which the prior trade exits.",
 "F7_donchian": "Timeframe H4. Donchian 20: long when close[i] > highest high of bars i-20..i-1 AND close[i-1] <= highest high of bars i-21..i-2 (first close above the channel); short mirrored with lows. Stop = 2.0*ATR(14). Target = 1R. No time exit.",
}
summ = pickle.load(open(os.path.join(HERE, "summary.pkl"), "rb"))
for s in summ:
    S = s["S"]
    def c(k): return f"n={S[k]['n']} win={S[k]['win']:.1f}% netR={S[k]['avgR']:+.3f}+-{S[k]['se']:.3f}"
    txt = f"{s['fam']}  chosen config: {s['cfg']}\n\nRULES\n{RULES[s['fam']]}\n\n{COMMON}\nRESULTS (net)\n"
    for k, lab in (("all","ALL"),("seen","SEEN"),(("seen",0),"SEEN h1"),(("seen",1),"SEEN h2"),("unseen","UNSEEN"),(("unseen",0),"UNSEEN h1"),(("unseen",1),"UNSEEN h2")):
        txt += f"  {lab:10s} {c(k)}\n"
    txt += (f"  GROSS (no spread/swap) ALL avgR={s['gross']['avgR']:+.3f}+-{s['gross']['se']:.3f}\n  trades/week (11 syms)={s['tpw']:.1f}  avg hold={s['hold']:.1f}h\n"
            f"  random-entry control (5 seeds, same geometry, net): win={s['ctrl']['win']:.1f}% avgR={s['ctrl']['avgR']:+.3f}+-{s['ctrl']['se']:.3f}\n"
            f"  PASS (UNSEEN avgR>0 both halves): {s['passed']}\n")
    open(os.path.join(HERE, f"{s['fam']}_rules.txt"), "w").write(txt)
    print(s["fam"], "ok")
