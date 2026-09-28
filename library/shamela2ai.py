"""Convert a Shamela4_Full_DB book into Markdown built for AI reading and analysis.

    python3 shamela2ai.py BOOK_ID [--volumes 8] [--name slug] [--out books/] [--dir local_folder]

Output, per book:
  NAME.md            YAML front matter (bibliography, provenance, stats, reading guide), contents list,
                     real Markdown headings, one paragraph per block, [[v1 p23]] page markers at the
                     start of every page, and each page's other text layers (glosses, editor's notes)
                     in labelled blockquotes, never mixed into the main text
  NAME.chunks.jsonl  the same text in section-sized chunks with heading path, pages and layer,
                     ready for embedding / retrieval

Text is faithful to Shamela: harakat kept, NFC-normalized, tatweel and HTML removed,
Shamela's \\r line breaks turned into paragraphs.
"""
import argparse, json, os, re, sys, unicodedata
from datetime import date
from shamela2openiti import HF, book_uri, clean, death_ah, jsonl, load_book, SPAN, catalog

CHUNK_CHARS = 6000   # upper bound per chunk
MIN_CHUNK = 1200     # sections shorter than this merge into the next one
TATWEEL = re.compile('ـ')
LAYER_TAG = re.compile(r'<hr\s*/?>\s*<s(\d)>|<s(\d)>')


def norm(s):
    s = unicodedata.normalize('NFC', s)
    s = TATWEEL.sub('', s)
    return re.sub(r'[ \t ]+', ' ', s).strip()


def paras(s):
    return [p for p in (norm(x) for x in clean(s).replace('\r\n', '\r').replace('\n', '\r').split('\r')) if p]


TOP = re.compile(r'^(ال)?(باب|كتاب|جزء|مجلد|قسم)(\s|$|:)')
EDGE = re.compile(r'^(ال)?(مقدمة|خاتمة|تقديم|تمهيد|فهرس)')
MID = re.compile(r'^(ال)?(فصل|مبحث|مطلب)(\s|$|:)')


def infer_levels(toc):
    """Heading depth. The dataset keeps only some parent links, so the rest is inferred:
    باب/كتاب/جزء/قسم open a top-level section, فصل/مبحث/مطلب sit one level below the last of
    those, and any other heading nests under the most recent container heading."""
    order = sorted(toc, key=lambda t: (t.get('shamela_title_id') or 0, t['title_id']))
    by_id = {t['title_id']: t for t in toc}
    parents = {t.get('parent_id') for t in toc if t.get('parent_id') in by_id}
    level, anchor, top, inferred = {}, 0, 0, 0
    for t in order:
        head = re.sub(r'^[\s\d٠-٩\-–.():\[\]]+', '', norm(t['title_text']))
        p = t.get('parent_id')
        if p in by_id and p in level:
            lv, container = level[p] + 1, True
        elif TOP.match(head):
            lv, container, top = 1, True, 1
            inferred += 1
        elif EDGE.match(head):
            lv, container = 1, False
            anchor = 0; inferred += 1
        elif MID.match(head):
            lv, container = top + 1, True
            inferred += 1
        else:
            lv, container = anchor + 1, t['title_id'] in parents
            inferred += 1
        lv = min(lv, 5)
        level[t['title_id']] = lv
        if container or t['title_id'] in parents:
            anchor = lv
        if TOP.match(head) or (p not in by_id and lv == 1 and container):
            top = lv
    return level, order, inferred


def ce(ah):
    return None if ah is None else round(ah * 0.970224 + 621.5709)


def vol_label(part):
    return str(part).strip() if part not in (None, '') else '1'


def parse_card(text):
    """Split the Shamela card (betaka) into named fields."""
    keys = {'الكتاب': 'full_title', 'المؤلف': 'author_full', 'المحقق': 'editor', 'تحقيق': 'editor',
            'الناشر': 'publisher', 'الطبعة': 'edition', 'عدد الأجزاء': 'volumes', 'عدد الصفحات': 'printed_pages'}
    fields, notes = {}, []
    for line in paras(text or ''):
        m = re.match(r'^([^:：]{2,20})\s*[:：]\s*(.+)$', line)
        k = m and keys.get(m.group(1).strip())
        if k and k not in fields:
            fields[k] = m.group(2).strip()
        else:
            notes.append(line)
    return fields, notes


