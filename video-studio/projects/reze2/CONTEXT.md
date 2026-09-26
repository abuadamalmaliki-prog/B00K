# RZ—02 — team brief (read this first)

We are re-editing a 60 s fan edit for a user who has no editing experience,
works only from an iPad, and posts to a private Instagram for friends. The
tool is `video-studio/` (read `video-studio/README.md`, `studio.js`,
`render.mjs`). Version 1 is `projects/reze/index.html` → `out/rz-01.mp4`.

## What the user said (their words, lightly condensed)

- "ITS PEAK" about v1, "the song — you clipped it perfectly." Keep the exact
  song window: `media/song.webm` from 96 s to 156 s.
- "Make it 4:5, 120 FPS." → 1080×1350, 120 fps, 60 s.
- "The edit is TOO minimalist … you can SPAM the clips following the song."
- "Complex 3D and advanced 3D and below-average editing styles." By
  "below average" they mean *not mainstream / not the common template look* —
  NOT low quality. They hate generic AI/CapCut/AMV-template editing.
- "In my mind it's ABSTRACT and ELEGANT." Also "AESTHETIC".
- Favourite colours: white, black, light blue, light purple. Earlier they liked
  "2000s vibes / how Sony did commercials in 2000".
- "The audio is not smooth." Diagnosed: the song's peaks reach 1.34 (above full
  scale) and v1 passed them straight to AAC → clipping on playback. Also 0.2 s
  hard fade-in. Fix with headroom + limiter + smooth (qsin) fades; AAC 256k.
- "The video is blurry and hard to see … people will see it as trash."
  Diagnosed: sources are 1280×720; v1 cover-cropped them to 4:5 (≈1.9×
  upscale), shrank them onto small 3D screens, added scanlines and a heavy
  gradient map that crushed detail. Fixes: prefer layouts that show footage at
  ≤1.0–1.3× scale (a full-width 16:9 strip is 1080×608 — a *downscale*, crisp),
  Lanczos + contrast-adaptive sharpening, no scanlines, keep faces readable.
- Watermark on the whole video, elegant and legible:
  `Instagram: ihvyone_1` and `Tiktok: rapidfirequestion`.

## The reference they sent (`media/reference.mp4`, 17.7 s, abstract)

Contact sheets: `work/sheet-ref.png`, `work/sheet-ref-dense.png`.
Y2K chrome / liquid-glass abstraction:
- chrome & glass ribbons and swirling tubes, very glossy, reflective;
- kaleidoscopic mirror symmetry (4-, 6-, 8-fold), mandala-like chrome flowers;
- crystal-shard explosions with prismatic / chromatic dispersion edges,
  blown-out whites;
- electric blue scenes, silver/monochrome scenes, thin cyan arcs on white;
- sky / cloud interludes (real sky feel) as breathing space;
- hard cuts to pure black between phrases; fast cutting on hits.

## Footage (all 1280×720) — in `projects/reze2/media/`

Scene-cut timestamps (s) from ffmpeg scene detection. Contact sheets with
timecodes: `projects/reze/work/sheet-{clean,church,fireworks}.png`.

- `clean.mp4` (38.9 s, 30 fps): rain + café, calm, character-focused.
  Cuts: 2.3 5.43 8.43 12.83 16 20.47 22.07 23.83 24.1 24.6 25.5 30.33 32.53.
  Rain outside window 0–2.3, smile in rain 2.3–5.4, flower 5.4–8.4, door 8.4–12.8,
  walking/spinning in rain 12.8–16, café counter 16–20.5, hand at collar
  20.5–22, sitting together 22.1–23.8, laugh 24.6–25.5, head tilt 25.5–30.3,
  close-up 30.3–32.5, smile 32.5–38.8.
- `church.mp4` (87.6 s, 23.976 fps): dark blue night school, corridors, car,
  coffee, library window, green-eye close-up at 81–84, title card at 84+ (don't use).
  **Burned-in Russian subtitles at the bottom and credits at the top-right** —
  only use the vertical band uv.y ∈ [0.13, 0.86] (flipY texture coords).
  Cuts: 37.95 44.38 52.64 58.89 65.15 71.40 83.79.
- `fireworks.mp4` (78 s, 30 fps): explosive action, very fast cuts (dense cut
  list in `projects/reze/work/fireworks.cuts`). Small dark box bottom-left
  (use uv.y ≥ 0.1). Great material for spamming.

Do not put song lyrics on screen. Do not model, draw or trace the anime
characters or any logos in 3D/2D — characters appear only via the user's
footage; all 3D is original abstract geometry.

## Song timing (edit time = song time − 96 s)

173 BPM. beat = 0.3468 s, bar = 1.3872 s, bar *i* starts at `b(i)=0.62+1.3872*i`.
The chorus/drop lands at **31.14 s** (bar 22). Before that it builds
(loudness ~0.65–0.8), after it is loud (~0.9–1.0). Last ~3.5 s fade out.
Per-beat onset strength and loudness: `projects/reze2/work/beats.txt`.

## Machine limits

4 CPU cores, no GPU (WebGL = SwiftShader). 120 fps × 60 s = 7200 frames, so
per-frame cost matters: aim ≤ 0.35 s/frame at 1080×1350. **Every shell command
must finish in under 5 minutes** — wrap long ones with `timeout 300` and set the
Bash tool timeout ≤ 300000. Never retry a failing command more than twice;
never loop waiting. Test with `node render.mjs … --still T --scale 0.4` and
short `--from/--to` ranges. Use `ffmpeg -v error`.
The Chromium CA trust, fonts, ffmpeg and Playwright are already set up.

## Who owns what (don't edit other people's files)

- **Director** — `projects/reze2/BRIEF.md`, `projects/reze2/plan.js`
- **Editor ("Premiere")** — `render.mjs`, `studio.js`, `render-parallel.mjs`,
  `lib/footage.js` (2D footage shader, looks, layouts, transitions)
- **3D artist ("Blender")** — `lib/kit3d.js` and `lib/demo-3d/` test pages
- **Lead (me)** — `projects/reze2/index.html` integration, final render.

### Shared vocabulary for plan.js (the contract between all of us)

`plan.js` is an ES module: `export default [ …segments ]`, sorted, covering
0–60 s without gaps. Each segment:

```js
{ start, end,                    // seconds, snapped to the beat grid
  kind: 'clip' | '3d' | 'black',
  // kind 'clip':
  shots: [{ src: 'clean'|'church'|'fireworks', from, fx: 0.5 }],  // 1+ shots; fx = horizontal focus 0..1
  layout: 'full' | 'strip' | 'stack2' | 'stack3' | 'glass' | 'kaleido',
  look: 'natural' | 'ice' | 'chrome' | 'mono' | 'invert',
  stutter: 0 | 0.5 | 0.25,       // repeat each N beats (clip spam), 0 = play normally
  speed: 1,                      // playback speed (0.5 slow-mo … 2)
  // kind '3d':
  scene: 'ribbons' | 'kaleido' | 'shards' | 'sky' | 'orbit',  // may also carry a shot to show inside the scene
  // any kind:
  in: 'cut' | 'flash' | 'prism' | 'shatter' | 'iris',       // transition into this segment
  note: 'why this choice'
}
```
