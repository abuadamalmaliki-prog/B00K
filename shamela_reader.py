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

Kajian mendalam (bacaan selari, matan + SEMUA nota kaki):
  prep   : pecah kitab jadi unit bacaan; setiap nota kaki diletak tepat di bawah
           baris matan yang dirujuknya (bukan di hujung halaman)
  (pembaca selari baca setiap unit penuh ikut kajian_prompt.md -> study/<id>/notes/)
  verify : semak setiap petikan «...» dalam nota wujud dalam teks asal
  merge  : himpun bahagian yang sama dari semua unit untuk peringkat penyatuan

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
# prep: sediakan unit bacaan (matan + nota kaki di bawah baris yang dihuraikan)
# ===========================================================================
STUDY_DIR = HERE / "study"
UNIT_TOKENS = 24_000                # saiz sasaran satu unit (dibaca penuh oleh satu pembaca)
_PARA = re.compile(r'^\s*([٠-٩]+)\s*[-ـ﵀-﷿]')    # "١٢٣ - " (nombor perenggan)
_MARK = re.compile(r'\(¬([٠-٩0-9]+)\)')
_HARAKAT = re.compile(r'[ؐ-ًؚ-ٰٟۖ-ۭـ]')


def _raw_dir(book_id: str) -> Path:
    hits = list((BOOKS_DIR / book_id / "_raw").glob("*/*/pages.jsonl"))
    if not hits:
        sys.exit(f"Kitab {book_id} belum dimuat turun. Guna: fetch <path>")
    return hits[0].parent


