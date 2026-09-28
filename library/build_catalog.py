"""Build site/catalog.json from the Shamela4_Full_DB metadata tables.

    pip install pyarrow
    python3 build_catalog.py

Reads _meta/book_metadata.parquet, _meta/categories.parquet and _meta/authors.parquet, and lists
the dataset's folders so every book knows where its files live on Hugging Face.
"""
import io, json, os, re, sys, time, urllib.parse, urllib.request
import pyarrow.parquet as pq

REPO = 'AuthenticIlm/Shamela4_Full_DB'
RESOLVE = f'https://huggingface.co/datasets/{REPO}/resolve/main/'
API = f'https://huggingface.co/api/datasets/{REPO}/tree/main/'
HERE = os.path.dirname(os.path.abspath(__file__))


def get(url):
    for attempt in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'B00K-library'}), timeout=120) as r:
                return r.read(), r.headers
        except Exception as e:
            if attempt == 4:
                raise
            time.sleep(2 ** attempt)


def table(name):
    data, _ = get(RESOLVE + '_meta/' + name)
    return pq.read_table(io.BytesIO(data)).to_pylist()


def list_dirs(path):
    """All entries directly under `path`, following the API's pagination."""
    url, out = API + urllib.parse.quote(path), []
    while url:
        data, headers = get(url)
        out += json.loads(data)
        m = re.search(r'<([^>]+)>;\s*rel="next"', headers.get('Link', '') or '')
        url = m.group(1) if m else None
    return out


def main():
    books = table('book_metadata.parquet')
    cats = table('categories.parquet')
    print(f'{len(books)} books, {len(cats)} categories', file=sys.stderr)
    print('columns:', sorted(books[0].keys()), file=sys.stderr)

    paths = {}
    for d in list_dirs(''):
        if d['type'] != 'directory' or d['path'].startswith('_'):
            continue
        for b in list_dirs(d['path']):
            m = re.match(r'(\d+)__', b['path'].split('/')[-1])
            if b['type'] == 'directory' and m:
                paths[int(m.group(1))] = b['path']
        print(f"  {d['path']}: {len(paths)} folders so far", file=sys.stderr)

    rows, missing = [], 0
    for b in books:
        p = paths.get(b['book_id'])
        if not p:
            missing += 1
            continue
        death = b.get('main_author_death_hijri')
        # negative = years before the Hijra (e.g. -76 for Imru' al-Qays); 99999 = living/unknown
        if death is not None and (death >= 9999 or death == 0):
            death = None
        rows.append([
            b['book_id'], b.get('shamela_id'), (b.get('title_ar') or '').strip(),
            (b.get('main_author_name_ar') or '').strip(), b.get('main_author_id'), death,
            b.get('category_id'), b.get('book_type_label') or '', int(bool(b.get('printed'))),
            int(bool(b.get('is_hidden'))), p,
        ])
    rows.sort(key=lambda r: (r[6] or 0, r[5] or 99999, r[2]))
    counts = {}
    for r in rows:
        counts[r[6]] = counts.get(r[6], 0) + 1
    cat_rows = []
    for c in cats:
        cid = c.get('category_id', c.get('id'))
        name = c.get('category_name_ar') or c.get('name_ar') or c.get('name')
        if cid in counts:
            cat_rows.append([cid, name, counts[cid]])
    cat_rows.sort()
    out = {
        'source': f'https://huggingface.co/datasets/{REPO}',
        'resolve': RESOLVE,
        'generated': time.strftime('%Y-%m-%d'),
        'fields': ['book_id', 'shamela_id', 'title', 'author', 'author_id', 'death_ah', 'category_id',
                   'book_type', 'printed', 'hidden', 'path'],
        'categories': cat_rows,
        'books': rows,
    }
    os.makedirs(os.path.join(HERE, 'site'), exist_ok=True)
    dest = os.path.join(HERE, 'site', 'catalog.json')
    json.dump(out, open(dest, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(f'wrote {dest}: {len(rows)} books, {missing} without a folder, {os.path.getsize(dest) // 1024} KB', file=sys.stderr)


if __name__ == '__main__':
    main()
