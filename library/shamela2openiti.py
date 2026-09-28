"""Convert a Shamela4_Full_DB book into one OpenITI mARkdown file.

    python3 shamela2openiti.py BOOK_ID [BOOK_ID ...]        # fetch from Hugging Face
    python3 shamela2openiti.py --dir path/to/book_folder     # local copy of one book folder
    python3 shamela2openiti.py --all --out books/            # the whole library (~19 GB of input)

The file holds everything in one place:
  * #META# header: URI, title, authors with death dates, category, book type, edition card
    (betaka), Shamela link, page/TOC counts and the source checksums
  * the full text, one paragraph per "# " line (Shamela's \\r breaks become real breaks)
  * headings from the table of contents at their true place ("### |", "### ||", …)
  * OpenITI page markers after each page (PageV01P023) and the page's footnotes

The same conversion runs in the browser in site/index.html; keep the two in step.
"""
import argparse, html, json, os, re, sys, urllib.parse, urllib.request

HF = 'https://huggingface.co/datasets/AuthenticIlm/Shamela4_Full_DB/resolve/main/'
HERE = os.path.dirname(os.path.abspath(__file__))

# ------------------------------------------------------------------ URIs
TRANS = {'ا': 'a', 'أ': 'a', 'إ': 'i', 'آ': 'a', 'ٱ': 'a', 'ء': '', 'ؤ': 'u', 'ئ': 'y', 'ب': 'b', 'ت': 't',
         'ث': 'th', 'ج': 'j', 'ح': 'h', 'خ': 'kh', 'د': 'd', 'ذ': 'dh', 'ر': 'r', 'ز': 'z', 'س': 's', 'ش': 'sh',
         'ص': 's', 'ض': 'd', 'ط': 't', 'ظ': 'z', 'ع': 'c', 'غ': 'gh', 'ف': 'f', 'ق': 'q', 'ك': 'k', 'ل': 'l',
         'م': 'm', 'ن': 'n', 'ه': 'h', 'ة': 'a', 'و': 'w', 'ي': 'y', 'ى': 'a'}
WORDS = {'ابن': 'Ibn', 'بن': 'b', 'أبو': 'Abu', 'ابو': 'Abu', 'أبي': 'Abi', 'عبد': 'Cabd', 'الله': 'Allah', 'محمد': 'Muhammad',
         'أحمد': 'Ahmad', 'علي': 'Cali', 'عمر': 'Cumar', 'عثمان': 'Cuthman', 'تيمية': 'Taymiyya', 'القيم': 'Qayyim'}


def translit(text, max_words=3):
    """Rough consonantal transliteration for OpenITI-style URIs (not a scholarly romanization)."""
    text = re.sub(r'[ً-ٰٟـ]', '', text or '')
    out = []
    for w in re.findall(r'[ء-يٱ]+|[A-Za-z0-9]+', text):
        if w in WORDS:
            out.append(WORDS[w]); continue
        if w.startswith('ال') and len(w) > 3:
            w = w[2:]
        t = ''.join(TRANS.get(c, c if c.isascii() else '') for c in w)
        if t:
            out.append(t[0].upper() + t[1:])
        if len(out) >= max_words:
            break
    return ''.join(out) or 'Unknown'


def death_ah(v):
    """Shamela stores Hijri years; negative values are years before the Hijra
    (e.g. -76 for Imru' al-Qays, d. 545 CE); 99999 means living or unknown."""
    if v is None or v >= 9999 or v == 0:
        return None
    return v


def death_label(ah):
    return f'{-ah} ق هـ' if ah < 0 else f'{ah} هـ'


def book_uri(meta):
    d = death_ah(meta.get('main_author_death_hijri'))
    author = translit(meta.get('main_author_name_ar'), 2)
    title = translit(re.split(r'\s[-–]\s|\(|ط\s', meta.get('title_ar') or '')[0], 3)
    return f"{max(d or 0, 0):04d}{author}.{title}.Shamela{meta['shamela_id']:07d}-ara1"


# ------------------------------------------------------------------ text
SPAN = re.compile(r"<span[^>]*data-type=['\"]title['\"][^>]*id=['\"]?toc-(\d+)['\"]?[^>]*>(.*?)</span>", re.S)
TAG = re.compile(r'<[^>]+>')
IMG = re.compile(r'<img[^>]*>', re.I)


def clean(s):
    s = IMG.sub(' [صورة] ', s)
    s = re.sub(r'<hr\s*/?>', '\r', s, flags=re.I)
    s = re.sub(r'</(p|div|tr|li|table)>|<br\s*/?>', '\r', s, flags=re.I)
    s = re.sub(r'</t[dh]>', ' | ', s, flags=re.I)
    s = TAG.sub('', s)
    return html.unescape(s)


def paragraphs(s):
    for line in clean(s).replace('\r\n', '\r').replace('\n', '\r').split('\r'):
        line = re.sub(r'[ \t ]+', ' ', line).strip()
        if line:
            yield line


def toc_levels(toc):
    by_id = {t['title_id']: t for t in toc}
    level = {}
    for t in toc:
        n, p, seen = 1, t.get('parent_id'), set()
        while p in by_id and p not in seen:
            seen.add(p); n += 1; p = by_id[p].get('parent_id')
        level[t['title_id']] = min(n, 6)
    return level


