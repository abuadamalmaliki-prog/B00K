# 🎯 Falcon Sniper V3

Liquidity-sweep sniper entries **held for a 300-pip target**, with lot sizing, a **$30 → $500 challenge planner**, and a live check of **which timeframe fits 300 pips on the chart you're viewing**.

File: [`falcon_sniper_v3.pine`](falcon_sniper_v3.pine). Research that backs every number here: [`research/`](research).

---

## 1. Straight answers first

### "Combine 3,000 techniques"
There aren't 3,000 independent trading techniques. There are a few dozen, and nearly all of them are rearrangements of the same price and volume data. V3 uses about 20: liquidity sweeps, BOS/CHoCH, FVG, order blocks, premium/discount, OTE, kill zones, pin bars, MSS, engulfing, HTF bias, EMA trend, RSI, MACD, volume, displacement, ATR and more. It **tested each one on real data**. Stacking more of them made results **worse**: setups with 8+ of 13 confluences averaged −0.09R per trade versus up to +0.23R for mid-scoring ones, in both halves of the data. Adding techniques that have no edge only removes good trades. So V3 uses the few that tested best as gates and shows the rest as information.

### "$30 → $500 in 3 trades"
That's a **16.7× return in 3 trades**. I worked out the best possible plan exactly:

| | Result |
|---|---|
| **Mathematical ceiling** for any strategy without a proven edge | **6%** (= $30 ÷ $500) |
| Best sizing, solved exactly (dynamic programming, real 0.01 lot steps and margin) | **3.2–6.0%**, depending on instrument and leverage |
| Historical replay of the plan on EURUSD H4, 1:1000 leverage | **6.0%** reached $500 · **62%** busted |
| Same at 1:500 leverage | 3.6% reached $500 · 46% busted |

**About 1 attempt in 20 succeeds. More than half the time the $30 is essentially gone.** No indicator changes that. The limit comes from the arithmetic, not from the chart. It's a demo account, so trying costs nothing real, and V3 gives you the best plan the numbers allow (section 7). **Never run this plan with real money.**

### "Target 300 pips"
Done. By default the whole position is held for +300 pips, with the stop moved to breakeven at +150. On H4, **13–15% of trades reached the full 300 pips**, up from 1–3% under V2 (section 4).

---

## 2. Reverse engineering: what do 300-pip winners look like at entry?

I traced the price path after **6,423 setups** (11 instruments, H1 + H4, 2 years) and recorded whether each reached +300 pips before its stop.

| Question | Answer (first half → second half of the data) |
|---|---|
| How often does price reach +300 before the sweep stop? | **11.6%** of setups overall |
| H4 vs H1 | H4 **13.0% → 12.8%** vs H1 10.3% → 10.3%, **consistent** |
| Deep OTE retracement vs shallow pullback | Shallow 14.0% → 14.2% vs OTE 10.9% → 10.8%. It looked robust, but **failed validation** on unseen instruments (−0.11R). Rejected. |
| With HTF trend / EMA trend / structure | **Flipped sign** between halves → noise. Not used as filters. |
| High confluence score (8+ of 13) | Worse in **both** halves → the score is information only |
| 300 pips vs the instrument's daily range | The closer 300 pips is to one day's range, the more often it's reached (14% vs 8–9%) |

## 3. Forward engineering: does it hold up on data it never saw?

Every rule was checked on **6 instruments V2 never saw** (NZDUSD, USDCAD, GBPAUD, EURJPY, GBPJPY, XAGUSD), in two separate time halves.

| Version | Seen instruments (H4) | **Unseen instruments (H4)** | H1 (unseen) |
|---|---|---|---|
| V2 rules | PF 1.12 → 1.29 | **PF 0.96 → 1.07** (break-even) | PF 0.97 → 0.94 |
| **V3 rules** | PF 1.10 → 1.61 | **PF 1.10 → 0.96** | PF 0.99 → 0.80 |

What this means:
- **V2's edge was partly luck of the sample**, and it faded on unseen instruments. I'm stating that openly rather than hiding it.
- V3 is positive in 3 of 4 H4 cells, but the edge is **small and statistically unproven** (roughly ±0.14R of noise per cell). Treat it as roughly break-even with a small positive lean.
- **H1 isn't recommended.** V3 is an **H4 tool** for majors.

