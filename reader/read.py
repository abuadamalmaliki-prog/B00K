#!/usr/bin/env python3
"""Whole-book reader: OCaml parses, C++ indexes, Python cross-checks and answers.

    python read.py build ../لوامع_الأنوار_البهية.mARkdown   # compile + process every line
    python read.py stats
    python read.py quran                 # verify every Qur'an citation against the mushaf
    python read.py map > map.md          # outline with each section's distinctive terms
    python read.py matn                  # the commented poem, verse by verse, with locations
    python read.py ask "رؤية المؤمنين ربهم يوم القيامة" [-k 5]      # plain BM25
    python read.py graph                 # build the section graph (see graph.py)
    python read.py explore "رؤية المؤمنين ربهم" [--top 8]          # BM25 + expansion + graph

Stage outputs live in reader/build/ (units.tsv, sections.tsv, vocab.tsv,
section_terms.tsv, quran_checks.tsv).
"""

from __future__ import annotations

import argparse
import bisect
import csv
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
sys.path.insert(0, str(HERE.parent))

# Verses per surah in the Hafs/Kufan count; summing to 6236 is checked at runtime.
AYAH_COUNTS = [
    7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99, 128, 111, 110, 98, 135,
    112, 78, 118, 64, 77, 227, 93, 88, 69, 60, 34, 30, 73, 54, 45, 83, 182, 88, 75, 85, 54, 53,
    89, 59, 37, 35, 38, 29, 18, 45, 60, 49, 62, 55, 78, 96, 29, 22, 24, 13, 14, 11, 11, 18, 12,
    12, 30, 52, 52, 44, 28, 28, 20, 56, 40, 31, 50, 40, 46, 42, 29, 19, 36, 25, 22, 17, 19, 26,
    30, 20, 15, 21, 11, 8, 8, 19, 5, 8, 8, 11, 11, 8, 3, 9, 5, 4, 7, 3, 6, 3, 5, 4, 5, 6,
]
CITATION = re.compile(r"﴿([^﴾]+)﴾\s*\[([^:\]]+):\s*([٠-٩0-9]+)")
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
NON_LETTER = re.compile(r"[^ء-ي]")


def letters(text: str) -> str:
    """Skeleton for matching Qur'an text across spelling conventions:
    letters only, alef/yaa/taa-marbuta folded, alef dropped entirely
    (imla'i vs. uthmani spelling differs mostly in alefs)."""
    text = re.sub("[إأآٱ]", "ا", text).replace("ى", "ي").replace("ة", "ت")  # مرضاة = مرضات
    return NON_LETTER.sub("", text).replace("ا", "").replace("وو", "و")  # داوود = داود


# ---------------------------------------------------------------- loading

def units() -> list[dict]:
    with open(BUILD / "units.tsv", encoding="utf-8") as f:
        return [dict(zip(("id", "vol", "page", "section", "kind", "text"), r))
                for r in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)]


def sections() -> dict[str, dict]:
    with open(BUILD / "sections.tsv", encoding="utf-8") as f:
        return {r[0]: dict(zip(("id", "parent", "level", "vol", "page", "title"), r))
                for r in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)}


def section_path(secs: dict, sid: str) -> str:
    parts = []
    while sid in secs:
        parts.append(secs[sid]["title"])
        sid = secs[sid]["parent"]
    return " › ".join(reversed(parts))


# ---------------------------------------------------------------- commands

def build(book: Path) -> None:
    BUILD.mkdir(exist_ok=True)
    run = lambda *cmd: subprocess.run(cmd, check=True, cwd=BUILD)
    run("ocamlopt", "-I", "+str", "str.cmxa", "-o", "parse", str(HERE / "parse.ml"))
    run("g++", "-O2", "-std=c++17", "-o", "index", str(HERE / "index.cpp"))
    run("./parse", str(book.resolve()), ".")
    run("./index", "build", "units.tsv", ".")
    quran(quiet=True)


def stats() -> None:
    us = units()
    kinds = Counter(u["kind"] for u in us)
    words = sum(len(u["text"].split()) for u in us)
    vols = Counter(u["vol"] for u in us)
    print(f"units: {len(us)}  ({dict(kinds)})")
    print(f"words: {words}   sections: {len(sections())}   volumes: {dict(vols)}")
    print(f"pages: {len({(u['vol'], u['page']) for u in us})}")


