# 🎯 Falcon Sniper V7: TradingView for analysis, MT5 for execution

Built for your setup: you **analyse on TradingView** and **trade on MetaTrader 5** with a **JustMarkets Standard account at 1:3000**.

| Part | File | Job |
|---|---|---|
| **MT5 Expert Advisor** | [`mt5/FalconSniperV7.mq5`](mt5/FalconSniperV7.mq5) | Runs on your broker's own prices. Finds setups, sizes lots from your real balance and your broker's contract specs, places orders (one click or auto), and moves the stop to breakeven. |
| TradingView indicator | [`falcon_sniper_v7.pine`](falcon_sniper_v7.pine) | Chart analysis, zones and structure, a scorecard with costs included, and alerts with an MT5 ticket |
| Research | [`research/`](research) | Reproduces every number below and proves the EA matches it |

---

## 1. Straight answers

**3,000 techniques.** There aren't 3,000 independent techniques; nearly all indicators re-read the same price and volume. V7 tested the ones that matter: about 20 techniques inside the sweep engine, plus **6 separate strategy families**, one of them a **random-entry control**. Only one family beat random entries, and costs erase its edge (section 3). Stacking more techniques made results worse in every version.

**$30 → $500 in 3 trades (demo).** That needs 16.7× in 3 trades.

| Measure | Result |
|---|---|
| Ceiling for any strategy without a proven edge | **6%** (= 30 ÷ 500) |
| Exact optimal sizing, USDJPY H4, costs included | **3.3–5.0%** (the EA plans each win as 280 pips instead of 300, to be safe) |
| Historical replay of V7's exact plan, USDJPY H4 | **4.4%** reached $500 · **67%** ended below $5 |

About 1 attempt in 25 succeeds, and in two out of three the demo account is wiped. The EA sizes for the best odds that exist. **Never do this with real money.**

**300 pips.** Held all-in to +300, with the stop moved to breakeven at +150. On H4, **13.6%** of trades reach the full 300.

---

## 2. What V7 does differently: 13 things I worked out on my own

| # | What | Why it matters |
|---|---|---|
| 1 | **Real MQL5 compiler.** I installed MetaTrader 5 and MetaEditor in the sandbox. | The EA compiles with **0 errors, 0 warnings**. It isn't just hand-checked. |
| 2 | **The EA runs natively in MT5.** | TradingView's feed isn't JustMarkets' feed, so sweeps and stops can differ by pips. The EA sees exactly what your broker fills. |
| 3 | **Broker-exact money** | Lot size uses your broker's tick value, contract size, lot step, `OrderCalcMargin` and actual stop-out level. Nothing is guessed. |
| 4 | **Costs in every number** | Longs fill at the ask, shorts are stopped on the ask, and swap is charged every rollover (Wednesday ×3). V3 ignored all of this. |
| 5 | **Swap is the biggest cost** | A 300-pip hold lasts a median of 36–40 hours, often days. The EA reads your real long and short swap. |
| 6 | **Strategy bake-off with a random control** | Only the sweep setup beat random entries: it **beat all 50 random runs**. |
| 7 | **Weekend test** | Closing before the weekend drops 300-pip hits from 13.6% to 1.8%. **So V7 doesn't.** |
| 8 | **Leverage-cut protection** | Brokers often cut leverage around news, weekends or at higher balances. Sizing assumes **×3 margin** (1:3000 behaves like 1:1000). For USDJPY the odds are identical, and a cut can't stop you out first. |
| 9 | **Exact dynamic-programming sizing in the EA** | The EA picks the lot size that maximises P(goal) for your balance and trades left. TradingView uses a rule within 3% of that optimum. |
| 10 | **Bug found in V3: the winning path fell short of the goal** | V3 sized on a gross 300-pip win. After costs, EURUSD's win-win path ended at **$486** ($30 → 0.04 lots → $144 → 0.12 lots → $486) and the plan never reached $500. V7 plans wins **net of 20 pips**. |
| 11 | **News filter from the MT5 economic calendar** | The EA blocks entries 30 minutes either side of high-impact events for the pair's currencies. |
| 12 | **Parity proofs** | EA engine vs research: **11,488 / 11,488** setups identical. EA trade replay: **5,921 / 5,921** identical. Pine swap counter: **230,190 / 230,190** identical. |
| 13 | **Two more bugs fixed before release** | My first V7 swap counter missed a night over US holiday long weekends (fixed and re-verified on 230,190 bar pairs). And bars where long and short both qualified were decided differently in each codebase; now all three skip them. |

The EA also keeps a CSV journal, can send push notifications to your phone, and has a one-click **EXECUTE** button.

---

## 3. Research results (2 years, 11 instruments, net of spread and swap)

**Strategy bake-off, H4** (avg R per trade ± standard error):

| Family | Avg R | Verdict |
|---|---|---|
| **A. Sweep reversal (V7)** | **+0.000 ± 0.081** | Break-even. Beats random by about 0.15R, but costs eat it. |
| C. Donchian 55/10 breakout | −0.256 ± 0.109 | ✗ |
| D. Daily-trend pullback | −0.143 ± 0.094 | ✗ |
| E. NR7 breakout | −0.094 ± 0.073 | ✗ |
| F. **Random entries** (50 runs) | median **−0.152** (5–95%: −0.289 … −0.036) | The cost of trading with no edge |

On H1 everything loses after costs (sweep −0.157R, London breakout −0.105R). **So V7 is an H4 tool.**

**Cost levers, H4 sweep:**