## 4. Debug report: bugs found in V2 and fixed in V3

| # | Bug | Evidence | V3 fix |
|---|---|---|---|
| 1 | **Opposite signals closed trades early** | **45–54%** of all trades ended this way, so only 0.7–3.3% ever reached 300 pips | Off by default (option *Opposite signal closes the trade*). 300-pip hit rate is now **13–15%** on H4. |
| 2 | **Breakeven at +50 choked runners** | Moving to breakeven early cut 300-pip reach from 11.3% to 6.5% (EURUSD H4) | Default: full position to TP3, breakeven at **+150**. It beat no protection in all 4 validation cells and was the best rule overall. |
| 3 | **Fixed 100-pip stop cap went stale** | Gold tripled in volatility. H4 stops now average 613 pips, so V2 printed **zero gold signals since July 2025**, silently. | New **Stop fit** row: shows the typical stop on your chart and tells you to change timeframe when it doesn't fit |
| 4 | No position sizing | You had to calculate lots yourself | **Money panel**: lots, $ risk, $ win, from balance, pip value (auto currency conversion) and margin |
| 5 | V2's research used broken daily data | Yahoo daily FX bars are 92% doji (open ≈ close) | Only clean H1 data used; H4 and D rebuilt from it |

## 5. Decisions (you asked me to decide everything)

| Decision | Choice | Why |
|---|---|---|
| Chart timeframe | **H4** | Best 300-pip reach, positive in 3/4 validation cells. H1 was negative out of sample. |
| Instrument for the $30 challenge | **EURUSD** (backup: USDJPY) | Stop ≈ 30–38 pips, so 300 pips pays about 8–10× the risk. Tightest spread. Best historical replay (6.0% at 1:1000). |
| Exit | **All-in to +300**, stop to breakeven at +150 | Highest 300-pip reach with protection |
| Opposite signals | **Ignored while a trade is open** | Bug #1 |
| Leverage (demo) | **1:1000** | At 1:500, margin limits cut the best odds from 4.5% to 3.2% on EURUSD |
| Sizing | **Challenge (optimal)**, the launch-pad rule | Matches the exact optimum in all 14 tested instrument/leverage cases |
| Confluence score, HTF filter | **Information only** | Tested flat or negative as filters |

---

## 6. Timeframe masterclass: which chart for 300 pips *today*

A 300-pip target only works as a sniper trade if the stop behind the sweep is small compared with 300 pips (V3 requires ≤ 100 pips, i.e. at least 3:1). Median sweep stop over the last 12 months:

| Instrument | Daily range | H4 stop | H1 stop | M15 stop | **Use for 300 pips** |
|---|---|---|---|---|---|
| EURUSD | 54p | **30p** ✓ | 24p ✓ | 12p | **H4** (300p ≈ 5–6 days) |
| GBPUSD | 71p | **45p** ✓ | 32p ✓ | 15p | **H4** |
| AUDUSD | 47p | 36p ✓ | 18p ✓ | 10p | H4 (300p ≈ 6 days, rarely reached) |
| NZDUSD | 43p | 30p ✓ | 20p ✓ | — | H4 (rarely reached) |
| USDCAD | 56p | 39p ✓ | 24p ✓ | — | **H4** |
| USDJPY | 94p | **71p** ✓ | 37p ✓ | 17p | **H4** (300p ≈ 3 days) |
| EURJPY | 96p | 70p ✓ | 40p ✓ | — | H4 |
| GBPJPY | 123p | 92p ≈ | 47p ✓ | — | H4 (borderline) or H1 |
| GBPAUD | 105p | 97p ≈ | 39p ✓ | — | H4 (borderline) or H1 |
| XAGUSD | 373p | 215p ✗ | 100p ≈ | — | M15 (untested) |
| **XAUUSD** | 1,052p | **613p ✗** | **311p ✗** | 137p ✗ | **None: 300 pips is too small for today's gold swings.** Lower the stop cap or pick a different target. |

**The rule behind the table:** choose the timeframe where the typical sniper stop is **10–33%** of the target. Volatility changes, so V3 checks this **live**. Watch the **Stop fit** row: ✓ means this chart works for your target, and *✗ too wide → lower TF* means switch down.

