import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, '..', 'research_trend_signals.pine')).read()
CONFIGS = {
  "A": dict(trendLen=50, sStar=0.89, minConv=0.5, asGamma=0.0141, asK=0.212, asHorizon=50, slMult=3.0,
            cycleMode="Block BUY in boom zone", cyclePeriod=2000, gapThr=20.0,
            stressMode="Block BUY in stress", stressThr=1.0),
  "B": dict(trendLen=20, sStar=0.89, minConv=0.0, asGamma=0.05, asK=0.212, asHorizon=500, slMult=1.5,
            cycleMode="Block BUY in boom, SELL in bust", cyclePeriod=300, gapThr=8.0,
            stressMode="Block BUY and SELL in stress", stressThr=1.0),
  "C": dict(trendLen=100, sStar=0.5, minConv=0.8, asGamma=0.0141, asK=0.1, asHorizon=100, slMult=2.0,
            cycleMode="Off", cyclePeriod=2000, gapThr=20.0, stressMode="Off", stressThr=1.0),
}
SUBS = [  # (regex matching the input call's default, key, kind)
  (r'(input\.int\()50(, "Trend horizon n)', "trendLen"),
  (r'(input\.float\()0\.89(, "Saturation)', "sStar"),
  (r'(input\.float\()0\.5(, "Minimum conviction)', "minConv"),
  (r'(input\.float\()0\.0141(, "Risk aversion)', "asGamma"),
  (r'(input\.float\()0\.212(, "Order-arrival)', "asK"),
  (r'(input\.int\()50(, "Horizon T)', "asHorizon"),
  (r'(input\.float\()3\.0(, "Stop distance)', "slMult"),
  (r'(input\.string\()CYCLE_BUY(, "Mode")', "cycleMode"),
  (r'(input\.int\()2000(, "Trend cut-off)', "cyclePeriod"),
  (r'(input\.float\()20\.0(, "Boom-zone gap)', "gapThr"),
  (r'(input\.string\()STRESS_BUY(, "Mode")', "stressMode"),
  (r'(input\.float\()1\.0(, "Stress threshold)', "stressThr"),
]
for name, cfg in CONFIGS.items():
    s = SRC
    for pat, key in SUBS:
        val = cfg[key]
        rep = json.dumps(val) if isinstance(val, str) else repr(val)
        s, cnt = re.subn(pat, lambda m: m.group(1) + rep + m.group(2), s)
        assert cnt == 1, (name, key, cnt)
    line = [l for l in s.splitlines() if 'request.security(' in l]
    assert len(line) == 1
    s = s.replace(line[0], 'float  stressVal = bar_index % 500 >= 400 ? 2.0 : 0.0')
    s = s.replace('syminfo.ticker', '"TEST"')  # PineTS has no syminfo for raw candles
    s += '\nplot(gapPct, "dbg_gap")\nplot(conv, "dbg_conv")\nplot(sumR, "dbg_sumR")\nplot(nTrades, "dbg_nTrades")\nplot(nTP, "dbg_nTP")\nplot(nSL, "dbg_nSL")\nplot(nExit, "dbg_nExit")\n'
    open(f"test_{name}.pine", "w").write(s)
    N = len(json.load(open("candles.json")))
    cfg = dict(cfg, stress=[2.0 if i % 500 >= 400 else 0.0 for i in range(N)])
    json.dump(cfg, open(f"cfg_{name}.json", "w"))
    print("built", name)