def volume(part):
    if part in (None, '', 0):
        return 1
    m = re.search(r'\d+', str(part).translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')))
    return int(m.group()) if m else 1


def to_markdown(meta, toc, pages, manifest=None):
    level = toc_levels(toc)
    by_shamela = {t.get('shamela_title_id'): t for t in toc}
    by_page = {}
    for t in toc:
        by_page.setdefault(t.get('page_id'), []).append(t)
    uri = book_uri(meta)
    out = ['######OpenITI#', '', '#META# Header#Begin#']
    m = lambda k, v: out.append(f'#META# {k}# {v}') if v not in (None, '', []) else None
    m('000.BookURI', uri)
    m('000.BookTitle', meta.get('title_ar'))
    m('000.Source', f"https://shamela.ws/book/{meta['shamela_id']}")
    m('000.ShamelaID', meta.get('shamela_id'))
    m('000.DatasetBookID', meta.get('book_id'))
    for a in meta.get('authors') or []:
        d = death_ah(a.get('death_hijri'))
        m(f"010.Author.{a.get('role', 'author')}", f"{a.get('name_ar')}" + (f" (ت {death_label(d)})" if d else '') + f" [author_id {a.get('author_id')}]")
    m('010.AuthorDiedAH', death_ah(meta.get('main_author_death_hijri')))
    m('020.Category', meta.get('category_name_ar'))
    m('020.BookType', meta.get('book_type_label'))
    m('020.Printed', 'yes' if meta.get('printed') else 'no')
    m('020.Volumes', meta.get('volume_count_observed') or None)
    m('030.PageCount', len(pages))
    m('030.TocCount', len(toc))
    for i, line in enumerate(paragraphs(meta.get('betaka_text') or '')):
        m(f'040.Card{i + 1:02d}', line)
    if manifest:
        m('090.Extracted', manifest.get('extracted_at'))
        m('090.Snapshot', manifest.get('snapshot_id'))
        for f in manifest.get('files', []):
            m(f"090.SHA256.{f['path']}", f['sha256'])
    m('090.ConvertedBy', 'B00K library/shamela2openiti.py')
    out += ['#META# Header#End#', '']

    def heading(t):
        out.extend(['', f"### {'|' * level.get(t['title_id'], 1)} {t['title_text'].strip()}", ''])

    done = set()
    for p in sorted(pages, key=lambda p: (p.get('sequence_num') or 0, p.get('page_id') or 0)):
        body = p.get('body') or ''
        inline = {int(n) for n, _ in SPAN.findall(body)}
        for t in by_page.get(p.get('page_id'), []):       # headings with no marker in the text
            if t.get('shamela_title_id') not in inline and t['title_id'] not in done:
                heading(t); done.add(t['title_id'])
        pos = 0
        for mt in SPAN.finditer(body):
            for para in paragraphs(body[pos:mt.start()]):
                out.append('# ' + para)
            t = by_shamela.get(int(mt.group(1)))
            if t and t['title_id'] not in done:
                heading(t); done.add(t['title_id'])
            else:
                out.extend(['', '### | ' + clean(mt.group(2)).strip(), ''])
            pos = mt.end()
        for para in paragraphs(body[pos:]):
            out.append('# ' + para)
        fn = list(paragraphs(p.get('footnotes') or ''))
        if fn:
            out.append('# ____________________')
            out.extend('# ' + f for f in fn)
        out.extend([f"PageV{volume(p.get('part')):02d}P{(p.get('page_num') or 0):03d}", ''])
    return uri, '\n'.join(out) + '\n'


# ------------------------------------------------------------------ io
def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'B00K-library'})) as r:
        return r.read().decode('utf-8')


def jsonl(text):
    return [json.loads(l) for l in text.splitlines() if l.strip()]


def load_book(path=None, folder=None):
    """path: 'NN__category/ID__slug' on Hugging Face; folder: a local copy."""
    if folder:
        rd = lambda f: open(os.path.join(folder, f), encoding='utf-8').read()
    else:
        base = HF + urllib.parse.quote(path) + '/'
        rd = lambda f: fetch(base + f)
    meta = json.loads(rd('book_metadata.json'))
    try:
        manifest = json.loads(rd('manifest.json'))
    except Exception:
        manifest = None
    return meta, jsonl(rd('toc.jsonl')), jsonl(rd('pages.jsonl')), manifest


def catalog():
    return json.load(open(os.path.join(HERE, 'site', 'catalog.json'), encoding='utf-8'))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('ids', nargs='*', type=int, help='dataset book_id values')
    ap.add_argument('--dir', help='local book folder instead of downloading')
    ap.add_argument('--all', action='store_true', help='convert every book in the catalog')
    ap.add_argument('--out', default='.', help='output folder')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    jobs = []
    if a.dir:
        jobs.append((None, a.dir))
    else:
        cat = catalog()
        paths = {b[0]: b[-1] for b in cat['books']}
        ids = list(paths) if a.all else a.ids
        if not ids:
            ap.error('give BOOK_IDs, --dir or --all')
        jobs = [(paths[i], None) for i in ids]
    for path, folder in jobs:
        uri, text = to_markdown(*load_book(path, folder))
        dest = os.path.join(a.out, uri + '.mARkdown')
        if a.all and os.path.exists(dest):
            continue
        open(dest, 'w', encoding='utf-8').write(text)
        print(dest, f'{len(text) // 1024} KB', file=sys.stderr)


if __name__ == '__main__':
    main()
