# reader — processing a whole book with OCaml, C++ and Python

Every line, sentence and word of a book exported by `../shamela.py` goes
through three stages. Each language does the part it is good at:

| Stage | Language | What it does |
|---|---|---|
| `parse.ml` | OCaml | Parses OpenITI mARkdown into typed units (prose sentence, poetry verse, **matn verse**, footnote, heading). Tracks the volume → heading tree → page of every unit. Never splits a sentence inside ﴿…﴾. |
| `index.cpp` | C++ | Decodes UTF-8 and normalises Arabic (diacritics, hamza forms, ى/ة). Light-stems every word, builds an inverted index, finds each section's distinctive terms (TF-IDF) and ranks passages for questions (BM25). |
| `read.py` | Python | Runs the pipeline. Checks every Qur'an citation against the mushaf in the dataset, extracts the commented poem and checks it against a standalone edition, writes the book map, answers questions. |

```bash
python read.py build ../لوامع_الأنوار_البهية.mARkdown   # compile + process (≈1 s)
python read.py stats
python read.py quran            # → quran_report.txt
python read.py matn             # → matn.txt   (--against 2218 to check vs. the standalone poem)
python read.py map              # → map.md
python read.py ask "حكم التقليد في أصول الدين" -k 5
```

Requires `ocamlopt` (OCaml ≥ 4.14, stdlib + `str`), `g++` (C++17), Python 3
with `pandas`/`huggingface_hub`. Intermediate files go to `build/`, which git
ignores.

## Results for لوامع الأنوار البهية

- **Size:** 921 pages, 2 volumes, 292 headings, 280,453 words. These become
  8,473 units, of which 201 are verses of the poem being explained, and
  19,972 distinct word stems.
- **Qur'an citations:** the book has 1,082 citations in the form ﴿…﴾ [سورة: آية].
  - 1,063 match the mushaf at the reference given. 11 of these differ
    slightly in wording and 2 point to the neighbouring verse.
  - 16 are **merged-surah slips in the edition**: verses from different
    surahs are chained in one ﴿…﴾ while the reference names only the last
    surah. Example: ﴿ورتل القرآن ترتيلا - ولا تعجل بالقرآن…﴾ [طه: ٤ - ١١٤],
    where the first verse is al-Muzzammil 73:4.
  - 3 are only a few letters long (e.g. حقا, طه) and too short to locate.
  - The script learns how the book names each surah from the citations
    themselves; no list of surah names is hard-coded.
- **The poem (الدرة المضية):** 195 of the 206 verses in the standalone
  edition (dataset book 2218) are found quoted whole in the commentary. The
  other 11 are quoted only by half-line, or sit in a corrupted passage of the
  source (ج1 ص320, which contains junk text and broken lines).
