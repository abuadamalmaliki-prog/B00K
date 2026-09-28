# Khizana (خِزانة) — Shamela as an OpenITI-style digital library

A searchable library of the 8,589 books in
[AuthenticIlm/Shamela4_Full_DB](https://huggingface.co/datasets/AuthenticIlm/Shamela4_Full_DB).
Any book downloads as **one OpenITI mARkdown file**: metadata header, table of contents, full text,
footnotes and page markers together.

## The site (`site/`)

A static page with no server or database. It needs only `index.html` and `catalog.json` (1.9 MB).

- Search by title or author, with Arabic normalization: harakat, hamza forms, ة/ه and ى/ي
  are ignored.
- Filter by category (40), century of death (Hijri, including pre-Islamic poets) and book type.
- Browse by author.
- Each book page shows its card (بطاقة الكتاب), metadata, OpenITI URI and a clickable
  table of contents, plus a page-by-page reader.
- **Download one file (.mARkdown):** the browser fetches the book from Hugging Face and
  converts it on the spot.
- **JSON bundle:** metadata, manifest, TOC and pages together in one file.

### Put it online (one-time)

1. Merge this branch into `main`.
2. On GitHub, open **Settings → Pages** and set **Source** to **GitHub Actions**.
3. The workflow `.github/workflows/library-pages.yml` publishes `library/site` to
   `https://abuadamalmaliki-prog.github.io/B00K/`.

To try it locally, run `cd library/site && python3 -m http.server`, then open http://localhost:8000.

## The mARkdown file

```
######OpenITI#

#META# Header#Begin#
#META# 000.BookURI# 0728IbnTaymiyya.Wasitiyya.Shamela0000000-ara1
#META# 000.BookTitle# …
#META# 010.Author.author# … (ت ٧٢٨ هـ) [author_id …]
#META# 020.Category# العقيدة
#META# 040.Card01# الكتاب: …          ← the Shamela card, line by line
#META# 090.SHA256.pages.jsonl# …      ← checksums of the source files
#META# Header#End#

### | باب …                            ← headings at their real place; || for level 2, …
# paragraph                           ← one paragraph per line (Shamela's \r breaks kept)
# ____________________
# (¬١) footnote                       ← the page's footnotes
PageV01P023                           ← OpenITI page marker, after the page
```

URIs follow the OpenITI pattern `{death AH}{Author}.{Title}.Shamela{id}-ara1`. The Latin part is
an automatic, unvocalized transliteration, so treat it as an identifier, not a scholarly
romanization. `0000` means the author is living or the death date is unknown.

## Scripts

| Script | What it does |
| --- | --- |
| `build_catalog.py` | Rebuilds `site/catalog.json` from the dataset's `_meta` parquet tables and folder listing (`pip install pyarrow`) |
| `shamela2openiti.py 1009 2739` | Converts books by id to `.mARkdown` |
| `shamela2openiti.py --dir folder/` | Converts a local copy of one book folder |
| `shamela2openiti.py --all --out books/` | Converts the whole library; the input is about 19 GB, so run it on a machine with the disk for it |

The Python converter and the in-browser converter produce byte-identical files.

Texts: al-Maktaba al-Shamila, version 4. Critical editions remain the property of their editors
and publishers; for personal and research use.
