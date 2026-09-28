# Books: AI-ready editions

Six books rebuilt from [Shamela4_Full_DB](https://huggingface.co/datasets/AuthenticIlm/Shamela4_Full_DB)
by `library/shamela2ai.py`. They replace the `.mARkdown` files in the repo root, whose line breaks
were lost.

| File | Book | Author | Scope | Pages | Words |
| --- | --- | --- | --- | ---: | ---: |
| `العقيدة_الواسطية.md` | العقيدة الواسطية (ت أشرف عبد المقصود) | ابن تيمية (ت ٧٢٨) | complete | 72 | 6,116 |
| `خلق_أفعال_العباد.md` | خلق أفعال العباد | البخاري (ت ٢٥٦) | complete | 295 | 23,436 |
| `شرح_العقيدة_الطحاوية.md` | شرح العقيدة الطحاوية (ط الرسالة) | ابن أبي العز (ت ٧٩٢) | complete, 2 vols | 797 | 125,200 |
| `شفاء_العليل.md` | شفاء العليل (ط المعرفة) | ابن القيم (ت ٧٥١) | complete | 333 | 161,925 |
| `مجموع_الفتاوى_ج08_القدر.md` | مجموع الفتاوى | ابن تيمية (ت ٧٢٨) | vol. 8 (القدر) | 548 | 106,992 |
| `تحفة_المحتاج_ج01.md` | تحفة المحتاج بحواشي الشرواني والعبادي | ابن حجر الهيتمي (ت ٩٧٤) | vol. 1 | 506 | 428,806 |
| `درء_تعارض_العقل_والنقل.md` | درء تعارض العقل والنقل (ت محمد رشاد سالم) | ابن تيمية (ت ٧٢٨) | complete, 10 vols | 4,031 | 670,546 |

**Large books:** درء تعارض العقل والنقل is about 1.2 million tokens, more than any AI can read at
once. `درء_تعارض_العقل_والنقل.volumes/v01.md … v10.md` hold one volume each (80k–155k tokens),
each with its own front matter and reading guide, so a single volume fits in one context window.
For questions across the whole book, use the `.chunks.jsonl` with a retrieval tool.

## What's in each `.md`

1. **YAML front matter:** title and full title, author (name, full name, death AH and approximate CE),
   editor, publisher, edition, category, scope, page range, statistics, the text layers present, and
   provenance (Shamela URL, dataset id, snapshot, SHA-256 of the source files). Any YAML parser reads it.
2. **Reading guide:** a short blockquote explaining every marker, so a model reading the file cold
   knows the conventions.
3. **Contents:** the book's own table of contents in reading order, nested, with links and page
   references.
4. **Text:**
   - `## / ### / ####` headings, each with a stable anchor such as `{#s34}`.
   - One paragraph per block.
   - `[[p53]]`, or `[[v8 p123]]` for multi-volume works, at the **start** of every printed page,
     so any passage can be cited.
   - Anything that isn't the main text (the two ḥawāshī in Tuhfa, editors' notes elsewhere) sits in
     a labelled blockquote: `> **[الحاشية الأولى]**`.

The text is faithful to the source: harakat are kept, it is NFC-normalized, and tatweel and HTML are
removed. Heading depth comes from the dataset where it was recorded and is otherwise inferred from the
heading words (باب › فصل › topic); the front matter says so.

## `.chunks.jsonl`

The same text split for retrieval (RAG), embedding or batch analysis: one JSON object per line.

```json
{"id": "shamela-22665#00004", "book": "shamela-22665", "title": "…", "author": "ابن تيمية",
 "section": ["الباب الأول: الإيمان بالله تعالى", "الفصل الأول: …"],
 "pages": ["p57", "p59"], "layer": "main", "chars": 2310, "text": "…"}
```

- Chunks follow section boundaries. They are at most about 6,000 characters, and sections under
  1,200 characters merge with the next one.
- Chunks never mix layers, so a gloss is never confused with the text it comments on
  (`layer`: `main`, `s0`, `s1`, `fn`).

## Rebuild or add books

```bash
cd library
python3 shamela2ai.py 22665 --shamela --name العقيدة_الواسطية --out ../books
python3 shamela2ai.py 7289 --shamela --volumes 8 --name مجموع_الفتاوى_ج08_القدر --out ../books
```

Any of the 8,589 books can be converted the same way; find ids in the Khizana library
(`library/site`).
