"""Section graph: links between parts of the book that share no query words.

Lexical retrieval (BM25) finds the passages that *say* the query words, so
it misses page 120 when page 120 is the real continuation of page 100 but
uses other words. This module links the 292 sections in five ways that
don't depend on the query:

  crossref  the author's own pointers ("وقد تقدم…", "كما سيأتي…"), resolved
            to the section they most likely mean, earlier or later in the book
  quran     both sections cite the same verse
  hadith    both sections quote the same hadith «…»
  lexical   their distinctive vocabularies are similar (TF-IDF cosine)
  sequence  neighbouring sections in reading order, and parent/child

`explore` then seeds the graph with BM25 hits for the query, expanded with
words the book itself uses alongside the query terms (PPMI, in C++). It
spreads that relevance along the links with a personalised PageRank, so a
section is found because the sections that match point to it.
"""

from __future__ import annotations

import csv
import math
import re
import subprocess
from collections import Counter, defaultdict
from itertools import combinations

from read import BUILD, letters, section_path, sections, units

INDEX = str(BUILD / "index")
UNITS = str(BUILD / "units.tsv")
EDGE_WEIGHT = {"crossref": 1.0, "quran": 0.7, "hadith": 0.7, "lexical": 0.6, "sequence": 0.25}
# Only the author's referring formulas: يأتي/سبق/مر are also ordinary verbs.
BACK = (r"(?:كما|وقد|قد|ما|مما|لما) (?:تقدم|مر|سبق|ذكرنا|أسلفنا|قدمنا)"
        r"|تقدم (?:في|أن|ذكر|الكلام|بيان|هذا|ذلك|قريبا|آنفا|لك)|آنفا")
FORWARD = (r"[وف]?سيأتي|كما يأتي|سنذكر|[وف]يأتي (?:في|الكلام|ذكر|بيان|إن|قريبا|تحقيق)"
           r"|ما يأتي (?:من|في)")
XREF = re.compile(rf"(?:^|\s)({BACK}|{FORWARD})(?=\s|$|[،.:])")
HADITH = re.compile(r"«([^»]{15,})»")
STRIP = re.compile(r"[ً-ْٰ]")
MARKER_STEMS = {"قد", "وقد", "كما", "تقدم", "سبق", "مر", "ذكرنا", "سياتي", "ياتي", "انفا",
                "شاء", "قريبا", "بيان", "كلام", "ذكر"}


def _stem_lines(lines: list[str]) -> list[set[str]]:
    out = subprocess.run([INDEX, "stem"], input="\n".join(lines) + "\n",
                         capture_output=True, text=True, check=True).stdout
    return [set(l.split()) - MARKER_STEMS for l in out.split("\n")[:len(lines)]]


def _vectors() -> dict[str, dict[str, float]]:
    vecs = {}
    with open(BUILD / "section_vectors.tsv", encoding="utf-8") as f:
        for row in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            v = {k: float(w) for k, w in (c.rsplit(":", 1) for c in row[1:])}
            norm = math.sqrt(sum(w * w for w in v.values())) or 1.0
            vecs[row[0]] = {k: w / norm for k, w in v.items()}
    return vecs