def _ar2int(s: str) -> int:
    return int(s.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")))


def _split_notes(fn: str) -> tuple[dict[str, str], list[str]]:
    """Pecah teks nota kaki satu halaman ikut penanda (¬n)."""
    notes, order, cur = {}, [], None
    for line in fn.split("\n"):
        m = re.match(r'\s*\(¬([٠-٩0-9]+)\)\s*(.*)', line)
        if m:
            cur = m.group(1)
            notes[cur] = m.group(2)
            order.append(cur)
        elif cur:
            notes[cur] += "\n" + line
        elif line.strip():
            notes.setdefault("?", "")
            notes["?"] += line + "\n"
            if "?" not in order:
                order.append("?")
    return notes, order


def _annotate(page: dict) -> tuple[str, int, int, list[int]]:
    """Teks halaman dengan setiap nota kaki diletak tepat selepas baris yang merujuknya."""
    body = _clean((page.get("body") or "").replace("\r", "\n"))
    notes, order = _split_notes(_clean((page.get("footnotes") or "").replace("\r", "\n")))
    used, out, paras = set(), [], []
    for line in body.split("\n"):
        out.append(line)
        m = _PARA.match(line)
        if m:
            paras.append(_ar2int(m.group(1)))
        for k in _MARK.findall(line):
            if k in notes and k not in used:
                used.add(k)
                txt = notes[k].strip().replace("\n", "\n        ")
                out.append(f"    ⟨حاشية {k}⟩ {txt}")
    for k in [k for k in order if k not in used]:
        txt = notes[k].strip().replace("\n", "\n        ")
        label = "تتمة حاشية من الصفحة السابقة" if k == "?" else f"حاشية {k} (لا إحالة لها في المتن)"
        out.append(f"    ⟨{label}⟩ {txt}")
    return "\n".join(out), len(order), len(used), paras


def prep(book_id: str, unit_tokens: int = UNIT_TOKENS) -> Path:
    """Pecah kitab kepada unit bacaan ikut bab/bahagian, setiap unit lengkap dengan nota kaki."""
    raw = _raw_dir(book_id)
    pages = [json.loads(l) for l in open(raw / "pages.jsonl", encoding="utf-8") if l.strip()]
    # sequence_num boleh menyelang-seli bahagian (cth mukadimah & matan): susun ikut
    # bahagian dulu (ikut kemunculan pertama), kemudian nombor halaman.
    first: dict = {}
    for p in sorted(pages, key=lambda p: p.get("sequence_num") or 0):
        first.setdefault(p.get("part"), len(first))
    pages.sort(key=lambda p: (first[p.get("part")], p.get("page_num") or 0,
                              p.get("sequence_num") or 0))
    toc = [json.loads(l) for l in open(raw / "toc.jsonl", encoding="utf-8") if l.strip()]
    titles: dict[int, list[str]] = {}
    for t in toc:
        titles.setdefault(t["page_id"], []).append(t["title_text"])

    blocks = []                     # satu blok = satu halaman
    for p in pages:
        text, n_notes, n_used, paras = _annotate(p)
        heads = titles.get(p["page_id"], [])
        hdr = f"\n[ج{p.get('part')}/ص{p.get('page_num')}]\n"
        hdr += "".join(f"### {h}\n" for h in heads)
        starts_mid = bool(text.strip()) and not _PARA.match(text.lstrip().split("\n")[0])
        blocks.append(dict(part=p.get("part"), page=p.get("page_num"), heads=heads,
                           text=hdr + text, notes=n_notes, used=n_used, paras=paras,
                           starts_mid=starts_mid))

    # Kumpul halaman jadi unit: putus di sempadan bab bila dah cukup saiz;
    # kalau satu bab terlalu besar, putus di halaman yang bermula dengan perenggan baru.
    cap = unit_tokens * CHARS_PER_TOKEN
    units, cur, size = [], [], 0.0
    for b in blocks:
        new_part = cur and b["part"] != cur[-1]["part"]
        at_head = bool(b["heads"])
        if cur and (new_part or (size >= cap and at_head) or
                    (size >= 1.35 * cap and not b["starts_mid"])):
            units.append(cur); cur, size = [], 0.0
        cur.append(b); size += len(b["text"])
    if cur:
        units.append(cur)

    out = STUDY_DIR / book_id
    (out / "units").mkdir(parents=True, exist_ok=True)
    manifest, toc_lines = [], []
    for i, u in enumerate(units, 1):
        name = f"{i:02d}.txt"
        text = "".join(b["text"] for b in u)
        (out / "units" / name).write_text(text, encoding="utf-8")
        paras = [n for b in u for n in b["paras"]]
        heads = [h for b in u for h in b["heads"]]
        info = dict(unit=name, part=u[0]["part"], pages=f"{u[0]['page']}-{u[-1]['page']}",
                    paras=f"{min(paras)}-{max(paras)}" if paras else "",
                    sections=heads, chars=len(text), tokens=_count(text),
                    lines=text.count("\n") + 1,
                    footnotes=sum(b["notes"] for b in u),
                    footnotes_placed=sum(b["used"] for b in u))
        manifest.append(info)
        toc_lines.append(f"## {name} — ج{info['part']} ص{info['pages']}"
                         + (f" — الفقرات {info['paras']}" if paras else ""))
        toc_lines += [f"- {h}" for h in heads] or ["- (تتمة الباب السابق)"]
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    (out / "toc.md").write_text("\n".join(toc_lines) + "\n", encoding="utf-8")
    full = "".join(b["text"] for b in blocks)
    (out / "plain.txt").write_text(_norm(full, keep_lines=True), encoding="utf-8")

    # Semakan liputan
    # Liputan perenggan: semak pada bahagian yang paling banyak perenggan bernombor
    by_part: dict = {}
    for b in blocks:
        by_part.setdefault(b["part"], []).extend(b["paras"])
    all_paras = sorted(max(by_part.values(), key=len)) if by_part else []
    print(f"Unit      : {len(units)} (sasaran ~{unit_tokens:,} token setiap satu)", file=sys.stderr)
    print(f"Halaman   : {len(blocks)} (semua masuk tepat sekali)", file=sys.stderr)
    nn, nu = sum(b["notes"] for b in blocks), sum(b["used"] for b in blocks)
    print(f"Nota kaki : {nn}, {nu} diletak di bawah baris rujukan, {nn - nu} lagi "
          f"(sambungan nota halaman sebelum / tiada penanda) di hujung halaman", file=sys.stderr)
    if all_paras:
        missing = sorted(set(range(1, all_paras[-1] + 1)) - set(all_paras))
        print(f"Perenggan : 1-{all_paras[-1]}, tak dikesan: {missing or 'tiada'}", file=sys.stderr)
    for m in manifest:
        print(f"  {m['unit']} ص{m['pages']:>9} ¶{m['paras']:>10}  ~{m['tokens']:>6,} token  "
              f"{m['footnotes']:>4} nota", file=sys.stderr)
    return out


# ===========================================================================
# verify: semak setiap petikan «...» dalam nota wujud dalam teks asal
# ===========================================================================
def _norm(t: str, keep_lines: bool = False) -> str:
    """Seragamkan ejaan untuk padanan: buang harakat/penanda/nombor, seragamkan hamzah."""
    t = _MARK.sub("", t)
    t = _HARAKAT.sub("", t)
    t = re.sub(r'⟨[^⟩]*⟩|\[ج[^\]]*\]|[«»"“”\'()\[\]{}.,،؛;:!?؟*…=\-–ـ]|[٠-٩0-9]+', " ", t)
    # Hamzah: teks lama sering tanpa hamzah atau dengan kerusi lain (شئ/شيء، مسئلة/مسألة)
    t = re.sub(r'[أإآٱ]', "ا", t).replace("ؤ", "و")
    t = re.sub(r'ئ(?!\S)', "ي", t).replace("ئ", "ا").replace("ء", "")
    t = re.sub(r'ا{2,}', "ا", t).replace("ى", "ي").replace("ة", "ه")
    t = re.sub(r'(?<!\S)ابن(?!\S)', "بن", t)
    t = re.sub(r'(?<!\S)عمن(?!\S)', "عن من", t)
    t = re.sub(r'(?<!\S)مما(?!\S)', "من ما", t)
    if keep_lines:
        return "\n".join(re.sub(r'\s+', ' ', l).strip() for l in t.split("\n"))
    return re.sub(r'\s+', ' ', t).strip()


def _haystack(book_id: str) -> str:
    """Matan bersambung (merentas halaman, tanpa nota) + setiap nota + teks beranotasi."""
    raw = _raw_dir(book_id)
    pages = [json.loads(l) for l in open(raw / "pages.jsonl", encoding="utf-8") if l.strip()]
    first: dict = {}
    for p in sorted(pages, key=lambda p: p.get("sequence_num") or 0):
        first.setdefault(p.get("part"), len(first))
    pages.sort(key=lambda p: (first[p.get("part")], p.get("page_num") or 0))
    body = " ".join(_clean((p.get("body") or "").replace("\r", "\n")) for p in pages)
    notes = " ¦ ".join(_clean((p.get("footnotes") or "").replace("\r", "\n")) for p in pages)
    return _norm(body) + " ¦ " + _norm(notes)


def _nearest(q: str, hay: str) -> str:
    """Cari tetingkap teks sumber yang paling hampir dengan petikan (utk diagnosis)."""
    import difflib
    words = q.split()
    if len(words) < 2:
        return ""
    best, best_r = "", 0.0
    for i in range(len(words) - 1):         # sauh: setiap pasangan kata yang wujud
        anchor = f"{words[i]} {words[i+1]}"
        for m in list(re.finditer(re.escape(anchor), hay))[:40]:
            start = max(0, m.start() - len(" ".join(words[:i])) - 10)
            win = hay[start:start + len(q) + 20]
            r = difflib.SequenceMatcher(None, q, win).ratio()
            if r > best_r:
                best, best_r = win, r
    return f"{best} ({best_r:.0%})" if best_r >= 0.6 else ""


def verify(book_id: str, files: list[str]) -> int:
    hay = _haystack(book_id)
    bad = total = 0
    for f in files:
        for ln, line in enumerate(Path(f).read_text(encoding="utf-8").split("\n"), 1):
            for q in re.findall(r'«([^»]+)»', line):
                pieces = [p for p in re.split(r'\.\.\.|…', q) if len(_norm(p)) >= 3]
                if not pieces:
                    continue
                total += 1
                missing = [p for p in pieces if _norm(p) not in hay]
                if missing:
                    bad += 1
                    print(f"{f}:{ln}: TIADA DALAM TEKS: «{missing[0].strip()}»")
                    near = _nearest(_norm(missing[0]), hay)
                    if near:
                        print(f"    terdekat dalam sumber: {near}")
    print(f"\n{total - bad}/{total} petikan sepadan dengan teks asal.", file=sys.stderr)
    return bad


# ===========================================================================
# merge: himpun bahagian yang sama dari nota semua unit (bahan untuk penyatuan)
# ===========================================================================
SECTIONS = ["النطاق", "خلاصة الأبواب", "خريطة الاستدلال", "المصطلحات والتعريفات",
            "المسائل والأمثلة", "النحو والصرف في كلام المؤلف", "حواشي المحقق اللغوية والنحوية",
            "الغريب والدلالة", "الرسم والضبط واختلاف النسخ", "الأحاديث والآثار والشعر",
            "تعقبات المحقق وآراؤه", "الشخصية والأسلوب", "الإحالات", "فهرس الموضوعات",
            "مواضع مشكلة", "أسئلة اختبار"]


def merge(book_id: str) -> Path:
    base = STUDY_DIR / book_id
    notes = sorted((base / "notes").glob("*.md"))
    if not notes:
        sys.exit("Tiada nota unit dalam study/<id>/notes/")
    out = base / "sections"
    out.mkdir(exist_ok=True)
    buckets: dict[int, list[str]] = {i: [] for i in range(len(SECTIONS))}
    for f in notes:
        text = _HARAKAT.sub("", f.read_text(encoding="utf-8"))   # jaring keselamatan: tanpa harakat
        f.write_text(text, encoding="utf-8")
        parts = re.split(r'^##\s*([٠-٩0-9]+)\s*[.\-]\s*.*$', text, flags=re.M)
        found = set()
        for num, body in zip(parts[1::2], parts[2::2]):
            i = _ar2int(num)
            if 0 <= i < len(SECTIONS):
                found.add(i)
                buckets[i].append(f"\n### الوحدة {f.stem}\n{body.strip()}\n")
        miss = [SECTIONS[i] for i in range(len(SECTIONS)) if i not in found]
        if miss:
            print(f"  {f.name}: bahagian tiada -> {', '.join(miss)}", file=sys.stderr)
    for i, name in enumerate(SECTIONS):
        p = out / f"{i:02d}_{name.replace(' ', '_')}.md"
        p.write_text(f"## {name}\n" + "".join(buckets[i]), encoding="utf-8")
        print(f"  {p.name:45s} ~{_count(p.read_text(encoding='utf-8')):>7,} token", file=sys.stderr)

    # Indeks berkategori: entri nahu (٥ + ٦) ikut وسم, glosari ikut abjad, riwayat ikut jenis
    def entries(i: int) -> list[tuple[str, str]]:
        rows = []
        for block in buckets[i]:
            unit = re.search(r'### الوحدة (\S+)', block).group(1)
            for line in block.split("\n"):
                line = re.sub(r'^\s*(?:[-*]|[0-9٠-٩]+[.)-])\s*', '', line).strip()
                if line and not line.startswith(("###", "الصيغة", "لا يوجد")):
                    rows.append((unit, line))
        return rows

    idx = out / "indeks"
    idx.mkdir(exist_ok=True)
    tagged: dict[str, list[str]] = {}
    for i, src in ((5, "متن"), (6, "حاشية")):
        for unit, line in entries(i):
            m = re.match(r'\[([^\]]+)\]\s*', line)
            tag = m.group(1) if m else "بلا وسم"
            if m and (tag in ("المحقق", "تحليل القارئ") or re.match(r'ص[0-9٠-٩]', tag)):
                tag = "بلا وسم"
            tagged.setdefault(tag, []).append(f"- ({src}، و{unit}) {line[m.end():] if m and tag != 'بلا وسم' else line}")
    for tag, rows in sorted(tagged.items(), key=lambda kv: -len(kv[1])):
        (idx / f"نحو_{tag.replace(' ', '_')}.md").write_text(
            f"## {tag}\n\nعدد المداخل: {len(rows)}\n\n" + "\n".join(rows) + "\n", encoding="utf-8")
        print(f"  indeks/نحو_{tag}: {len(rows)}", file=sys.stderr)

    words = sorted(entries(7), key=lambda r: _norm(r[1].split("|")[0]))
    (idx / "الغريب_مرتبا.md").write_text(
        "## الغريب مرتبا على الحروف\n\n" + "\n".join(f"- {l} (و{u})" for u, l in words) + "\n",
        encoding="utf-8")
    kinds: dict[str, list[str]] = {}
    for unit, line in entries(9):
        m = re.match(r'\[(حديث|أثر|شعر|آية)\]', line)
        kinds.setdefault(m.group(1) if m else "أخرى", []).append(f"- (و{unit}) {line}")
    (idx / "الروايات.md").write_text(
        "".join(f"## {k}\n\nعدد المداخل: {len(v)}\n\n" + "\n".join(v) + "\n\n" for k, v in kinds.items()),
        encoding="utf-8")
    print(f"  indeks/الغريب: {len(words)}  الروايات: "
          + ", ".join(f"{k} {len(v)}" for k, v in kinds.items()), file=sys.stderr)
    return out


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

    p = sub.add_parser("prep", help="pecah kitab jadi unit bacaan (matan + nota kaki di tempatnya)")
    p.add_argument("book_id")
    p.add_argument("--tokens", type=int, default=UNIT_TOKENS, help="saiz sasaran satu unit")

    p = sub.add_parser("verify", help="semak petikan «...» dalam fail nota wujud dalam teks asal")
    p.add_argument("book_id")
    p.add_argument("files", nargs="+")

    p = sub.add_parser("merge", help="himpun bahagian sama dari nota semua unit")
    p.add_argument("book_id")

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

    elif a.cmd == "prep":
        out = prep(a.book_id, a.tokens)
        print(f"Siap -> {out}")

    elif a.cmd == "merge":
        print(f"Siap -> {merge(a.book_id)}")

    elif a.cmd == "verify":
        sys.exit(1 if verify(a.book_id, a.files) else 0)


if __name__ == "__main__":
    main()
