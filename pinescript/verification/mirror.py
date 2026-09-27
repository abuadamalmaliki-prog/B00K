"""Line-by-line Python mirror of research_trend_signals.pine (TradingView semantics).

Usage: python3 mirror.py candles.json config.json out.json [--pinets-compat]
config keys mirror the Pine inputs; 'stress' is a list (per bar) replacing
request.security output (the Pine test copy uses the same synthetic formula).

Default: TradingView semantics (full float64; ta.rma seeded with ta.sma, which
is na while its window holds an na). --pinets-compat reproduces two PineTS
runtime details instead, so its output can be compared exactly: its ta.rma
reads na as 0 (seeding one bar earlier), and it rounds stored values to 10
decimals.
"""
import json
import math
import sys

NA = None


def isna(x):
    return x is None or (isinstance(x, float) and math.isnan(x))


COMPAT = "--pinets-compat" in sys.argv


def r10(v):
    return v if isna(v) or not COMPAT else round(v * 1e10) / 1e10


def rma(src, n):
    if COMPAT:
        return rma_pinets(src, n)
    return rma_tv(src, n)


def rma_pinets(src, n):
    out, prev, cnt, acc = [], NA, 0, 0.0
    for x in src:
        x = 0.0 if isna(x) else x
        if cnt < n:
            acc += x
            cnt += 1
            out.append(r10(acc / n) if cnt == n else NA)
            prev = acc / n if cnt == n else NA
            continue
        prev = x / n + prev * (1 - 1 / n)
        out.append(r10(prev))
    return out


def rma_tv(src, n):
    # TradingView ta.rma: seed with ta.sma (na if any na in window), then alpha = 1/n
    out, prev = [], NA
    for i in range(len(src)):
        if isna(prev):
            w = src[max(0, i - n + 1): i + 1]
            prev = sum(w) / n if len(w) == n and not any(isna(x) for x in w) else NA
        else:
            prev = NA if isna(src[i]) else prev + (src[i] - prev) / n
        out.append(prev)
    return out


def tanh_safe(x):
    if isna(x):
        return NA
    e = math.exp(-2.0 * abs(x))
    sgn = 1.0 if x > 0 else (-1.0 if x < 0 else 0.0)
    return sgn * (1.0 - e) / (1.0 + e)


def gt(a, b):
    return not isna(a) and not isna(b) and a > b


