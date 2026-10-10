#!/usr/bin/env python3
"""
shamela_reader — biar Claude (Opus) baca satu kitab Shamela SEPENUHNYA dan faham
seluruh konteks. Bukan RAG, bukan grep: setiap patah teks dibaca.

Dataset: AuthenticIlm/Shamela4_Full_DB di Hugging Face.
Setiap kitab ada folder: pages.jsonl (teks), toc.jsonl, book_metadata.json.

Aliran:
  find   : cari kitab ikut nama / id dalam dataset
  fetch  : muat turun satu kitab + cantum jadi teks bersih (book.txt)
  read   : Opus baca kitab penuh, jawab soalan + rujukan muka surat
           (via CLI `claude -p`, tanpa API key)
           - muat 1M      -> baca penuh (satu context, paling setia)
           - terlalu besar -> MAP->REDUCE (baca 100% teks berperingkat)

Guna:
  pip install -r requirements.txt
  # Tak perlu ANTHROPIC_API_KEY: guna CLI `claude` (Claude Code) yang dah login.

  python shamela_reader.py find "الطحاوية"
  python shamela_reader.py fetch "01__العقيدة/2970__شرح-العقيدة-الطحاوية-ط-الرسالة"
  python shamela_reader.py read 2970 "ما منهج الشارح في العقيدة؟"
  python shamela_reader.py read 2970 --faham          # faham seluruh kitab
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ID = "AuthenticIlm/Shamela4_Full_DB"
MODEL = "claude-opus-5-5"            # Opus terbaru, context 1M token
FIT_BUDGET = 700_000                # <= ni: baca penuh satu context
SEGMENT_BUDGET = 700_000            # saiz satu segmen MAP (besar = lebih setia)
REDUCE_BUDGET = 700_000
CHARS_PER_TOKEN = 2.2               # anggaran kasar teks Arab

HERE = Path(__file__).resolve().parent
BOOKS_DIR = HERE / "books"          # tempat simpan kitab yang dimuat turun
CACHE_DIR = HERE / ".cache"


# ===========================================================================
# Hugging Face: cari & muat turun
# ===========================================================================
def _hf_api():
    from huggingface_hub import HfApi
    return HfApi()


def list_book_dirs() -> list[str]:
    """Senarai semua folder kitab (dicache). Bentuk: 'NN__kategori/ID__slug'."""
    CACHE_DIR.mkdir(exist_ok=True)
    cache = CACHE_DIR / "book_dirs.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    files = _hf_api().list_repo_files(REPO_ID, repo_type="dataset")
    dirs = sorted({str(Path(f).parent) for f in files if f.endswith("/book_metadata.json")})
    cache.write_text(json.dumps(dirs, ensure_ascii=False), encoding="utf-8")
    return dirs


def find(keyword: str) -> list[tuple[str, str, str]]:
    """Pulangkan (book_id, slug, full_path) yang padan keyword pada nama folder."""
    out = []
    for d in list_book_dirs():
        leaf = Path(d).name              # 'ID__slug'
        if keyword in leaf or keyword in d:
            bid, _, slug = leaf.partition("__")
            out.append((bid, slug, d))
    return out


def resolve_path(book_id: str) -> str | None:
    for d in list_book_dirs():
        if Path(d).name.startswith(f"{book_id}__"):
            return d
    return None


def fetch(book_path: str) -> Path:
    """Muat turun pages/toc/metadata satu kitab, cantum jadi book.txt."""
    from huggingface_hub import hf_hub_download
    bid = Path(book_path).name.split("__")[0]
    dest = BOOKS_DIR / bid
    dest.mkdir(parents=True, exist_ok=True)
    for fn in ("book_metadata.json", "toc.jsonl", "pages.jsonl"):
        hf_hub_download(
            REPO_ID, f"{book_path}/{fn}", repo_type="dataset",
            local_dir=str(dest / "_raw"),
        )
    raw = dest / "_raw" / book_path
    meta = json.loads((raw / "book_metadata.json").read_text(encoding="utf-8"))
    assemble(raw / "pages.jsonl", dest / "book.txt")
    (dest / "meta.json").write_text(
        json.dumps({k: meta.get(k) for k in
                    ("book_id", "shamela_id", "title_ar", "main_author_name_ar",
                     "main_author_death_hijri", "betaka_text", "volume_count_observed")},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    return dest


# ===========================================================================
# Cantum teks bersih dari pages.jsonl
# ===========================================================================
def _clean(t: str) -> str:
    import html
    if not t:
        return ""
    t = re.sub(r'<span[^>]*data-type="title"[^>]*>(.*?)</span>', r'\n### \1\n', t, flags=re.S)
    t = re.sub(r'<[^>]+>', '', t)
    return html.unescape(t).strip()


def assemble(pages_jsonl: Path, out_txt: Path) -> None:
    pages = [json.loads(l) for l in open(pages_jsonl, encoding="utf-8") if l.strip()]
    pages.sort(key=lambda p: p.get("sequence_num") or 0)
    chunks = []
    for p in pages:
        chunks.append(f"\n[ج{p.get('part')}/ص{p.get('page_num')}]\n" + _clean(p.get("body") or ""))
        fn = _clean(p.get("footnotes") or "")
        if fn:
            chunks.append(f"\n(الحواشي ج{p.get('part')}/ص{p.get('page_num')}): {fn}")
    out_txt.write_text("\n".join(chunks), encoding="utf-8")


# ===========================================================================
# Claude via CLI `claude -p` (guna login Claude Code, tanpa API key)
# ===========================================================================


SYSTEM = (
    "أنت قارئ متقن وأمين لكتب التراث العربي الإسلامي. اقرأ النص المعطى كاملًا "
    "وافهم سياقه كله، لا الكلمات المفتاحية وحدها؛ التقط أيضًا ما يتصل بالمسألة "
    "ولو بألفاظ مختلفة أو في مواضع متباعدة. اذكر أرقام الصفحات [ج/ص] عند النقل، "
    "ولا تذكر ما ليس في النص."
)


def _count(text: str) -> int:
    """Anggaran token secara lokal (tiada API utk count_tokens)."""
    return int(len(text) / CHARS_PER_TOKEN)


def _ask(prompt: str, cache_text: str | None = None, effort: str = "high") -> str:
    """Satu panggilan Opus via `claude -p`. Teks kitab dihantar melalui stdin."""
    full = f"{cache_text}\n\n{prompt}" if cache_text is not None else prompt
    r = subprocess.run(
        ["claude", "-p", "--model", MODEL, "--effort", effort,
         "--system-prompt", SYSTEM, "--tools", "", "--output-format", "text"],
        input=full, capture_output=True, text=True, encoding="utf-8",
    )
    if r.returncode != 0:
        sys.exit(f"claude -p gagal ({r.returncode}): {r.stderr.strip()}")
    return r.stdout.strip()


# --- Baca penuh (muat 1M) ---------------------------------------------------
def _read_full(book_text: str, task: str) -> str:
    return _ask(task, cache_text=book_text)


# --- MAP -> REDUCE (kitab gergasi) -----------------------------------------
def _segments(text: str) -> list[str]:
    """Pecah ikut penanda muka surat [ج/ص] jadi segmen <= SEGMENT_BUDGET."""
    parts = re.split(r'(?=\n\[ج\d+/ص\d+\]\n)', text)
    segs, buf, buf_len = [], [], 0
    cap = int(SEGMENT_BUDGET * 2.2)      # had aksara (~2.2 aksara/token)
    for p in parts:
        if buf_len + len(p) > cap and buf:
            segs.append("".join(buf)); buf, buf_len = [], 0
        buf.append(p); buf_len += len(p)
    if buf:
        segs.append("".join(buf))
    return segs


def _map_one(book_id: str, idx: int, total: int, seg: str, task: str) -> str:
    CACHE_DIR.mkdir(exist_ok=True)
    key = CACHE_DIR / (hashlib.sha256(f"{book_id}|{idx}|{task}".encode()).hexdigest()[:16] + ".txt")
    if key.exists():
        return key.read_text(encoding="utf-8")
    print(f"  MAP {idx+1}/{total} ...", file=sys.stderr)
    prompt = (
        "هذا جزء من كتاب كبير يُقرأ على مراحل.\n"
        f"المطلوب: {task}\n\n"
        "استخرج من هذا الجزء كل ما يتصل بالمطلوب: نصوصًا حرفية مع [ج/ص]، أدلة، "
        "حججًا، وإحالات — بسخاء، فالأخذ خير من التفويت. إن لم يوجد شيء فاكتب: لا شيء."
    )
    res = _ask(prompt, cache_text=seg)
    key.write_text(res, encoding="utf-8")
    return res


def _reduce(notes: list[str], task: str) -> str:
    joined = "\n\n---\n\n".join(n for n in notes if n.strip() and "لا شيء" not in n[:10])
    if not joined.strip():
        return "لم يُعثر على مادة متصلة بالمطلوب في الكتاب."
    if len(joined) > REDUCE_BUDGET * 2.2:
        mid = len(notes) // 2
        joined = _reduce(notes[:mid], task) + "\n\n---\n\n" + _reduce(notes[mid:], task)
    prompt = (
        "فيما يلي كل النصوص المتصلة بالمطلوب، مجموعة من الكتاب كله (قُرئ كل جزء "
        f"كاملًا):\n\n{joined}\n\n"
        f"بناءً على هذه المادة كلها، {task} واربط الإحالات بين المواضع والأجزاء، "
        "واذكر الصفحات [ج/ص]."
    )
    return _ask(prompt, effort="high")


# ===========================================================================
# read: pilih mod ikut saiz + anggaran kos
# ===========================================================================
def read(book_id: str, task: str) -> None:
    dest = BOOKS_DIR / book_id
    book_txt = dest / "book.txt"
    if not book_txt.exists():
        path = resolve_path(book_id)
        if not path:
            sys.exit(f"Kitab id {book_id} tak jumpa. Guna: find <keyword>")
        print(f"Muat turun {path} ...", file=sys.stderr)
        fetch(path)
    text = book_txt.read_text(encoding="utf-8")

    meta = json.loads((dest / "meta.json").read_text(encoding="utf-8")) if (dest / "meta.json").exists() else {}
    print(f"Kitab : {meta.get('title_ar', book_id)}", file=sys.stderr)
    print(f"Mؤلف  : {meta.get('main_author_name_ar','-')}", file=sys.stderr)

    tokens = _count(text)
    print(f"Token : ~{tokens:,} (anggaran)", file=sys.stderr)

    if tokens <= FIT_BUDGET:
        print("Mod   : BACA PENUH (satu context, paling setia)\n", file=sys.stderr)
        print(_read_full(text, task))
    else:
        segs = _segments(text)
        print(f"Mod   : MAP->REDUCE, {len(segs)} segmen (baca 100%, jangan terlepas)\n",
              file=sys.stderr)
        notes = [_map_one(book_id, i, len(segs), s, task) for i, s in enumerate(segs)]
        print("  REDUCE ...", file=sys.stderr)
        print(_reduce(notes, task))


# ===========================================================================
# CLI
# ===========================================================================
def main() -> None:
    ap = argparse.ArgumentParser(description="Biar Opus baca kitab Shamela penuh (bukan RAG).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("find", help="cari kitab ikut nama/id")
    p.add_argument("keyword")

    p = sub.add_parser("fetch", help="muat turun + cantum satu kitab")
    p.add_argument("book_path", help="cth 01__العقيدة/2970__...  (dari find)")

    p = sub.add_parser("read", help="baca kitab penuh + jawab soalan")
    p.add_argument("book_id")
    p.add_argument("question", nargs="?", default=None)
    p.add_argument("--faham", action="store_true", help="faham seluruh kitab (tanpa soalan)")

    a = ap.parse_args()

    if a.cmd == "find":
        hits = find(a.keyword)
        if not hits:
            print("Tiada padanan."); return
        for bid, slug, path in hits:
            print(f"[{bid}] {slug}\n      {path}")
        print(f"\n{len(hits)} kitab. Seterusnya: read <id> \"soalan\"")

    elif a.cmd == "fetch":
        dest = fetch(a.book_path)
        print(f"Siap -> {dest/'book.txt'}")

    elif a.cmd == "read":
        task = a.question or (
            "افهم واشرح بنية الكتاب وموضوعاته ومنهج المؤلف وأبرز مسائله إجمالًا."
            if (a.faham or not a.question) else a.question)
        read(a.book_id, task)


if __name__ == "__main__":
    main()