def _cos(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(w * b.get(k, 0.0) for k, w in a.items())


Edge = tuple[str, float, str, tuple[str, ...]]  # kind, weight, reason, evidence unit ids


def build_graph() -> dict[tuple[str, str], list[Edge]]:
    """Undirected edges keyed (a, b) with a < b: [(kind, weight, reason, units), …]."""
    secs, us, vecs = sections(), units(), _vectors()
    order = list(secs)                       # reading order
    pos = {s: i for i, s in enumerate(order)}
    edges: dict[tuple[str, str], list[Edge]] = defaultdict(list)

    def link(a: str, b: str, kind: str, weight: float, reason: str, ev: tuple = ()) -> None:
        if a != b and a in secs and b in secs:
            edges[(a, b) if pos[a] < pos[b] else (b, a)].append((kind, weight, reason, ev))

    # sequence and hierarchy
    for a, b in zip(order, order[1:]):
        link(a, b, "sequence", 1.0, "next section")
    for s in order:
        if secs[s]["parent"] != "0":
            link(s, secs[s]["parent"], "sequence", 1.0, "parent")

    # the author's own cross-references
    cands = []
    for u in us:
        plain = STRIP.sub("", u["text"])
        for m in XREF.finditer(plain):
            words = plain.split()
            at = len(plain[:m.start()].split())
            snippet = " ".join(words[max(0, at - 8):at + 14])
            cands.append((u, bool(re.fullmatch(FORWARD, m.group(1))), snippet))
    for (u, forward, snippet), stems in zip(cands, _stem_lines([c[2] for c in cands])):
        here = u["section"]
        if here not in pos or len(stems) < 2:
            continue
        query = {s: 1.0 for s in stems}
        pool = order[pos[here] + 1:] if forward else order[:pos[here]]
        scored = [(_cos(query, vecs.get(s, {})), s) for s in pool if s != secs[here]["parent"]]
        if scored:
            score, target = max(scored)
            if score > 0.12:
                link(here, target, "crossref", min(1.0, score * 3),
                     f"{'→' if forward else '←'} ج{u['vol']} ص{u['page']}: «{snippet}»", (u["id"],))

    # shared Qur'an verses and hadith (rare shared citations count for more)
    by_unit = {u["id"]: u["section"] for u in us}
    verse_secs: dict[str, dict[str, str]] = defaultdict(dict)   # verse -> section -> unit
    with open(BUILD / "quran_checks.tsv", encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            if row["found"]:
                verse_secs[row["found"]].setdefault(by_unit[row["unit"]], row["unit"])
    hadith_secs: dict[str, dict[str, str]] = defaultdict(dict)
    hadith_text: dict[str, str] = {}
    for u in us:
        for m in HADITH.finditer(u["text"]):
            key = letters(m.group(1))[:24]
            if len(key) >= 12:
                hadith_secs[key].setdefault(u["section"], u["id"])
                hadith_text.setdefault(key, STRIP.sub("", m.group(1))[:60])
    for kind, groups, label in (("quran", verse_secs, lambda k: f"both cite {k}"),
                                ("hadith", hadith_secs, lambda k: f"both quote «{hadith_text[k]}…»")):
        for key, group in groups.items():
            if 2 <= len(group) <= 12:
                for a, b in combinations(sorted(group), 2):
                    link(a, b, kind, 1.0 / (len(group) - 1), label(key), (group[a], group[b]))

    # vocabulary similarity: each section's five nearest neighbours
    for s in order:
        sims = sorted(((_cos(vecs.get(s, {}), vecs.get(t, {})), t) for t in order if t != s),
                      reverse=True)[:5]
        for score, t in sims:
            if score > 0.15:
                link(s, t, "lexical", score, f"similar vocabulary ({score:.2f})")
    return edges


def graph_stats() -> None:
    edges = build_graph()
    kinds = Counter(k for es in edges.values() for k, _, _ in es)
    print(f"{len(edges)} linked section pairs; links by kind: {dict(kinds)}")
    with open(BUILD / "graph.tsv", "w", encoding="utf-8") as f:
        for (a, b), es in edges.items():
            for kind, w, reason, _ in es:
                f.write(f"{a}\t{b}\t{kind}\t{w:.3f}\t{reason}\n")


def _bm25(words: list[str], k: int) -> list[tuple[str, float]]:
    out = subprocess.run([INDEX, "query", UNITS, str(k), *words],
                         capture_output=True, text=True, check=True).stdout
    return [(a, float(b)) for a, b in (l.split("\t") for l in out.splitlines())]


def explore(question: str, top: int = 8, show_units: int = 2, alpha: float = 0.5) -> None:
    secs, us = sections(), units()
    by_id = {u["id"]: u for u in us}

    # 1. expand each query word with the book's own associated vocabulary,
    #    trusting specific words (high idf) more than common ones: "المؤمنين"
    #    alone would drag in "أمير المؤمنين عمر بن الخطاب".
    df = {}
    with open(BUILD / "vocab.tsv", encoding="utf-8") as f:
        for row in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            df[row[0]] = int(row[2])
    n_units = len(us)
    words = question.split()
    idf = {}
    for w, stems in zip(words, _stem_lines(words)):
        if stems:
            idf[w] = max(math.log(n_units / df.get(s, 1)) for s in stems)
    top_idf = max(idf.values(), default=1.0)
    expansion: dict[str, float] = {}
    for w, wi in idf.items():
        rel = subprocess.run([INDEX, "related", UNITS, "8", w],
                             capture_output=True, text=True, check=True).stdout.splitlines()
        rel = [l.split("\t") for l in rel]
        if not rel:
            continue
        best = float(rel[0][2])
        trust = (wi / top_idf) ** 2
        for _, surface, score in rel:
            weight = 0.4 * trust * float(score) / best
            if weight >= 0.08:
                expansion[surface] = max(expansion.get(surface, 0.0), weight)
    hits = _bm25(words + [f"{s}^{w:.2f}" for s, w in expansion.items()], 80)
    shown = sorted(expansion.items(), key=lambda x: -x[1])
    print(f"expanded with: {'، '.join(f'{s} ({w:.2f})' for s, w in shown)}\n")

    # 2. seeds: direct relevance of each section
    seed: Counter = Counter()
    unit_score = {}
    for uid, score in hits:
        seed[by_id[uid]["section"]] += score
        unit_score[uid] = score
    total = sum(seed.values()) or 1.0
    seed = Counter({s: v / total for s, v in seed.items()})

    # 3. personalised PageRank over the weighted section graph
    edges = build_graph()
    nbrs: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    why: dict[tuple[str, str], list[tuple[float, str, tuple]]] = defaultdict(list)
    for (a, b), es in edges.items():
        for kind, w, reason, ev in es:
            wt = EDGE_WEIGHT[kind] * w
            nbrs[a][b] += wt
            nbrs[b][a] += wt
            why[(a, b)].append((wt, f"{kind}: {reason}", ev))
            why[(b, a)].append((wt, f"{kind}: {reason}", ev))
    rank = dict(seed)
    for _ in range(40):
        nxt: Counter = Counter({s: (1 - alpha) * v for s, v in seed.items()})
        for s, r in rank.items():
            out = sum(nbrs[s].values())
            for t, w in nbrs[s].items():
                nxt[t] += alpha * r * w / out
        rank = nxt
    plain = {s for s, _ in seed.most_common(top)}

    # 4. report: each section, why it was reached, and its best passages
    for s, r in sorted(rank.items(), key=lambda x: -x[1])[:top]:
        sec = secs[s]
        tag = "direct match" if s in plain else "found through links"
        print(f"══ {section_path(secs, s)}\n   ج{sec['vol']} ص{sec['page']} · rank {r:.3f} · {tag}")
        reasons = sorted(((w, txt, t, ev) for t in rank if t != s and seed.get(t)
                          for w, txt, ev in why.get((s, t), [])), key=lambda x: -x[0])[:3]
        for w, txt, t, _ in reasons:
            print(f"   ↔ {secs[t]['title'][:50]} — {txt[:150]}")
        # Show the sentences that carry the links first, then the best matches.
        evidence = [e for *_, ev in reasons for e in ev if by_id[e]["section"] == s]
        in_sec = [u for u in us if u["section"] == s and u["kind"] != "heading"]
        in_sec.sort(key=lambda u: (u["id"] not in evidence, -unit_score.get(u["id"], 0.0)))
        for u in in_sec[:show_units]:
            print(f"   ▶ ج{u['vol']} ص{u['page']}: {u['text']}")
        print()
