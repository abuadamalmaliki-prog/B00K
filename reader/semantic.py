#!/usr/bin/env python3
"""Read the whole book locally, let Claude read ~1% of it.

Every unit of the book (sentence / verse, from units.tsv) is embedded once
with a multilingual embedding model that runs on this machine's CPU
(fastembed + intfloat/multilingual-e5-large). That costs no Claude tokens.
Embeddings capture meaning, so a passage can be found even when it shares no
words with the question (e.g. a prayer issue discussed inside the hajj
chapter).

For a question, three rankers vote (reciprocal-rank fusion):
  semantic  cosine similarity to several phrasings of the question
  bm25      the C++ keyword index (exact terms still matter)
  graph     neighbours of strong hits via the author's own cross-references
and units are taken in rank order until the budget (default 1% of the book's
characters) is spent. The output, in reading order, is what Claude reads.

    python semantic.py embed                       # once per book (cached)
    python semantic.py ask "سؤال" ["صيغة أخرى" ...] [--budget 0.01]
    python semantic.py eval                        # recall vs. the 50-reader ground truth
"""

from __future__ import annotations

import argparse
import re
import subprocess
from collections import defaultdict

import numpy as np

from read import BUILD, section_path, sections, units

MODEL = "intfloat/multilingual-e5-large"
EMB = BUILD / "embeddings.npy"
STRIP = re.compile(r"[ً-ْٰ]")


def _model():
    from fastembed import TextEmbedding
    return TextEmbedding(MODEL, cache_dir=str(BUILD / "models"))


def plain(text: str) -> str:
    return STRIP.sub("", text)


def embed() -> None:
    us = units()
    vecs = list(_model().embed([f"passage: {plain(u['text'])[:1500]}" for u in us], batch_size=32))
    arr = np.asarray(vecs, dtype=np.float32)
    arr /= np.linalg.norm(arr, axis=1, keepdims=True)
    np.save(EMB, arr)
    print(f"embedded {len(us)} units -> {EMB} {arr.shape}")


def _semantic(queries: list[str], emb: np.ndarray) -> np.ndarray:
    q = np.asarray(list(_model().embed([f"query: {x}" for x in queries])), dtype=np.float32)
    q /= np.linalg.norm(q, axis=1, keepdims=True)
    return (emb @ q.T).max(axis=1)          # best match over all phrasings


def _bm25(queries: list[str], n: int) -> dict[str, float]:
    scores: dict[str, float] = defaultdict(float)
    for q in queries:
        out = subprocess.run([str(BUILD / "index"), "query", str(BUILD / "units.tsv"), str(n), *q.split()],
                             capture_output=True, text=True, check=True).stdout
        for line in out.splitlines():
            uid, s = line.split("\t")
            scores[uid] = max(scores[uid], float(s))
    return scores


def select(queries: list[str], budget: float = 0.01) -> list[dict]:
    us = units()
    emb = np.load(EMB)
    total = sum(len(plain(u["text"])) for u in us)
    limit = budget * total

    sem = _semantic(queries, emb)
    sem_rank = {us[i]["id"]: r for r, i in enumerate(np.argsort(-sem))}
    bm = _bm25(queries, 2000)
    bm_rank = {uid: r for r, (uid, _) in enumerate(sorted(bm.items(), key=lambda x: -x[1]))}

    # graph: units in sections the author links (crossref) to the top semantic sections
    graph_rank: dict[str, int] = {}
    try:
        from graph import build_graph
        top_secs = []
        for i in np.argsort(-sem)[:30]:
            if us[i]["section"] not in top_secs:
                top_secs.append(us[i]["section"])
        linked = set()
        for (a, b), es in build_graph().items():
            if any(k == "crossref" for k, *_ in es):
                if a in top_secs[:10]:
                    linked.add(b)
                if b in top_secs[:10]:
                    linked.add(a)
        cand = [i for i, u in enumerate(us) if u["section"] in linked]
        cand.sort(key=lambda i: -sem[i])
        graph_rank = {us[i]["id"]: r for r, i in enumerate(cand)}
    except Exception:
        pass

    k = 60  # reciprocal-rank fusion constant
    fused: dict[str, float] = defaultdict(float)
    for ranks, w in ((sem_rank, 1.0), (bm_rank, 0.7), (graph_rank, 0.4)):
        for uid, r in ranks.items():
            fused[uid] += w / (k + r)

    by_id = {u["id"]: u for u in us}
    chosen, used = [], 0
    for uid, _ in sorted(fused.items(), key=lambda x: -x[1]):
        u = by_id[uid]
        if u["kind"] == "heading":
            continue
        n = len(plain(u["text"]))
        if used + n > limit:
            continue
        chosen.append(u)
        used += n
        if used >= limit * 0.98:
            break
    chosen.sort(key=lambda u: int(u["id"]))
    return chosen


def ask(queries: list[str], budget: float) -> None:
    chosen = select(queries, budget)
    secs = sections()
    chars = sum(len(plain(u["text"])) for u in chosen)
    print(f"{len(chosen)} units, {chars} chars (budget {budget:.1%} of the book)\n")
    last = None
    for u in chosen:
        if u["section"] != last:
            last = u["section"]
            print(f"\n## {section_path(secs, u['section'])}")
        print(f"[ج{u['vol']} ص{u['page']}] {plain(u['text'])}")


# Pages the 50 readers found decisive on tafwid vs ithbat (vol. 1),
# both the ithbat proofs and the tafwid-worded passages and definitions.
GROUND_TRUTH = {25, 97, 107, 113, 116, 117, 128, 194, 211, 214, 215, 219, 241, 243, 247, 261, 265, 266}
EVAL_QUERIES = [
    "هل يفوض السفاريني معنى الصفات أم يثبت المعنى ويفوض الكيفية",
    "تفويض المعنى وإثبات المعنى في آيات الصفات عند السلف",
    "الكيف مجهول والمعنى معلوم وأهل التجهيل",
]


def evaluate() -> None:
    us = units()
    for budget in (0.005, 0.01, 0.02, 0.05):
        chosen = select(EVAL_QUERIES, budget)
        pages = {int(u["page"]) for u in chosen if u["vol"] == "1"}
        hit = sorted(GROUND_TRUTH & pages)
        print(f"budget {budget:>5.1%}: {len(chosen):4d} units, recall {len(hit)}/{len(GROUND_TRUTH)} "
              f"missed {sorted(GROUND_TRUTH - pages)}")
    # baseline: BM25 alone at 1%
    bm = _bm25(EVAL_QUERIES, 2000)
    total = sum(len(plain(u["text"])) for u in us)
    by_id = {u["id"]: u for u in us}
    used, pages = 0, set()
    for uid, _ in sorted(bm.items(), key=lambda x: -x[1]):
        n = len(plain(by_id[uid]["text"]))
        if used + n > 0.01 * total:
            break
        used += n
        if by_id[uid]["vol"] == "1":
            pages.add(int(by_id[uid]["page"]))
    print(f"BM25 only @1%: recall {len(GROUND_TRUTH & pages)}/{len(GROUND_TRUTH)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("embed")
    a = sub.add_parser("ask")
    a.add_argument("queries", nargs="+")
    a.add_argument("--budget", type=float, default=0.01)
    sub.add_parser("eval")
    args = ap.parse_args()
    if args.cmd == "embed":
        embed()
    elif args.cmd == "ask":
        ask(args.queries, args.budget)
    else:
        evaluate()


if __name__ == "__main__":
    main()