def yaml_lines(key, v, indent=0):
    """YAML with JSON-quoted scalars (always valid YAML, Arabic kept readable)."""
    pad = '  ' * indent
    empty = lambda x: x in (None, '', [], {})
    if isinstance(v, dict):
        out = [f'{pad}{key}:']
        for k, x in v.items():
            if not empty(x):
                out += yaml_lines(k, x, indent + 1)
        return out
    if isinstance(v, list) and not all(isinstance(x, (str, int, float)) for x in v):
        out = [f'{pad}{key}:']
        for x in v:
            sub = [l for k, y in x.items() if not empty(y) for l in yaml_lines(k, y, indent + 2)]
            out.append(f'{pad}  - ' + sub[0].lstrip())
            out += sub[1:]
        return out
    return [f'{pad}{key}: {json.dumps(v, ensure_ascii=False)}']


LAYER_NAMES = {
    'main': 'النص',
    's0': 'الحاشية الأولى',
    's1': 'الحاشية الثانية',
    'fn': 'هوامش المحقق',
}


def split_layers(body, footnotes):
    """Return [(layer, text)] for one page: the main text, then gloss layers marked <s0>/<s1>, then footnotes."""
    out, pos, layer = [], 0, 'main'
    for m in LAYER_TAG.finditer(body):
        out.append((layer, body[pos:m.start()]))
        layer, pos = 's' + (m.group(1) or m.group(2)), m.end()
    out.append((layer, body[pos:]))
    if footnotes:
        out.append(('fn', LAYER_TAG.sub('', footnotes)))
    return [(l, t) for l, t in out if t and t.strip()]


