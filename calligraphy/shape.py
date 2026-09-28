import uharfbuzz as hb
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

class Font:
    def __init__(self, path):
        self.file = path
        data = open(path, 'rb').read()
        self.hbfont = hb.Font(hb.Face(data))
        self.tt = TTFont(path)
        self.gs = self.tt.getGlyphSet()
        self.order = self.tt.getGlyphOrder()
        self.upem = self.tt['head'].unitsPerEm
        gdef = self.tt['GDEF'].table if 'GDEF' in self.tt else None
        self.classes = (gdef.GlyphClassDef.classDefs if gdef and gdef.GlyphClassDef else {})
        self._cache = {}

    def shape(self, text, features=None):
        buf = hb.Buffer(); buf.add_str(text); buf.guess_segment_properties()
        hb.shape(self.hbfont, buf, features or {})
        out, x = [], 0
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            name = self.order[info.codepoint]
            out.append(dict(name=name, cluster=info.cluster,
                            x=x + pos.x_offset, y=pos.y_offset,
                            mark=self.classes.get(name) == 3))
            x += pos.x_advance
        return out, x   # glyphs (visual LTR order), total advance

    def path(self, name, m=(1, 0, 0, 1, 0, 0)):
        pen = SVGPathPen(self.gs)
        self.gs[name].draw(TransformPen(pen, m))
        return pen.getCommands()

    def bounds(self, name):
        from fontTools.pens.boundsPen import BoundsPen
        bp = BoundsPen(self.gs); self.gs[name].draw(bp); return bp.bounds
