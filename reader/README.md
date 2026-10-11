# reader — processing a whole book with OCaml, C++ and Python

Every line, sentence and word of a book exported by `../shamela.py` goes
through three stages. Each language does the part it is good at:

| Stage | Language | What it does |
|---|---|---|
| `parse.ml` | OCaml | Parses OpenITI mARkdown into typed units (prose sentence, poetry verse, **matn verse**, footnote, heading). Tracks the volume → heading tree → page of every unit. Never splits a sentence inside ﴿…﴾. |
| `index.cpp` | C++ | Decodes UTF-8 and normalises Arabic (diacritics, hamza forms, ى/ة). Light-stems every word, builds an inverted index, finds each section's distinctive terms (TF-IDF) and ranks passages for questions (BM25). |
| `graph.py` | Python | Links sections (cross-references, shared verses/hadith, vocabulary, order) and runs graph search (`explore`). |
| `read.py` | Python | Runs the pipeline. Checks every Qur'an citation against the mushaf in the dataset, extracts the commented poem and checks it against a standalone edition, writes the book map, answers questions. |

```bash
python read.py build ../لوامع_الأنوار_البهية.mARkdown   # compile + process (≈1 s)
python read.py stats
python read.py quran            # → quran_report.txt
python read.py matn             # → matn.txt   (--against 2218 to check vs. the standalone poem)
python read.py map              # → map.md
python read.py ask "حكم التقليد في أصول الدين" -k 5      # plain BM25
python read.py explore "رؤية المؤمنين ربهم" --top 8      # expansion + section graph
```

Requires `ocamlopt` (OCaml ≥ 4.14, stdlib + `str`), `g++` (C++17), Python 3
with `pandas`/`huggingface_hub`. Intermediate files go to `build/`, which git
ignores.

## Beyond keyword retrieval: `explore`

`ask` is plain BM25. It only finds passages that use the query's words, so a
passage that continues the argument in other words is missed. `explore`
(`graph.py`) fixes that with links built from the whole book, none of which
depend on the query:

| Link | Built from | Count |
|---|---|---|
| crossref | the author's own pointers (كما تقدم، وقد تقدم في…، وسيأتي، ويأتي الكلام…), each resolved to the earlier/later section it most likely means | 247 |
| quran | two sections cite the same verse (found by the Qur'an check) | 282 |
| hadith | two sections quote the same hadith «…» | 20 |
| lexical | similar distinctive vocabulary (TF-IDF cosine, C++) | 595 |
| sequence | neighbouring / parent sections | 367 |

The query is first expanded with words this book uses alongside each query
word (PPMI, computed in C++), weighted by how specific the word is. For
رؤية the expansion is لمحجوبون، تضارون، ناضرة، المطففين. Those matches seed a
personalised PageRank over the section graph. Each result says whether it
matched directly or was reached through a link, names the link, and shows the
sentence that carries it.

Example: `explore "رؤية المؤمنين ربهم"` also returns صفة الكلام (ج1 ص132), in the
other volume, through the shared verses 7:143 (لن تراني) and 42:51. It returns
مدارك العلوم (ج2 ص439), where النظر is defined as الانتظار والرؤية, through 75:22.
It returns the Prophet's-vision passage (ج2 ص284) through the author's own
"تقدم الكلام على رؤية النبي ﷺ…". Plain BM25 finds none of the three.

Limits: the links are lexical and citation-based. A passage linked to the
topic only by meaning (no shared words, citations or pointers) can still be
missed. Common words also leak through, e.g. المؤمنين matches "أمير المؤمنين".

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