def quran(quiet: bool = False) -> None:
    """Find every ﴿…﴾ [سورة: آية] citation in the mushaf and check the reference.

    The surah *names* the book uses are not hard-coded: they are learned from
    citations whose text occurs exactly once in the Qur'an, then used to
    disambiguate the rest and to flag references that disagree with the text.
    """
    from shamela import Library
    assert sum(AYAH_COUNTS) == 6236
    verses = Library().meta("quran_verses").sort_values("id", key=lambda s: s.astype(int))
    surah_ayah = [(s + 1, a + 1) for s, n in enumerate(AYAH_COUNTS) for a in range(n)]
    starts, joined, pos = [], [], 0
    for body in verses.body:
        starts.append(pos)
        sk = letters(body)
        joined.append(sk)
        pos += len(sk)
    mushaf = "".join(joined)

    def find_all(sk: str) -> list[tuple[int, int]]:
        hits, i = [], mushaf.find(sk)
        while i != -1:
            hits.append(surah_ayah[bisect.bisect_right(starts, i) - 1])
            i = mushaf.find(sk, i + 1)
        return hits

    def locate(fragment: str) -> tuple[list[tuple[int, int]], bool]:
        """Return (verse hits, exact?). The reference number belongs to the first
        verse when several are chained with " - "; elisions ("…", "إلى قوله")
        are skipped by matching the longest piece."""
        first = re.split(r"\s-\s", fragment)[0]
        piece = max(re.split(r"\.\.\.|…|إلى قوله", first), key=len)
        if len(letters(piece)) < 4:
            return [], True
        if hits := find_all(letters(piece)):
            return hits, True
        # Slightly misquoted: longest run of consecutive words (>= 60%) that occurs.
        words = piece.split()
        for size in range(len(words) - 1, max(2, -(-len(words) * 3 // 5)) - 1, -1):
            for start in range(len(words) - size + 1):
                sk = letters(" ".join(words[start:start + size]))
                if len(sk) >= 8 and (hits := find_all(sk)):
                    return hits, False
        return [], False

    cites = []
    for u in units():
        for m in CITATION.finditer(u["text"]):
            name = m.group(2).strip()
            ayah = int(m.group(3).translate(ARABIC_DIGITS))
            hits, exact = locate(m.group(1))
            pieces = re.split(r"\s-\s", m.group(1))
            last = locate(pieces[-1])[0] if len(pieces) > 1 else []
            cites.append((u, name, ayah, m.group(1), hits, exact, last))

    votes: dict[str, Counter] = defaultdict(Counter)
    for _, name, _, frag, hits, exact, _ in cites:
        # Learn names only from single-verse quotes found in exactly one surah.
        if exact and " - " not in frag and len(set(s for s, _ in hits)) == 1:
            votes[name][hits[0][0]] += 1
    name_to_surah = {n: c.most_common(1)[0][0] for n, c in votes.items()}
    # Names never quoted unambiguously: learn them from any quote that has
    # exactly one occurrence carrying the cited verse number.
    fallback: dict[str, Counter] = defaultdict(Counter)
    for _, name, ayah, _, hits, _, _ in cites:
        cands = {s for s, a in hits if a == ayah}
        if name not in name_to_surah and len(cands) == 1:
            fallback[name][cands.pop()] += 1
    name_to_surah.update({n: c.most_common(1)[0][0] for n, c in fallback.items()})

    rows, status = [], Counter()
    for u, name, ayah, frag, hits, exact, last in cites:
        want = name_to_surah.get(name)
        if not hits:
            found = ""
            short = len(letters(re.split(r"\s-\s", frag)[0])) < 4
            st = "too-short" if short else "not-found"
        else:
            same = [h for h in hits if h[0] == want] or hits
            best = min(same, key=lambda h: abs(h[1] - ayah) if h[0] == want else 999)
            found = f"{best[0]}:{best[1]}"
            if best[0] != want and any(s == want for s, _ in last):
                # Verses from several surahs chained in one ﴿…﴾ while the
                # reference names only the last surah: an edition formatting slip.
                st = "merged-surahs"
            elif best[0] != want:
                st = "surah-mismatch"
            elif best[1] == ayah:
                st = "ok"
            elif abs(best[1] - ayah) <= 2:  # fragment spans into a neighbouring verse
                st = "ok-adjacent"
            else:
                st = "ayah-mismatch"
            if not exact:
                st += "-partial"  # wording differs slightly from the mushaf
        status[st] += 1
        rows.append((u["id"], u["vol"], u["page"], name, ayah, found, st, frag.strip()))
    with open(BUILD / "quran_checks.tsv", "w", encoding="utf-8") as f:
        f.write("unit\tvol\tpage\tcited_surah\tcited_ayah\tfound\tstatus\ttext\n")
        for r in rows:
            f.write("\t".join(map(str, r)) + "\n")
    print(f"quran: {len(cites)} citations, {len(name_to_surah)} surah names learned: {dict(status)}")
    if not quiet:
        for r in rows:
            if not r[6].startswith(("ok", "too-short")):
                print(f"  ج{r[1]} ص{r[2]}  cited {r[3]}:{r[4]}  text is at {r[5]}  ﴿{r[7][:60]}﴾")


def book_map() -> None:
    secs = sections()
    terms = {}
    with open(BUILD / "section_terms.tsv", encoding="utf-8") as f:
        for r in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            terms[r[0]] = r[1:]
    per = defaultdict(Counter)
    for u in units():
        per[u["section"]][u["kind"]] += 1
        per[u["section"]]["words"] += len(u["text"].split())
    print("# Book map\n")
    for sid, s in secs.items():
        c = per[sid]
        print(f"{'  ' * (int(s['level']) - 1)}- **{s['title']}** — ج{s['vol']} ص{s['page']}, "
              f"{c['words']} words, {c['matn']} matn verses, {c['poetry']} other verses  \n"
              f"{'  ' * (int(s['level']) - 1)}  _{'، '.join(terms.get(sid, [])[:8])}_")


def matn(against: int | None = None) -> None:
    """The poem the book explains (al-Durra al-Mudiyya), in order, with locations.

    With --against BOOK_ID, compare with a standalone edition of the poem
    (2218 = العقيدة السفارينية) and list verses the commentary never quotes whole.
    """
    secs = sections()
    verses = [(re.sub(r"[()]", "", u["text"]).strip(), u) for u in units() if u["kind"] == "matn"]
    if against is None:
        for n, (verse, u) in enumerate(verses, 1):
            print(f"{n:3d}. {verse}\n     ج{u['vol']} ص{u['page']} · {secs.get(u['section'], {}).get('title', '')}")
        return
    from difflib import SequenceMatcher
    from shamela import Library, clean
    book = Library().book(against)
    lines = "\n".join(clean(p["body"]) for p in book.pages).split("\n")
    poem = [re.sub(r"^[٠-٩\s\-]+", "", l).strip("() ") for l in lines if " ... " in l]
    ours = [letters(v) for v, _ in verses]
    missing = [v for v in poem
               if max(SequenceMatcher(None, letters(v), o).ratio() for o in ours) < 0.8]
    print(f"standalone edition: {len(poem)} verses; commentary quotes {len(verses)} whole; "
          f"{len(poem) - len(missing)} matched (>=80% similar), {len(missing)} not quoted whole:")
    for v in missing:
        print("  ", v)


def ask(question: str, k: int) -> None:
    out = subprocess.run([str(BUILD / "index"), "query", str(BUILD / "units.tsv"), str(k), question],
                         capture_output=True, text=True, check=True).stdout
    us = units()
    by_id = {u["id"]: i for i, u in enumerate(us)}
    secs = sections()
    for line in out.splitlines():
        uid, score = line.split("\t")
        i = by_id[uid]
        u = us[i]
        print(f"── ج{u['vol']} ص{u['page']} · {section_path(secs, u['section'])} · score {float(score):.1f}")
        for j in range(max(0, i - 1), min(len(us), i + 2)):  # one unit of context each side
            mark = "▶ " if j == i else "  "
            print(mark + us[j]["text"])
        print()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build").add_argument("book", type=Path)
    sub.add_parser("stats")
    sub.add_parser("quran")
    sub.add_parser("map")
    sub.add_parser("matn").add_argument("--against", type=int)
    q = sub.add_parser("ask")
    q.add_argument("question")
    q.add_argument("-k", type=int, default=5)
    sub.add_parser("graph")
    e = sub.add_parser("explore")
    e.add_argument("question")
    e.add_argument("--top", type=int, default=8)
    a = ap.parse_args()
    if a.cmd == "build":
        build(a.book)
    elif a.cmd == "stats":
        stats()
    elif a.cmd == "quran":
        quran()
    elif a.cmd == "map":
        book_map()
    elif a.cmd == "matn":
        matn(a.against)
    elif a.cmd == "graph":
        from graph import graph_stats
        graph_stats()
    elif a.cmd == "explore":
        from graph import explore
        explore(a.question, a.top)
    else:
        ask(a.question, a.k)


if __name__ == "__main__":
    main()
