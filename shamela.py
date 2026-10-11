#!/usr/bin/env python3
"""Explore the Shamela 4 digital library hosted on Hugging Face.

Dataset: https://huggingface.co/datasets/AuthenticIlm/Shamela4_Full_DB

The dataset is ~19 GB, so nothing is loaded wholesale: the 1.2 MB catalogue
(_meta/book_metadata.parquet) is used to find books, and only the books you
open are downloaded (a few hundred KB to a few tens of MB each). Everything is
cached under ./.shamela_cache (override with SHAMELA_CACHE).

Layout on the hub:
    _meta/*.parquet                       catalogue, authors, categories, xrefs…
    NN__<category>/<book_id>__<slug>/     one folder per book
        book_metadata.json  manifest.json  toc.jsonl  pages.jsonl

Library use:
    from shamela import Library
    lib = Library()
    lib.search(title="الواسطية")            # pandas DataFrame
    book = lib.book(5946)
    book.print_toc()
    print(book.page_text(book.pages[2]))
    book.grep("الإيمان")
    book.to_openiti("out.mARkdown")

CLI:
    python shamela.py categories
    python shamela.py search --title الواسطية --author "ابن تيمية"
    python shamela.py info 5946
    python shamela.py toc 5946
    python shamela.py read 5946 --page 54
    python shamela.py grep 5946 "صفة المحبة"
    python shamela.py export 5946 العقيدة_الواسطية.mARkdown
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Iterator

import pandas as pd
from huggingface_hub import HfApi, hf_hub_download

REPO_ID = "AuthenticIlm/Shamela4_Full_DB"
CACHE_DIR = Path(os.environ.get("SHAMELA_CACHE", Path(__file__).parent / ".shamela_cache"))

META_TABLES = (
    "authors", "book_metadata", "categories", "quran_verses", "narrators",
    "root_dictionary", "hadith_xrefs", "tafsir_xrefs", "page_isnads",
)

# Arabic diacritics (tashkeel) + tatweel, for diacritic-insensitive search.
_TASHKEEL = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
_TITLE_SPAN = re.compile(r'<span data-type="?title"?\s+id="?toc-(\d+)"?>(.*?)</span>', re.S)
_TAG = re.compile(r"<[^>]+>")
_IMG = re.compile(r"<img[^>]*>", re.I)


def strip_tashkeel(text: str) -> str:
    return _TASHKEEL.sub("", text)


def normalize(text: str) -> str:
    """Loose form for searching: no diacritics, unified alef/yaa/taa marbuta."""
    text = strip_tashkeel(text)
    text = re.sub("[إأآٱ]", "ا", text)
    return text.replace("ى", "ي").replace("ة", "ه")


def clean(raw: str | None, keep_tashkeel: bool = True) -> str:
    """Raw Shamela page markup -> plain text with real newlines."""
    if not raw:
        return ""
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = _IMG.sub("[صورة]", text)
    text = _TAG.sub("", text)
    if not keep_tashkeel:
        text = strip_tashkeel(text)
    return text.strip()


def _download(path: str) -> Path:
    return Path(hf_hub_download(REPO_ID, path, repo_type="dataset", local_dir=CACHE_DIR))


# ---------------------------------------------------------------------------
# Library: catalogue-level operations
# ---------------------------------------------------------------------------

class Library:
    def __init__(self) -> None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def meta(self, table: str) -> pd.DataFrame:
        """Load one of the _meta parquet tables (downloaded on first use).

        Sizes: book_metadata 1.2 MB, authors 2 MB, narrators 8 MB,
        root_dictionary 11 MB, the rest < 1 MB.
        Note: in tafsir_xrefs/hadith_xrefs, book_id is the *shamela_id*.
        """
        if table not in META_TABLES:
            raise ValueError(f"unknown table {table!r}; choose from {META_TABLES}")
        return pd.read_parquet(_download(f"_meta/{table}.parquet"))

    @cached_property
    def catalog(self) -> pd.DataFrame:
        return self.meta("book_metadata").set_index("book_id", drop=False)

    @cached_property
    def categories(self) -> pd.DataFrame:
        counts = self.catalog.groupby("category_id").size().rename("books")
        cats = self.meta("categories").set_index("id").join(counts)
        return cats[cats.books.notna()].sort_values("sort_order")

    @cached_property
    def _book_dirs(self) -> dict[int, str]:
        """book_id -> hub folder. Built from one file-listing call, then cached."""
        index = CACHE_DIR / "book_dirs.json"
        if index.exists():
            return {int(k): v for k, v in json.loads(index.read_text()).items()}
        dirs = {}
        for f in HfApi().list_repo_files(REPO_ID, repo_type="dataset"):
            if f.endswith("/pages.jsonl"):
                folder = f.rsplit("/", 1)[0]
                dirs[int(folder.split("/")[1].split("__")[0])] = folder
        index.write_text(json.dumps(dirs, ensure_ascii=False))
        return dirs

    def search(self, title: str | None = None, author: str | None = None,
               category: int | str | None = None, died_before: int | None = None,
               died_after: int | None = None) -> pd.DataFrame:
        """Filter the catalogue. Text matching ignores diacritics and hamza forms."""
        df = self.catalog
        mask = pd.Series(True, index=df.index)
        if title:
            mask &= df.title_ar.fillna("").map(normalize).str.contains(normalize(title), regex=False)
        if author:
            names = df.main_author_name_ar.fillna("") + " " + df.authors_json.fillna("")
            mask &= names.map(normalize).str.contains(normalize(author), regex=False)
        if category is not None:
            if isinstance(category, int) or str(category).isdigit():
                mask &= df.category_id == int(category)
            else:
                mask &= df.category_name_ar.fillna("").map(normalize).str.contains(normalize(category))
        if died_before is not None:
            mask &= df.main_author_death_hijri.between(1, died_before)
        if died_after is not None:
            mask &= df.main_author_death_hijri.between(died_after, 99998)
        cols = ["book_id", "shamela_id", "title_ar", "main_author_name_ar",
                "main_author_death_hijri", "category_name_ar"]
        return df.loc[mask, cols]

    def book(self, book_id: int) -> "Book":
        """Download (if needed) and open a book by its dataset book_id."""
        book_id = int(book_id)
        folder = self._book_dirs.get(book_id)
        if folder is None:
            raise KeyError(f"no book with book_id={book_id}")
        for name in ("book_metadata.json", "toc.jsonl", "pages.jsonl"):
            _download(f"{folder}/{name}")
        return Book(CACHE_DIR / folder)

    def book_by_shamela_id(self, shamela_id: int) -> "Book":
        """Open a book by its shamela.ws id (as in https://shamela.ws/book/<id>)."""
        hit = self.catalog[self.catalog.shamela_id == int(shamela_id)]
        if hit.empty:
            raise KeyError(f"no book with shamela_id={shamela_id}")
        return self.book(int(hit.book_id.iloc[0]))


# ---------------------------------------------------------------------------
# Book: one downloaded book
# ---------------------------------------------------------------------------

@dataclass
class Heading:
    title_id: int
    shamela_title_id: int
    page_id: int
    text: str
    depth: int = 0
    children: list["Heading"] = field(default_factory=list)


class Book:
    def __init__(self, folder: Path) -> None:
        self.folder = Path(folder)
        self.metadata: dict = json.loads((self.folder / "book_metadata.json").read_text())

    def __repr__(self) -> str:
        return f"<Book {self.book_id}: {self.title} — {self.author}>"

    @property
    def book_id(self) -> int:
        return self.metadata["book_id"]

    @property
    def title(self) -> str:
        return self.metadata["title_ar"]

    @property
    def author(self) -> str:
        return self.metadata.get("main_author_name_ar") or ""

    def iter_pages(self) -> Iterator[dict]:
        """Stream pages in reading order without loading the whole file."""
        with open(self.folder / "pages.jsonl", encoding="utf-8") as f:
            for line in f:
                yield json.loads(line)

    @cached_property
    def pages(self) -> list[dict]:
        return sorted(self.iter_pages(), key=lambda p: p["sequence_num"])

    @cached_property
    def toc(self) -> list[Heading]:
        """Table of contents as a tree (roots), ordered by position in the book."""
        rows = [json.loads(l) for l in open(self.folder / "toc.jsonl", encoding="utf-8")]
        rows.sort(key=lambda r: (r["page_id"], r["shamela_title_id"]))
        nodes = {r["title_id"]: Heading(r["title_id"], r["shamela_title_id"], r["page_id"],
                                        r["title_text"]) for r in rows}
        roots = []
        for r in rows:
            node, parent = nodes[r["title_id"]], nodes.get(r["parent_id"])
            (parent.children if parent else roots).append(node)

        def set_depth(ns: list[Heading], d: int) -> None:
            for n in ns:
                n.depth = d
                set_depth(n.children, d + 1)
        set_depth(roots, 0)
        return roots

    def headings(self) -> list[Heading]:
        """Flattened TOC in reading order (depth still reflects the tree)."""
        flat: list[Heading] = []

        def walk(ns: list[Heading]) -> None:
            for n in ns:
                flat.append(n)
                walk(n.children)
        walk(self.toc)
        return sorted(flat, key=lambda h: (h.page_id, h.shamela_title_id))

    def print_toc(self, max_depth: int | None = None) -> None:
        by_id = {p["page_id"]: p for p in self.pages}
        for h in self.headings():
            if max_depth is None or h.depth <= max_depth:
                print(f"{'  ' * h.depth}{h.text}  [{self.page_ref(by_id.get(h.page_id))}]")

    @staticmethod
    def page_ref(page: dict | None) -> str:
        """Printed reference like 'ج2 ص45' (falls back to the sequence number)."""
        if not page:
            return "?"
        num = page["page_num"] if page["page_num"] is not None else f"#{page['sequence_num']}"
        return f"ج{page['part']} ص{num}" if page.get("part") else f"ص{num}"

    def find_page(self, page_num: int, part: str | int | None = None) -> dict:
        """Look up a page by its printed number (and volume, for multi-part books)."""
        for p in self.pages:
            if p["page_num"] == page_num and (part is None or str(p["part"]) == str(part)):
                return p
        raise KeyError(f"page {page_num} (part {part}) not found")

    def page_text(self, page: dict, keep_tashkeel: bool = True, footnotes: bool = True) -> str:
        text = clean(page["body"], keep_tashkeel)
        if footnotes and page.get("footnotes"):
            text += "\n__________\n" + clean(page["footnotes"], keep_tashkeel)
        return text

    def text(self, keep_tashkeel: bool = True, footnotes: bool = False) -> str:
        return "\n\n".join(self.page_text(p, keep_tashkeel, footnotes) for p in self.pages)

    def grep(self, pattern: str, regex: bool = False, context: int = 40) -> list[tuple[str, str]]:
        """Diacritic-insensitive search. Returns (page ref, snippet) pairs."""
        needle = re.compile(pattern if regex else re.escape(normalize(pattern)))
        hits = []
        for p in self.pages:
            plain = normalize(clean(p["body"]))
            for m in needle.finditer(plain):
                s, e = max(0, m.start() - context), m.end() + context
                hits.append((self.page_ref(p), plain[s:e].replace("\n", " ")))
        return hits

    def to_openiti(self, out_path: str | Path, keep_tashkeel: bool = True) -> Path:
        """Export as OpenITI mARkdown (same layout as the books in this repo).

        Volumes become '### | الجزء NN', TOC headings '### ||', '### |||', …
        at their TOC depth, each page ends with a PageVxxPyyy milestone.
        """
        heads_on_page: dict[int, list[Heading]] = {}
        for h in self.headings():
            heads_on_page.setdefault(h.page_id, []).append(h)

        vols = {p["part"] for p in self.pages}
        vol_no = {v: i + 1 for i, v in enumerate(sorted(vols, key=lambda v: (v is None, str(v).zfill(5))))}
        out = [
            "######OpenITI#", "",
            "#META# Header#Begin#",
            f"#META# 000.BookURI# {self.title}",
            f"#META# 000.Author# {self.author}",
            f"#META# 000.Source# https://shamela.ws/book/{self.metadata['shamela_id']}",
            "#META# Header#End#", "",
        ]
        current_vol = object()
        for p in self.pages:
            if p["part"] != current_vol:
                current_vol = p["part"]
                out += [f"### | الجزء {vol_no[current_vol]:02d}", ""]
            for h in heads_on_page.get(p["page_id"], []):
                text = h.text if keep_tashkeel else strip_tashkeel(h.text)
                out += [f"### {'|' * (h.depth + 2)} {text}", ""]
            body = clean(p["body"], keep_tashkeel)
            if body:
                out += ["# " + line for line in body.split("\n") if line.strip()]
            if p.get("footnotes"):
                out += ["", "_" * 20] + ["# " + l for l in clean(p["footnotes"], keep_tashkeel).split("\n") if l.strip()]
            page_no = p["page_num"] if p["page_num"] is not None else 0
            out += [f"PageV{vol_no[current_vol]:02d}P{page_no:03d}", ""]
        out_path = Path(out_path)
        out_path.write_text("\n".join(out), encoding="utf-8")
        return out_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("categories", help="list categories with book counts")
    s = sub.add_parser("search", help="search the catalogue")
    s.add_argument("--title"); s.add_argument("--author"); s.add_argument("--category")
    s.add_argument("--died-before", type=int); s.add_argument("--died-after", type=int)
    s.add_argument("--limit", type=int, default=50)
    for name in ("info", "toc"):
        sub.add_parser(name).add_argument("book_id", type=int)
    r = sub.add_parser("read", help="print a page by printed number")
    r.add_argument("book_id", type=int); r.add_argument("--page", type=int, required=True)
    r.add_argument("--part"); r.add_argument("--no-tashkeel", action="store_true")
    g = sub.add_parser("grep", help="search inside a book")
    g.add_argument("book_id", type=int); g.add_argument("pattern")
    g.add_argument("--regex", action="store_true")
    e = sub.add_parser("export", help="export a book to OpenITI mARkdown")
    e.add_argument("book_id", type=int); e.add_argument("out")
    e.add_argument("--no-tashkeel", action="store_true")
    a = ap.parse_args(argv)

    lib = Library()
    pd.set_option("display.width", 200, "display.max_colwidth", 60)
    if a.cmd == "categories":
        print(lib.categories[["name_ar", "books"]].astype({"books": int}).to_string())
    elif a.cmd == "search":
        res = lib.search(a.title, a.author, a.category, a.died_before, a.died_after)
        print(f"{len(res)} books")
        print(res.head(a.limit).to_string(index=False))
    elif a.cmd == "info":
        b = lib.book(a.book_id)
        m = b.metadata
        death = m.get("main_author_death_hijri")
        death = "?" if death in (None, 99999) else death  # 99999 = unknown
        print(f"{b.title}\n{b.author} (ت {death}هـ)\n"
              f"category: {m.get('category_name_ar')}  shamela: https://shamela.ws/book/{m['shamela_id']}\n"
              f"pages: {len(b.pages)}  headings: {len(b.headings())}\n")
        print(clean(m.get("betaka_text")))
    elif a.cmd == "toc":
        lib.book(a.book_id).print_toc()
    elif a.cmd == "read":
        b = lib.book(a.book_id)
        print(b.page_text(b.find_page(a.page, a.part), keep_tashkeel=not a.no_tashkeel))
    elif a.cmd == "grep":
        hits = lib.book(a.book_id).grep(a.pattern, a.regex)
        for ref, snip in hits:
            print(f"{ref}\t…{snip}…")
        print(f"{len(hits)} hits", file=sys.stderr)
    elif a.cmd == "export":
        print(lib.book(a.book_id).to_openiti(a.out, keep_tashkeel=not a.no_tashkeel))


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:  # e.g. `python shamela.py toc 1 | head`
        sys.stderr.close()
