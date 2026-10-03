#!/usr/bin/env python3
"""Tiny CLI over the AuthenticIlm/Shamela4_Full_DB dataset (HuggingFace).

Usage:
  shamela.py find  <regex>                 search book titles/authors -> book_id
  shamela.py toc   <book_id> [regex]       table of contents (optionally filtered)
  shamela.py grep  <book_id> <regex> [N]   search pages; N = max hits (default 15)
  shamela.py page  <book_id> <page_num> [part]   print one full page (original text)
  shamela.py pid   <book_id> <page_id>    print the page a toc entry points to
grep prints NORMALISED text (to find things); quote from `page`/`pid` output.
Books are downloaded once and cached under lib/books/<book_id>/.
Normalisation: grep ignores tashkeel and unifies أ/إ/آ->ا, ى->ي, ة->ه.
"""
import json, os, re, signal, sys, urllib.parse, urllib.request

signal.signal(signal.SIGPIPE, signal.SIG_DFL)

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = "https://huggingface.co/datasets/AuthenticIlm/Shamela4_Full_DB/resolve/main/"
INDEX = json.load(open(os.path.join(HERE, "index.json")))
META = os.path.join(os.path.dirname(HERE), "book_metadata.parquet")

TASHKEEL = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
TAGS = re.compile(r"<[^>]+>")


def norm(s):
    s = TASHKEEL.sub("", s or "")
    s = re.sub("[أإآٱ]", "ا", s)
    return s.replace("ى", "ي").replace("ة", "ه")


def clean(s):
    return TAGS.sub("", (s or "")).replace("\r", "\n")


def fetch(book_id, name):
    d = os.path.join(HERE, "books", str(book_id))
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, name)
    if not os.path.exists(p):
        path = INDEX[str(book_id)]
        url = BASE + urllib.parse.quote(path + "/" + name)
        tmp = p + ".part"
        with urllib.request.urlopen(url) as r, open(tmp, "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
        os.rename(tmp, p)
    return p


def pages(book_id):
    with open(fetch(book_id, "pages.jsonl"), encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def cmd_find(rx):
    import pandas as pd
    df = pd.read_parquet(META)
    r = re.compile(norm(rx))
    for _, b in df.iterrows():
        hay = norm(f"{b.title_ar} {b.main_author_name_ar}")
        if r.search(hay):
            print(f"{b.book_id}\t{b.title_ar}\t{b.main_author_name_ar} (d.{b.main_author_death_hijri})\t[{b.category_name_ar}]")


def cmd_toc(book_id, rx=None):
    r = re.compile(norm(rx)) if rx else None
    with open(fetch(book_id, "toc.jsonl"), encoding="utf-8") as f:
        for line in f:
            t = json.loads(line)
            s = json.dumps(t, ensure_ascii=False)
            if r is None or r.search(norm(s)):
                print(s[:300])


def cmd_grep(book_id, rx, n=15):
    r = re.compile(norm(rx))
    hits = 0
    for p in pages(book_id):
        body = clean(p.get("body"))
        nb = norm(body)
        m = r.search(nb)
        if not m:
            continue
        # map approximate position back: show a window from the normalised text
        a, b = max(0, m.start() - 350), min(len(nb), m.end() + 450)
        print(f"--- book {book_id} | part {p.get('part')} | page {p.get('page_num')}")
        print(nb[a:b].strip())
        hits += 1
        if hits >= n:
            break
    if not hits:
        print("(no hits)")


def cmd_page(book_id, num, part=None, by="page_num"):
    for p in pages(book_id):
        if str(p.get(by)) == str(num) and (part is None or str(p.get("part")) == str(part)):
            print(f"--- book {book_id} | part {p.get('part')} | page {p.get('page_num')}")
            print(clean(p.get("body")))
            if p.get("footnotes"):
                print("[footnotes]\n" + clean(p.get("footnotes")))


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__)
    elif a[0] == "find":
        cmd_find(a[1])
    elif a[0] == "toc":
        cmd_toc(a[1], a[2] if len(a) > 2 else None)
    elif a[0] == "grep":
        cmd_grep(a[1], a[2], int(a[3]) if len(a) > 3 else 15)
    elif a[0] == "page":
        cmd_page(a[1], a[2], a[3] if len(a) > 3 else None)
    elif a[0] == "pid":
        cmd_page(a[1], a[2], by="page_id")
    else:
        print(__doc__)
