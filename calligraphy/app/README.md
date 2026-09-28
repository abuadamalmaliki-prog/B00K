# Mihbara (مِحْبَرَة)

A browser calligraphy studio, built from scratch in the spirit of *Ana Muhtarif al-Khat*
(no code or fonts from that app). It runs on a phone and has no ads.

Live: https://claude.ai/artifact/2opmdUYqopJja1Hp33t59A

- HarfBuzz (WebAssembly) shaping with full tashkeel in six scripts: Thuluth (ae_Tholoth),
  Naskh Mushaf (Amiri Quran), Katibeh, Ruqaa, Kufi, Farsi/Nastaliq
- Every word is its own object: drag, pinch to scale and rotate, stretch, mirror, **bend along a circle**
- Letters & marks mode: move, scale, rotate any single letter, dot or haraka; harakat can follow their letter
- Layouts: medallion ring, tarkib (stacked words in a circle), tiers, single line
- Tashkeel palette, kashida (tatweel), optional "Add full tashkeel with Claude"
- Gold leaf, ink colors, colored harakat, outline, shadow, presets
- Photo inside a circle or arch window, patterns, frames; 1:1, 4:5 and 9:16 canvases
- Undo/redo, autosave, project files, PNG (1080/2160) and SVG export

Build: `python3 build.py` inlines `hb.js` and `hbjs.js` (harfbuzzjs 0.4.15, MIT) into `studio.html`
and writes `mihbara.html`; publish it with `hb.wasm`, `sample.jpg` and `fonts/` beside it.
