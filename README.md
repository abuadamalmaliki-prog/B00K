# B00K
1'TS JUST B00K

## Exploring the Shamela 4 library with Python

[`shamela.py`](shamela.py) lets you browse and download books from the
[Shamela4_Full_DB](https://huggingface.co/datasets/AuthenticIlm/Shamela4_Full_DB)
dataset on Hugging Face. It holds 8,589 books in 40 categories, about 19 GB in all.

```bash
pip install -r requirements.txt
```

### How the dataset is laid out

```
_meta/book_metadata.parquet        catalogue of all books (1.2 MB) ← start here
_meta/{authors,categories,quran_verses,narrators,root_dictionary,
       hadith_xrefs,tafsir_xrefs,page_isnads}.parquet
NN__<category>/<book_id>__<slug>/  one folder per book
    book_metadata.json             title, authors, edition card (betaka_text)
    toc.jsonl                      headings: page_id, parent_id → title_id
    pages.jsonl                    one page per line: body, footnotes, part, page_num
```

Things worth knowing:
- Folder names start with the dataset's `book_id`. This is **not** the
  shamela.ws id, which is stored as `shamela_id`. The Wasitiyya in this repo
  has `shamela_id` 22665 and `book_id` 5946.
- Page text uses `\r` for line breaks and contains a little HTML. Headings look
  like `<span data-type="title" id=toc-N>`, where N is the TOC entry's
  `shamela_title_id`.
- `part` is the volume and `page_num` is the printed page number.
- The `book_id` values in `hadith_xrefs` and `tafsir_xrefs` are shamela ids.
- A death year of `99999` means unknown.

The script never downloads the whole dataset. It reads the catalogue to find
books and downloads only the books you open. Files are cached in
`.shamela_cache/`; set `SHAMELA_CACHE` to change that. Setting `HF_TOKEN` gives
higher rate limits.

### Command line

```bash
python shamela.py categories                                  # categories and book counts
python shamela.py search --title الواسطية --author "ابن تيمية"
python shamela.py search --category 16 --died-before 700      # early Shafi'i fiqh
python shamela.py info 5946                                   # edition card and stats
python shamela.py toc 5946                                    # nested table of contents
python shamela.py read 5946 --page 64                         # printed page 64
python shamela.py read 3226 --page 10 --part 2                # vol. 2, p. 10
python shamela.py grep 5946 "صفة المحبة"                      # ignores diacritics
python shamela.py export 5946 out.mARkdown [--no-tashkeel]    # OpenITI mARkdown
```

### From Python

```python
from shamela import Library

lib = Library()
lib.search(title="تحفة المحتاج")                 # pandas DataFrame
book = lib.book(5946)                            # or lib.book_by_shamela_id(22665)
book.print_toc(max_depth=1)
page = book.find_page(64)
print(book.page_text(page, keep_tashkeel=False))
for ref, snippet in book.grep("الإيمان"):
    print(ref, snippet)
book.to_openiti("العقيدة_الواسطية.mARkdown")

quran = lib.meta("quran_verses")                 # any _meta table
```
