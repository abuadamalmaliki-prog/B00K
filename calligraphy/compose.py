"""Thuluth-style composition engine.

Pipeline for every glyph (letter body or tashkeel mark, each its own path):
  HarfBuzz shaping -> outline in font units
  -> per-glyph tweak      (dx, dy, scale, rotation: hand-adjust anything)
  -> ascender warp        y' = h0 + k(y - h0) for y > h0   (tall Thuluth alifs/lams)
  -> global map           affine tier placement  OR  circular arc warp
All transforms are plain functions of (x, y), so any math can be slotted in.
"""
import base64, json, math, sys
import cairosvg
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.boundsPen import BoundsPen
from shape import Font

HERE = sys.path[0] + '/'
FONT = Font(HERE + 'fonts/AmiriQuran-Regular.ttf')
PHOTO = HERE + 'the-word-vasnetsov.jpg'
import os
TWEAKS = json.load(open(HERE + 'tweaks.json')) if os.path.exists(HERE + 'tweaks.json') else {}

W, H = 1400, 2080
H0, K = 430, 1.45          # ascender warp: threshold (font units), stretch factor
MARK_SCALE = 1.12


def warp_pts(args, f):
    return tuple(None if p is None else f(*p) for p in args)


def outline(name, f):
    """Draw glyph `name` with every point mapped through f(x, y) -> (x, y)."""
    rec = DecomposingRecordingPen(FONT.gs); FONT.gs[name].draw(rec)
    out = SVGPathPen(None)
    for op, args in rec.value:
        getattr(out, op)(*warp_pts(args, f))
    return out.getCommands()


def bbox(name):
    bp = BoundsPen(FONT.gs); FONT.gs[name].draw(bp)
    return bp.bounds or (0, 0, 0, 0)


def tall(y):
    return y if y <= H0 else H0 + (y - H0) * K


def glyph_funcs(tier, i, g):
    """Local font-unit transform for glyph i: tweak, then Thuluth warp."""
    t = TWEAKS.get(f'{tier}:{i}', {})
    x0, y0, x1, y1 = bbox(g['name'])
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    s = t.get('scale', MARK_SCALE if g['mark'] else 1.0)
    r = math.radians(t.get('rot', 0))
    dx, dy = t.get('dx', 0), t.get('dy', 0)
    # a mark rides on the warped height of its lowest point, undistorted
    lift = (tall(g['y'] + y0) - (g['y'] + y0)) if g['mark'] else 0

    def f(x, y):
        x, y = x - cx, y - cy
        x, y = s * (x * math.cos(r) - y * math.sin(r)), s * (x * math.sin(r) + y * math.cos(r))
        x, y = x + cx + g['x'] + dx, y + cy + g['y'] + dy
        return (x, y + lift) if g['mark'] else (x, tall(y))
    return f


def tier_paths(tier, text, place):
    glyphs, adv = FONT.shape(text)
    paths = []
    for i, g in enumerate(glyphs):
        local = glyph_funcs(tier, i, g)
        paths.append((i, g, outline(g['name'], lambda x, y: place(*local(x, y), adv))))
    return paths, adv


def straight(cx, baseline, width, adv_hint=None):
    def place(x, y, adv):
        s = width / adv
        return cx + (x - adv / 2) * s, baseline - y * s
    return place


def arc(cx, cy, R, span_deg):
    """Bend text onto a circle: x -> angle, y -> radius. Reads upright over the top."""
    def place(x, y, adv):
        s = math.radians(span_deg) * R / adv
        a = (x - adv / 2) * s / R
        rr = R + y * s
        return cx + rr * math.sin(a), cy - rr * math.cos(a)
    return place


# ---------------------------------------------------------------- composition
TIERS = [
    ('crown', 'أَشْهَدُ أَنْ لَا إِلٰهَ إِلَّا ٱللَّٰهُ ٱلْوَاحِدُ', arc(700, 750, 555, 104)),
    ('trinity', 'ٱلْآبُ وَٱلِٱبْنُ وَٱلرُّوحُ ٱلْقُدُسُ', straight(700, 1610, 1180)),
    ('word', 'وَأَشْهَدُ أَنَّ يَسُوعَ ٱلْمَسِيحَ هُوَ كَلِمَةُ ٱللَّٰهِ', straight(700, 1870, 1080)),
]


