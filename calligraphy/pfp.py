"""1:1 circular medallion for a WhatsApp profile picture.

    python3 pfp.py [path/to/Thuluth.ttf]

Top ring: text bent onto a circle, reading upright over the top   (x -> angle, y -> +radius)
Bottom ring: text bent the other way, upright along the bottom    (x -> angle, y -> -radius)
Everything stays inside the inscribed circle WhatsApp crops to.
"""
import base64, math, sys
import cairosvg
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.svgPathPen import SVGPathPen
from shape import Font

HERE = sys.path[0] + '/'
FONT = Font(sys.argv[1] if len(sys.argv) > 1 else HERE + 'fonts/ae_Tholoth.ttf')
PHOTO = HERE + 'the-word-vasnetsov.jpg'
S, C = 1080, 540                       # canvas, centre

TOP = 'أَشْهَدُ أَنْ لَا إِلٰهَ إِلَّا ٱللَّٰهُ ٱلْآبُ وَٱلِٱبْنُ وَٱلرُّوحُ ٱلْقُدُسُ'
BOTTOM = 'وَيَسُوعُ ٱلْمَسِيحُ كَلِمَةُ ٱللَّٰهِ'

# Fonts without wasla / dagger alif (e.g. ae_Tholoth): standard modern fully-voweled spelling.
if 0x0671 not in FONT.tt.getBestCmap() or 0x0670 not in FONT.tt.getBestCmap():
    for a, b in [('إِلٰهَ', 'إِلَهَ'), ('ٱللَّٰه', 'اللَّه'), ('ٱ', 'ا')]:
        TOP, BOTTOM = TOP.replace(a, b), BOTTOM.replace(a, b)


def ring(text, R, span_deg, bottom=False):
    glyphs, adv = FONT.shape(text)
    s = math.radians(span_deg) * R / adv

    def place(x, y):
        a = (x - adv / 2) * s / R
        if bottom:                      # upright along the bottom: ascenders point inward
            r = R - y * s
            return C + r * math.sin(a), C + r * math.cos(a)
        r = R + y * s
        return C + r * math.sin(a), C - r * math.cos(a)

    d = []
    for g in glyphs:
        rec = DecomposingRecordingPen(FONT.gs); FONT.gs[g['name']].draw(rec)
        pen = SVGPathPen(None)
        for op, args in rec.value:
            getattr(pen, op)(*(None if p is None else place(p[0] + g['x'], p[1] + g['y']) for p in args))
        d.append(pen.getCommands())
    return ''.join(d)


def build():
    img = base64.b64encode(open(PHOTO, 'rb').read()).decode()
    k, fx, fy, fr = 1.18, 365, 235, 225        # zoom and face/halo circle in photo pixels
    top = ring(TOP, 372, 236)
    bot = ring(BOTTOM, 440, 112, bottom=True)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{S}" height="{S}" viewBox="0 0 {S} {S}">
<defs>
 <linearGradient id="gold" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2="{S}">
  <stop offset="0" stop-color="#fbe7a1"/><stop offset=".3" stop-color="#d9a441"/>
  <stop offset=".55" stop-color="#f6d98a"/><stop offset="1" stop-color="#b07a24"/></linearGradient>
 <radialGradient id="bg" cx=".5" cy=".5" r=".7">
  <stop offset="0" stop-color="#1d3263"/><stop offset="1" stop-color="#070d1e"/></radialGradient>
 <pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse">
  <circle cx="12" cy="12" r="1.4" fill="#d9a441" opacity=".16"/></pattern>
 <clipPath id="win"><circle cx="{C}" cy="{C}" r="{fr * k:.0f}"/></clipPath>
 <filter id="glow" x="-5%" y="-5%" width="110%" height="110%">
  <feGaussianBlur stdDeviation="2.5" in="SourceAlpha"/><feOffset dy="2.5"/>
  <feComponentTransfer><feFuncA type="linear" slope=".75"/></feComponentTransfer>
  <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge></filter>
</defs>
<rect width="{S}" height="{S}" fill="url(#bg)"/><rect width="{S}" height="{S}" fill="url(#dots)"/>
<image x="{C - fx * k:.1f}" y="{C - fy * k:.1f}" width="{732 * k:.1f}" height="{800 * k:.1f}" clip-path="url(#win)" xlink:href="data:image/jpeg;base64,{img}"/>
<g fill="none" stroke="url(#gold)">
 <circle cx="{C}" cy="{C}" r="{fr * k:.0f}" stroke-width="6"/><circle cx="{C}" cy="{C}" r="{fr * k + 10:.0f}" stroke-width="1.5"/>
 <circle cx="{C}" cy="{C}" r="512" stroke-width="3"/><circle cx="{C}" cy="{C}" r="500" stroke-width="1"/></g>
<g fill="url(#gold)" stroke="url(#gold)" stroke-width="3.2" stroke-linejoin="round" filter="url(#glow)">
 <path d="{top}"/><path d="{bot}"/></g>
<g fill="url(#gold)">{''.join(
        f'<circle cx="{C + 425 * math.sin(math.radians(a)):.1f}" cy="{C - 425 * math.cos(math.radians(a)):.1f}" r="7"/>'
        for a in (121.5, -121.5))}</g>
</svg>'''


if __name__ == '__main__':
    svg = build()
    open(HERE + 'pfp.svg', 'w').write(svg)
    cairosvg.svg2png(bytestring=svg.encode(), write_to=HERE + 'pfp.png')
    print('wrote pfp.png')