def convert(meta, toc, pages, manifest, volumes=None, name=None, profile=None):
    if volumes:
        pages = [p for p in pages if vol_label(p.get('part')) in volumes]
    pages = sorted(pages, key=lambda p: (p.get('sequence_num') or 0, p.get('page_id') or 0))
    page_ids = {p['page_id'] for p in pages}
    toc = [t for t in toc if t.get('page_id') in page_ids] if volumes else toc
    level, toc_order, inferred = infer_levels(toc)
    by_shamela = {t.get('shamela_title_id'): t for t in toc}
    by_page = {}
    for t in toc:
        by_page.setdefault(t.get('page_id'), []).append(t)
    multi = len({vol_label(p.get('part')) for p in pages}) > 1 or bool(volumes)
    ref = lambda p: (f"v{vol_label(p.get('part'))} " if multi else '') + f"p{p.get('page_num') or 0}"

    # ---- walk the pages once, emitting blocks and chunks
    body, chunks = [], []
    path, done, anchors = [], set(), {}
    open_ = {}   # layer -> chunk being filled
    layers_seen, words = set(), 0

    def flush(layer=None):
        for l in ([layer] if layer else list(open_)):
            c = open_.pop(l, None)
            if c and c['text']:
                chunks.append({'section': c['section'], 'pages': [c['pages'][0], c['pages'][-1]],
                               'layer': l, 'text': '\n\n'.join(c['text'])})

    def add_chunk_text(txt, pref, layer):
        c = open_.get(layer)
        if c and sum(len(x) for x in c['text']) + len(txt) > CHUNK_CHARS:
            flush(layer); c = None
        if not c:
            c = open_[layer] = {'text': [], 'pages': [], 'section': [h for _, h in path]}
        c['text'].append(txt); c['pages'].append(pref)

    def heading(t, pref):
        if sum(len(x) for x in open_.get('main', {}).get('text', [])) >= MIN_CHUNK:
            flush()
        lv = level.get(t['title_id'], 1)
        while path and path[-1][0] >= lv:
            path.pop()
        text = norm(t['title_text'])
        path.append((lv, text))
        aid = f"s{t.get('shamela_title_id') or t['title_id']}"
        anchors[t['title_id']] = (aid, pref)
        body.extend([f"{'#' * min(lv + 1, 6)} {text} {{#{aid}}}", ''])

    for p in pages:
        pref = ref(p)
        raw = p.get('body') or ''
        inline = {int(n) for n, _ in SPAN.findall(raw)}
        for t in by_page.get(p.get('page_id'), []):
            if t.get('shamela_title_id') not in inline and t['title_id'] not in done:
                heading(t, pref); done.add(t['title_id'])
        body.extend([f'[[{pref}]]', ''])
        for layer, text in split_layers(raw, p.get('footnotes')):
            layers_seen.add(layer)
            if layer == 'main':
                pos = 0
                for m in SPAN.finditer(text):
                    for x in paras(text[pos:m.start()]):
                        body.extend([x, '']); add_chunk_text(x, pref, 'main'); words += len(x.split())
                    t = by_shamela.get(int(m.group(1)))
                    if t and t['title_id'] not in done:
                        heading(t, pref); done.add(t['title_id'])
                    elif norm(clean(m.group(2))):
                        x = norm(clean(m.group(2)))
                        body.extend([f'**{x}**', '']); add_chunk_text(x, pref, 'main')
                    pos = m.end()
                for x in paras(text[pos:]):
                    body.extend([x, '']); add_chunk_text(x, pref, 'main'); words += len(x.split())
            else:
                ps = paras(SPAN.sub(lambda m: m.group(2), text))
                if not ps:
                    continue
                label = (profile or {}).get('layers', {}).get(layer, LAYER_NAMES.get(layer, layer))
                body.append(f'> **[{label}]**')
                for x in ps:
                    body.extend(['>', f'> {x}'])
                    words += len(x.split())
                body.append('')
                add_chunk_text('\n\n'.join(ps), pref, layer)
    flush()

    # ---- front matter
    fields, notes = parse_card(meta.get('betaka_text'))
    d = death_ah(meta.get('main_author_death_hijri'))
    authors = []
    for a in meta.get('authors') or []:
        ad = death_ah(a.get('death_hijri'))
        authors.append({'name': norm(a.get('name_ar') or ''), 'role': a.get('role'), 'death_ah': ad, 'death_ce_approx': ce(ad),
                        'shamela_author_id': a.get('author_id')})
    first, last = (ref(pages[0]), ref(pages[-1])) if pages else ('', '')
    fm = {
        'id': f"shamela-{meta['shamela_id']}" + (f"-v{'-'.join(volumes)}" if volumes else ''),
        'openiti_uri': book_uri(meta),
        'title': norm(meta.get('title_ar') or ''),
        'full_title': fields.get('full_title'),
        'author': {'name': norm(meta.get('main_author_name_ar') or ''), 'full_name': fields.get('author_full'),
                   'death_ah': d, 'death_ce_approx': ce(d)},
        'contributors': authors if len(authors) > 1 else None,
        'editor': fields.get('editor'),
        'publisher': fields.get('publisher'),
        'edition': fields.get('edition'),
        'printed_volumes': fields.get('volumes'),
        'category': meta.get('category_name_ar'),
        'book_type': meta.get('book_type_label'),
        'language': 'ar (Classical Arabic)',
        'diacritics': 'as in source (harakat kept)',
        'scope': f"volume {', '.join(volumes)} only" if volumes else 'complete work',
        'page_range': f'{first} – {last}',
        'stats': {'pages': len(pages), 'headings': len(anchors), 'words': words, 'chunks': len(chunks)},
        'heading_levels': 'from the dataset where recorded, otherwise inferred from heading words (باب/فصل…)' if inferred else 'from the dataset',
        'text_layers': {l: (profile or {}).get('layers', {}).get(l, LAYER_NAMES.get(l, l)) for l in ['main', 's0', 's1', 'fn'] if l in layers_seen},
        'card_notes': notes or None,
        'source': {
            'shamela_url': f"https://shamela.ws/book/{meta['shamela_id']}",
            'dataset': 'https://huggingface.co/datasets/AuthenticIlm/Shamela4_Full_DB',
            'dataset_book_id': meta.get('book_id'),
            'snapshot': (manifest or {}).get('snapshot_id'),
            'sha256': {f['path']: f['sha256'] for f in (manifest or {}).get('files', [])} or None,
        },
        'generated': date.today().isoformat(),
    }
    guide = [
        'Reading guide for machines and people:',
        f"- `[[{'v1 ' if multi else ''}p23]]` marks the START of printed page 23{' of volume 1' if multi else ''}; cite text by the nearest marker above it.",
        '- Headings come from the book\'s own table of contents; `{#s123}` is a stable anchor (Shamela heading id).',
        '- Each plain paragraph is the main text. Blockquotes labelled `[…]` are separate layers printed on the same page '
        '(glosses, editor\'s notes); they are not the author\'s words.',
        '- `﴿…﴾` encloses Qur\'an verses; ﷺ ﵁ ﵀ ﷿ are single-character honorifics.',
    ]
    guide += (profile or {}).get('guide', [])
    lines = ['---']
    for k, v in fm.items():
        if v not in (None, '', [], {}):
            lines += yaml_lines(k, v)
    lines += ['---', '', f"# {fm['title']}", '']
    lines += [f'> {g}' if i == 0 else f'> {g}' for i, g in enumerate(guide)]
    lines += ['', '## المحتويات {#contents}', '']
    for t in toc_order:
        if t['title_id'] in anchors:
            aid, pref = anchors[t['title_id']]
            lines.append(f"{'  ' * (level.get(t['title_id'], 1) - 1)}- [{norm(t['title_text'])}](#{aid}) — [[{pref}]]")
    lines += ['', '---', '']
    md = '\n'.join(lines + body).rstrip() + '\n'

    book = fm['id']
    for i, c in enumerate(chunks):
        c.update({'id': f'{book}#{i + 1:05d}', 'book': book, 'title': fm['title'], 'author': fm['author']['name'],
                  'chars': len(c['text'])})
    chunk_lines = [json.dumps({k: c[k] for k in ['id', 'book', 'title', 'author', 'section', 'pages', 'layer', 'chars', 'text']},
                              ensure_ascii=False) for c in chunks]
    return md, '\n'.join(chunk_lines) + '\n', fm