**Top-down routine (unchanged from V2):** Weekly/Daily for bias and obvious liquidity, **H4 for signals**, and the kill zones for timing. In Malaysia time, London is 15:00–18:00 (Nov–Mar) or 14:00–17:00 (Mar–Nov), and New York is 20:00–23:00 or 19:00–22:00. On H4 the kill-zone filter switches off automatically.

---

## 7. The $30 → $500 playbook (demo only)

**Setup**
1. Open a demo account with **$30** and **1:1000** leverage. Chart **EURUSD H4** and add Falcon Sniper V3.
2. Settings → ⑦ Money & challenge: Balance **30**, sizing **Challenge (optimal)**, goal **500** in **3** trades, leverage **1000**.
3. Check the dashboard. **Stop fit** should read ✓, and **Pip · value per lot** should read `0.0001 · $10.00`.
4. Create an alert: *Any alert() function call*, frequency *Once Per Bar Close*. Each signal alert includes the **exact lot size**.

**Each trade**
- Enter at the signal bar's close with the lots shown. Stop and TP3 exactly as drawn. At +150 pips, move the stop to entry.
- After the trade closes, **update the balance** and lower **trades** by 1. The lot size for the next trade depends on this.

**What the plan does (EURUSD, typical 38-pip stop, 1:1000):**

| Path | Trade 1 | Trade 2 | Trade 3 | End |
|---|---|---|---|---|
| Win, Win | $30 → **0.04 lots** (risk $15.20) → **$150** | 0.12 lots (risk $45.60) → **$510** ✅ | — | **$510** |
| Win, Loss, Win | → $150 | → $104.40 | 0.14 lots (risk $53.20) → **$524** ✅ | $524 |
| Loss, Win, Win | → $14.80 | 0.03 lots → $104.80 | 0.14 lots → **$525** ✅ | $525 |
| Win, Loss, Loss | → $150 | → $104.40 | → $51.20 | ❌ |
| Loss, Loss | → $14.80 | → $3.40 | — | ❌ bust |

Each trade reaches +300 about **13%** of the time. Every ✅ row needs at least two 300-pip wins, and that's why the overall odds come to about **5%**. The dashboard's **Goal row** replays this exact plan over the chart's own history, and the **Zero-edge ceiling** row shows the 6% limit.

**If you want the account to survive instead:** switch sizing to **Fixed risk %** at 1–2%. $30 won't become $500 in 3 trades that way, and no honest method does that reliably.

---

## 8. Install · dashboard · alerts

**Install:** TradingView → Pine Editor → paste `falcon_sniper_v3.pine` → Save → Add to chart. (Not compiled in TradingView by me. If it reports an error, send it to me.)

| Dashboard row | Meaning |
|---|---|
| Liquidity · Kill zone · Structure · Price zone · HTF bias · Confluence | Market context (as in V2) |
| **Stop fit (TF)** | Typical stop of the last 30 setups. ✓ = this timeframe suits the target. |
| **Pip · value per lot** | Pip size and $ per pip for 1.00 lot (auto-converted to USD) |
| **Balance · sizing** · **Lots · risk** · **Win at target** | Exact lots, $ at risk and $ gained if TP3 hits, for the live trade (or a typical setup when flat) |
| **Goal $500 in 3** | Historical replay of your challenge plan on this chart: success % and bust % |
| **Zero-edge ceiling** | Balance ÷ goal: the best odds possible without a real edge |
| Position · Stop · Open P&L · Scorecard | Live trade and closed-trade statistics |

**Alerts:** *Any alert() function call* sends the plan with lot size, e.g.
`SNIPER BUY (Pin bar, 7/13) | Entry … | SL … (-38.0p) | TP1 … | TP2 … | TP3 … | Lots 0.04 risk $15.20`, plus breakeven, stop and TP3 events.

## 9. Honest limitations

- Results are from about 2 years of data, **before spread, commission and slippage**. On a 38-pip stop, a 1-pip spread costs about 0.03R per trade, which is a large share of the small measured edge.
- The measured edge is small and not statistically proven. The challenge odds are close to the no-edge ceiling, and they'd be about the same with a coin-flip entry.
- Pip value and margin use the **current** price. Contract sizes vary by broker, so check yours (auto: forex 100,000, gold 100 oz, silver 5,000 oz).
- This is a decision-support tool, not financial advice. Risking a large fraction of a real account per trade is how accounts are lost.