def run(c, cfg):
    O = [x["open"] for x in c]; H = [x["high"] for x in c]
    L = [x["low"] for x in c]; C = [x["close"] for x in c]
    N = len(C)
    n = cfg["trendLen"]
    dp = [NA] + [C[i] - C[i - 1] for i in range(1, N)]
    ema = rma(C, n)
    sig_abs = rma([NA if isna(x) else abs(x) for x in dp], n)
    sig_rms_sq = rma([NA if isna(x) else x * x for x in dp], n)
    sig_rms = [NA if isna(v) else math.sqrt(v) for v in sig_rms_sq]
    ref = [NA] + ema[:-1]
    s_sig = [((C[i] - ref[i]) / sig_abs[i]) if gt(sig_abs[i], 0) and not isna(ref[i]) else NA for i in range(N)]
    conv = [NA if isna(s) else tanh_safe(s / cfg["sStar"]) for s in s_sig]

    g, k, hz = cfg["asGamma"], cfg["asK"], cfg["asHorizon"]
    as_raw = (1.0 / g) * math.log(1.0 + g / k) - g * hz / 2.0
    as_units = max(as_raw, 0.5)

    P = cfg["cyclePeriod"]
    lam = 1.0 / (16.0 * math.sin(math.pi / P) ** 4)
    hx1 = hx2 = NA
    gap = []
    for i in range(N):
        y = math.log(C[i]) if C[i] > 0 else NA
        if isna(y):  # Pine: state turns na and the filter restarts on the next bar
            hx1 = NA
            gap.append(NA)
            continue
        if isna(hx1):
            hx1, hx2, p11, p12, p22 = y, y, 1.0e5, 0.0, 1.0e5
        S = p11 + 1.0
        k1 = (2.0 * p11 - p12) / S
        k2 = p11 / S
        v = y - hx1
        A = 2.0 - k1
        B = 1.0 - k2
        nx1 = 2.0 * hx1 - hx2 + k1 * v
        nx2 = hx1 + k2 * v
        n11 = A * A * p11 - 2.0 * A * p12 + p22 + 1.0 / lam + k1 * k1
        n12 = B * (A * p11 - p12) + k1 * k2
        n22 = B * B * p11 + k2 * k2
        hx1, hx2, p11, p12, p22 = r10(nx1), r10(nx2), r10(n11), r10(n12), r10(n22)
        gap.append(100.0 * (y - hx2))
    warm = int(math.floor(P / 4.0 + 0.5))  # math.round

    pos, entry, tp, sl, risk, eb = 0, NA, NA, NA, NA, NA
    ev = []
    stats = dict(nTrades=0, nTP=0, nSL=0, nExit=0, sumR=0.0)
    plots = {k: [] for k in ("Entry", "TP", "SL", "BUY", "SELL", "TP hit", "SL hit",
                             "Signal exit", "BUY removed", "SELL removed", "gap", "conv")}
    for i in range(N):
        raw_buy = i > 0 and gt(conv[i], cfg["minConv"]) and not isna(conv[i - 1]) and conv[i - 1] <= cfg["minConv"]
        raw_sell = i > 0 and not isna(conv[i]) and conv[i] < -cfg["minConv"] and not isna(conv[i - 1]) and conv[i - 1] >= -cfg["minConv"]
        gap_ready = i >= warm
        boom = gap_ready and not isna(gap[i]) and gap[i] >= cfg["gapThr"]
        bust = gap_ready and not isna(gap[i]) and gap[i] <= -cfg["gapThr"]
        sv = cfg["stress"][i]
        in_stress = not isna(sv) and sv > cfg["stressThr"]
        block_buy = (cfg["cycleMode"] != "Off" and boom) or (cfg["stressMode"] != "Off" and in_stress)
        block_sell = (cfg["cycleMode"] == "Block BUY in boom, SELL in bust" and bust) or \
                     (cfg["stressMode"] == "Block BUY and SELL in stress" and in_stress)
        e_buy = e_sell = e_tp = e_sl = e_exit = e_bb = e_bs = False
        exit_px = NA
        if pos != 0 and i > eb:
            hit_sl = L[i] <= sl if pos == 1 else H[i] >= sl
            hit_tp = H[i] >= tp if pos == 1 else L[i] <= tp
            if hit_sl:
                exit_px = min(O[i], sl) if pos == 1 else max(O[i], sl); e_sl = True
            elif hit_tp:
                exit_px = max(O[i], tp) if pos == 1 else min(O[i], tp); e_tp = True
        if pos != 0 and not e_sl and not e_tp and ((pos == 1 and raw_sell) or (pos == -1 and raw_buy)):
            exit_px = C[i]; e_exit = True
        if e_sl or e_tp or e_exit:
            stats["sumR"] += (exit_px - entry) * pos / risk
            stats["nSL"] += e_sl; stats["nTP"] += e_tp; stats["nExit"] += e_exit
            pos = 0
        if pos == 0 and gt(sig_rms[i], 0):
            if raw_buy:
                if block_buy:
                    e_bb = True
                else:
                    pos = 1; e_buy = True
            elif raw_sell:
                if block_sell:
                    e_bs = True
                else:
                    pos = -1; e_sell = True
            if e_buy or e_sell:
                entry = C[i]; eb = i; risk = cfg["slMult"] * sig_abs[i]
                sl = C[i] - pos * risk; tp = C[i] + pos * as_units * sig_rms[i]
                stats["nTrades"] += 1
        plots["Entry"].append(entry if pos != 0 else NA)
        plots["TP"].append(tp if pos != 0 else NA)
        plots["SL"].append(sl if pos != 0 else NA)
        plots["BUY"].append(e_buy); plots["SELL"].append(e_sell)
        plots["TP hit"].append(exit_px if e_tp else NA)
        plots["SL hit"].append(exit_px if e_sl else NA)
        plots["Signal exit"].append(exit_px if e_exit else NA)
        plots["BUY removed"].append(e_bb); plots["SELL removed"].append(e_bs)
        plots["gap"].append(gap[i]); plots["conv"].append(conv[i])
    return plots, stats


if __name__ == "__main__":
    candles = json.load(open(sys.argv[1]))
    cfg = json.load(open(sys.argv[2]))
    plots, stats = run(candles, cfg)
    json.dump({"plots": plots, "stats": stats}, open(sys.argv[3], "w"))
    print(json.dumps(stats))