PROFILES = {
    # Tuhfat al-Muhtaj: commentary with the Minhaj in parentheses, plus two gloss layers per page
    9059: {
        'layers': {'main': 'تحفة المحتاج (الشرح، والمتن بين قوسين)', 's0': 'الحاشية الأولى', 's1': 'الحاشية الثانية'},
        'guide': ['- Main paragraphs are Ibn Hajar al-Haytami\'s commentary; words in `(…)` inside it are the text of '
                  'al-Nawawi\'s Minhaj al-Talibin being explained.',
                  '- `[الحاشية الأولى]` and `[الحاشية الثانية]` are the two gloss layers of this edition (the hawashi of '
                  'al-Shirwani and Ibn Qasim al-Abbadi); glosses quote their lemma as `(قوله …)`, and `سم` abbreviates Ibn Qasim.'],
    },
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('id', type=int, help='dataset book_id (or Shamela id with --shamela)')
    ap.add_argument('--shamela', action='store_true', help='the id is a Shamela book id')
    ap.add_argument('--volumes', nargs='*', help='keep only these volume labels, e.g. --volumes 8')
    ap.add_argument('--name', help='output file name without extension')
    ap.add_argument('--out', default='.')
    ap.add_argument('--dir', help='local copy of the book folder')
    a = ap.parse_args()
    cat = catalog()
    row = next((r for r in cat['books'] if (r[1] if a.shamela else r[0]) == a.id), None)
    if not row and not a.dir:
        sys.exit('book not found in catalog')
    meta, toc, pages, manifest = load_book(row[-1] if row else None, a.dir)
    md, chunks, fm = convert(meta, toc, pages, manifest, a.volumes, a.name, PROFILES.get(meta['shamela_id']))
    os.makedirs(a.out, exist_ok=True)
    name = a.name or fm['openiti_uri']
    open(os.path.join(a.out, name + '.md'), 'w', encoding='utf-8').write(md)
    open(os.path.join(a.out, name + '.chunks.jsonl'), 'w', encoding='utf-8').write(chunks)
    s = fm['stats']
    print(f"{name}: {s['pages']} pages, {s['headings']} headings, {s['words']:,} words, {s['chunks']} chunks", file=sys.stderr)


if __name__ == '__main__':
    main()
