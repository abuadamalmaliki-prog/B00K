#!/usr/bin/env python3
"""Exhaustive, speaker-aware evidence for a doctrinal question.

Ranked retrieval answers "which passages look most like the query?", which
is the wrong question for "what is the author's position?". There, an
ambiguous slogan ("نمرها كما جاءت") scores as well as the definition that
explains it, and a long quotation from someone else scores as well as the
author's own verdict. This tool does the opposite of top-k:

  * recall is exhaustive: every unit matching any term of the concept family
    is kept, with its neighbours for context, in reading order;
  * every unit carries a speaker tag: the author, the poem (matn), or the
    scholar he is quoting. Quotations open at "قال X:" and close at
    "انتهى/اهـ", when the author resumes glossing his poem "((…))", or
    after 12 units / at the section's end if unclosed;
  * passages are grouped by section so an argument reads as a whole.

The output is meant to be read in full, by a person or by Claude.

    python evidence.py tafwid > build/evidence_tafwid.md
"""

from __future__ import annotations

import argparse
import re
from collections import Counter

from read import section_path, sections, units

STRIP = re.compile(r"[ً-ْٰ]")

CONCEPTS = {
    # Tafwid vs. ithbat al-ma'na: the terms the dispute is argued in.
    "tafwid": {
        "core": [r"فوض|تفويض|المفوض", r"أمروها|أمرها|إمرار|نمره|نمرها|تمر كما|نمرها"],
        # these count only in combination (any two families in one unit)
        "pairs": {
            "معنى": r"(?:ال)?معن(?:ى|اه|اها|اهما)|المراد",
            "كيف": r"كيف|الكيفي|تكييف",
            "ظاهر": r"ظاهر",
            "تأويل": r"تأويل|يتأول|تأول|المؤول",
            "حقيقة": r"حقيقة|الحقيقة|حقيقي|مجاز",
            "إثبات": r"إثبات|نثبت|يثبت|أثبت",
        },
    },
}

QUOTE_OPEN = re.compile(
    r"(?:^|\s)(?:و|ف)?(?:قال|وقال|يقول|ذكر|حكى|نقل)\s+"
    r"((?:شيخ الإسلام|الإمام|الحافظ|العلامة|الشيخ|القاضي|الإمام المحقق|المحقق|ابن|أبو|الحافظ ابن)"
    r"[^:،.]{0,60}?)\s*:")
QUOTE_CLOSE = re.compile(r"انتهى|اهـ|ا\. هـ")
# The author is back when he resumes glossing his poem ("((…))") or says so.
AUTHOR_RESUMES = re.compile(r"\(\(|(?:فلهذا|ولهذا) قلت|قال الناظم|إذا (?:علمت|استحضرت|عرفت|تقرر)")
AUTHOR_MARK = re.compile(r"(?:^|\s)(?:قلت|فالحاصل|والحاصل|والحق|والمعتمد|وأقول|والذي يظهر)(?=[\s:،])")


def speaker_tags(us: list[dict]) -> list[str]:
    tags, quoting, left, section = [], None, 0, None
    for u in us:
        text = STRIP.sub("", u["text"])
        if u["section"] != section:
            quoting, section = None, u["section"]
        if u["kind"] == "matn":
            tags.append("poem")
            continue
        if u["kind"] == "heading":
            tags.append("heading")
            continue
        opened = QUOTE_OPEN.search(text)
        if quoting and AUTHOR_RESUMES.search(text) and not opened:
            quoting = None
        if quoting is None and opened:
            quoting, left = opened.group(1).strip(), 12
        if quoting:
            tags.append(f"quoting {quoting}")
            left -= 1
            if QUOTE_CLOSE.search(text) or left == 0:
                quoting = None
        else:
            tags.append("author!" if AUTHOR_MARK.search(text) else "author")
    return tags


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("concept", choices=CONCEPTS)
    ap.add_argument("--context", type=int, default=2, help="units of context each side")
    a = ap.parse_args()
    spec = CONCEPTS[a.concept]
    us, secs = units(), sections()
    tags = speaker_tags(us)

    hits = set()
    for i, u in enumerate(us):
        text = STRIP.sub("", u["text"])
        families = {k for k, p in spec["pairs"].items() if re.search(p, text)}
        if any(re.search(p, text) for p in spec["core"]) or len(families) >= 2:
            hits.add(i)
    keep = sorted({j for i in hits for j in range(i - a.context, i + a.context + 1)
                   if 0 <= j < len(us)})

    voices = Counter(tags[i].split(" ", 1)[0] for i in hits)
    print(f"# Evidence: {a.concept}\n\n{len(hits)} matching units (speakers: {dict(voices)}); "
          f"{len(keep)} units shown with context, in reading order. "
          f"★ = matching unit; [author!] = an explicit verdict marker (قلت، والحاصل، والحق…).\n")
    section = prev = None
    for j in keep:
        u = us[j]
        if u["section"] != section:
            section = u["section"]
            print(f"\n## {section_path(secs, section)} (ج{u['vol']} ص{u['page']})\n")
        elif prev is not None and j != prev + 1:
            print("   …")
        star = "★" if j in hits else " "
        print(f"{star} [{tags[j]}] ص{u['page']}: {u['text']}")
        prev = j


if __name__ == "__main__":
    main()