| Scenario | Avg R | 300-pip hits |
|---|---|---|
| No costs | +0.110 | 13.8% |
| **Swap-free** (spread only) | **+0.069** | 13.6% |
| Standard account (spread + 0.5 pip/night swap) | +0.000 | 13.6% |
| Double spread | −0.014 | 13.4% |
| Swap 1.5 pip/night | −0.136 | 13.6% |
| Close before weekend | −0.081 | **1.8%** |
| No breakeven | −0.029 | 15.6% |

**The lesson: swap decides whether this is profitable.** Check your MT5 swap values (section 6). If your broker offers a swap-free option you qualify for, it's the single biggest improvement available.

**Challenge odds by instrument** (V7 sizing, 1:3000 with ×3 safety):

| | USDJPY | USDCAD | NZDUSD | AUDUSD | GBPUSD | GBPJPY | EURJPY | EURUSD | GBPAUD |
|---|---|---|---|---|---|---|---|---|---|
| Replay: reached $500 | **4.4%** | 3.2% | 3.1% | 2.6% | 1.8% | 1.6% | 1.5% | 1.3% | 0.7% |
| Exact model | 5.0% | 4.3% | 1.0% | 3.5% | 3.4% | 2.5% | 3.1% | 5.2% | 2.3% |

Gold replayed at 15%, but that's only 20 windows from 2024. Today gold's H4 stops average about 600 pips, so a 300-pip sniper trade doesn't fit.

---

## 4. Decision: the $30 → $500 plan

| | Choice |
|---|---|
| Instrument · chart | **USDJPY · H4** (best replay, highest 300-pip rate among majors, about 3 days of range) |
| Execution | **MT5 EA**, mode *Signals + EXECUTE button* (or *Auto*) |
| Sizing | *Challenge*: goal 500, trades 3 |
| Exit | All-in to +300, breakeven at +150, no weekend closing, opposite signals ignored |

**What the EA will size** (typical 57-pip stop, current USDJPY price):

| Path | Trade 1 | Trade 2 | Trade 3 | Result |
|---|---|---|---|---|
| Win, Win | $30 → **0.04 lots**, risk $14.36 → **$104.98** | **0.23 lots**, risk $82.58 → **$536** | | ✅ |
| Win, Breakeven, Win | → $104.98 | → ~$98 (swap) | 0.23 lots → **$529** | ✅ |
| Breakeven, Win, Win | → ~$29 | 0.04 lots → $104 | 0.23 lots → **$535** | ✅ |
| Win, Loss, … | → $104.98 | → $22.39 | goal no longer reachable | ❌ |
| Loss, … | → $15.64 | goal no longer reachable | | ❌ |

It takes **two 300-pip wins without a loss in between**, and each trade reaches 300 only about 16% of the time. If the goal becomes mathematically unreachable, the EA panel shows **P(goal) 0.0%** and it falls back to the minimum lot.

---

## 5. Install

### MT5 Expert Advisor (execution)
1. In MT5: **File → Open Data Folder → MQL5 → Experts**. Copy `FalconSniperV7.mq5` there. (Or copy the ready-compiled `FalconSniperV7.ex5`, built with MT5 build 6182, and skip step 2.)
2. Press **F4** (MetaEditor), open the file and press **F7** to compile. It should say **0 errors, 0 warnings**.
3. Back in MT5, open a **USDJPY H4** chart. Drag *Falcon Sniper V7* from **Navigator → Expert Advisors** onto it.
4. In the dialog, tick **Allow Algo Trading**, then set the inputs: *Challenge goal* 500, *trades* 3, *Mode* (button or auto).
5. Switch on the **Algo Trading** button in the MT5 toolbar.
6. Optional phone alerts: install MT5 mobile, copy your **MetaQuotes ID** into MT5 → **Tools → Options → Notifications**, and set *Push notifications* = true.

The panel (top-left) shows pip value, spread, **your real swap**, leverage, the **2-year replay on your broker's data**, challenge status, and the live signal with lots. Historical signals appear as arrows: green hit the target, grey hit breakeven, red hit the stop. Hover an arrow for details.

### TradingView indicator (analysis)
Pine Editor → paste `falcon_sniper_v7.pine` → Save → Add to chart. In **⑦ Money & challenge**, set your **spread** and **swap** from MT5 (section 6). The alerts include an MT5 ticket, e.g. `MT5: BUY 0.04 lots, SL 57.2p from entry, TP 300p, risk $14.36`. Enter SL and TP as **distances**, because TradingView prices differ slightly from your broker's.

(Pine was checked with an offline parser, not TradingView's compiler. If TradingView shows an error, send it to me.)

---

## 6. Check these at JustMarkets (the EA reads most of them for you)

| Item | Where in MT5 | Used by |
|---|---|---|
| Symbol name (may have a suffix, e.g. `USDJPY.m`) | Market Watch | Put the EA on that exact symbol |
| Spread | Market Watch → right-click → Spread | EA reads it live. For Pine, enter it by hand (points ÷ 10 for 3/5-digit symbols). |
| **Swap long / short, triple-swap day** | Right-click symbol → Specification | EA reads it. Pine needs it entered. **This decides profitability.** |
| Minimum lot / step, contract size | Specification | EA reads them |
| Stop-out level | Account terms | EA reads it and never assumes below 50% |
| Leverage limits around news, weekends and higher balances | JustMarkets website / support | Not readable by software. That's why the ×3 margin safety exists. |

---

## 7. Honest limitations

- **The EA hasn't run inside MT5 yet.** The sandbox has no broker connection, so it has no symbols to run on. It's verified by the real compiler plus exact parity with the research engine. **Run it on your demo first** and check the panel values against MT5's own symbol specification.
- Spread assumptions in the research (e.g. USDJPY 1.5 pips) are typical standard-account values, not measured JustMarkets values.
- Two years of data. The edge before costs is small and not statistically proven. After costs it's break-even.
- Decision support, not financial advice.