def build(debug=False):
    img = base64.b64encode(open(PHOTO, 'rb').read()).decode()
    body, labels = [], []
    for tier, text, place in TIERS:
        paths, _ = tier_paths(tier, text, place)
        for i, g, d in paths:
            body.append(f'<path d="{d}" class="{"m" if g["mark"] else "b"}"/>')
            if debug:
                x0, y0, x1, y1 = bbox(g['name'])
                lx = g['x'] + (x0 + x1) / 2
                ly = g['y'] + (y0 + y1) / 2 if g['mark'] else -260 - 90 * (i % 3)
                x, y = place(lx, ly, _)
                cls = 'lbl mk' if g['mark'] else 'lbl'
                labels.append(f'<text x="{x:.0f}" y="{y:.0f}" class="{cls}">{tier[0]}{i}</text>')
    ink = ''.join(body)
    ax, aw, atop = 700 - 450, 900, 300           # arch window
    arch = (f'M{ax},{atop + 450} A450,450 0 0 1 {ax + aw},{atop + 450} '
            f'L{ax + aw},{atop + 1000} L{ax},{atop + 1000} Z')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>
 <linearGradient id="gold" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2="{H}">
  <stop offset="0" stop-color="#fbe7a1"/><stop offset=".35" stop-color="#d9a441"/>
  <stop offset=".6" stop-color="#f6d98a"/><stop offset="1" stop-color="#b07a24"/></linearGradient>
 <radialGradient id="bg" cx=".5" cy=".38" r=".75">
  <stop offset="0" stop-color="#1d3263"/><stop offset="1" stop-color="#080f22"/></radialGradient>
 <pattern id="dots" width="28" height="28" patternUnits="userSpaceOnUse">
  <circle cx="14" cy="14" r="1.6" fill="#d9a441" opacity=".18"/></pattern>
 <clipPath id="win"><path d="{arch}"/></clipPath>
 <filter id="glow" x="-5%" y="-5%" width="110%" height="110%">
  <feGaussianBlur stdDeviation="3" in="SourceAlpha"/><feOffset dy="3"/>
  <feComponentTransfer><feFuncA type="linear" slope=".7"/></feComponentTransfer>
  <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge></filter>
</defs>
<style>.b,.m{{fill:url(#gold);stroke:url(#gold);stroke-linejoin:round}} .b{{stroke-width:2.4}} .m{{stroke-width:.8}}
.lbl{{font:bold 12px monospace;fill:#ff5c5c;text-anchor:middle}} .mk{{fill:#7fe0ff}}</style>
<rect width="{W}" height="{H}" fill="url(#bg)"/><rect width="{W}" height="{H}" fill="url(#dots)"/>
<rect x="30" y="30" width="{W - 60}" height="{H - 60}" fill="none" stroke="url(#gold)" stroke-width="3"/>
<rect x="44" y="44" width="{W - 88}" height="{H - 88}" fill="none" stroke="url(#gold)" stroke-width="1"/>
<image x="{ax - 1}" y="{atop}" width="{aw + 2}" height="1000" preserveAspectRatio="xMidYMin slice" clip-path="url(#win)" xlink:href="data:image/jpeg;base64,{img}"/>
<path d="{arch}" fill="none" stroke="url(#gold)" stroke-width="7"/>
<path d="{arch}" fill="none" stroke="#080f22" stroke-width="2" transform="translate(0,0)" opacity=".6"/>
<g stroke="url(#gold)" stroke-width="2" fill="none">
 <path d="M150,1385 H620 M780,1385 H1250"/><path d="M700,1367 l18,18 -18,18 -18,-18z" fill="url(#gold)"/>
 <path d="M200,1975 H1200"/><circle cx="700" cy="1975" r="9" fill="url(#gold)"/></g>
<g filter="url(#glow)">{ink}</g>
{''.join(labels)}
</svg>'''
    return svg


if __name__ == '__main__':
    debug = '--debug' in sys.argv
    svg = build(debug)
    name = 'orthodox-shahada-thuluth' + ('-debug' if debug else '')
    open(HERE + name + '.svg', 'w').write(svg)
    cairosvg.svg2png(bytestring=svg.encode(), write_to=HERE + name + '.png')
    print('wrote', name)
