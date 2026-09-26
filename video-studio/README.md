# video-studio

Make videos with HTML, CSS, JavaScript, WebGL and Three.js.

A composition is an ordinary web page. `render.mjs` opens it in headless
Chromium, moves it to the exact time of each frame, screenshots it, and pipes
the frames — plus any audio — into ffmpeg. Because every frame is computed
from its timestamp, the result is identical on every render and never drops a
frame, however heavy the WebGL.

Browser text shaping means Arabic (and any other script) renders correctly,
which ffmpeg's own text filter cannot do.

## Setup

```sh
./setup.sh
```

Installs ffmpeg, the Amiri Arabic font and Playwright, and generates the sample
clip for `examples/footage-fx`. Needs Node 20+ and a Playwright-compatible
Chromium.

## Render

```sh
node render.mjs examples/arabic-quote/index.html            # → out/arabic-quote.mp4
node render.mjs examples/three-scene/index.html --scale 0.5  # quick half-size draft
node render.mjs examples/footage-fx/index.html --still 2.2   # one PNG, for checking a frame
node render.mjs my/overlay/index.html --transparent -o out/overlay.mov   # ProRes 4444 with alpha
```

| Option | Meaning |
| --- | --- |
| `-o FILE` | Output: `.mp4` (H.264), `.mov` (ProRes), `.webm` (VP9). Default `out/<name>.mp4` |
| `--fps N`, `--duration S` | Override the composition's values |
| `--from S --to S` | Render only part of the timeline |
| `--scale X` | Render at a fraction of full size, for fast drafts |
| `--crf N` | Quality for `.mp4`/`.webm`; lower is better and larger (defaults 18 / 28) |
| `--preset P` | x264 speed preset for `.mp4` (default `medium`) |
| `--transparent` | Keep the background transparent (needs `.mov` or `.webm`) |
| `--still S` | Write a single PNG of time `S` |
| `--no-audio` | Video only |
| `--audio-only FILE` | Write just the mixed audio track (`.m4a`), no frames |
| `--prepare` | Extract all footage into the cache and exit |
| `--info FILE` | Write size, fps, duration and the files the page loads as JSON |

Opened directly in a browser, a composition plays as a preview with a scrub bar.

### Parallel, resumable renders

```sh
node render-parallel.mjs projects/reze2/index.html -o out/rz-02.mp4        # HEVC, 3 jobs, 1 s chunks
node render-parallel.mjs lib/footage-test.html --chunk 0.5 --codec h264
```

Renders the timeline as exact frame ranges in parallel `render.mjs` processes
(video-only x264 CRF 12 intermediates), mixes the audio **once** for the whole
range, encodes (`--codec hevc`: libx265 CRF 24, `hvc1`, or `h264`: CRF 20) and
joins everything with the concat demuxer, checking the frame count. A chunk that
fails or runs past `--timeout` (300 s) is split in half and retried once.

It works within a time budget: after `--budget S` seconds (default 280, `0` = none)
it stops, keeps the finished chunks in `out/.parallel/<name>/`, and exits with
code 75 — run the same command again to continue. Changing any file the page
loads starts over; `--fresh` forces that. Other options: `--jobs N` (3),
`--chunk S` (1), `--crf`, `--preset` (medium), `--keep`, and `--fps`,
`--duration`, `--from`, `--to`, `--scale` as for `render.mjs`.

## Writing a composition

```html
<script src="../../studio.js"></script>
<div id="stage"> …everything visible goes here… </div>
<script>
  Studio.setup({
    width: 1920, height: 1080, fps: 30, duration: 10,
    footage: { interview: 'media/interview.mp4' },          // or { src, start, from, duration }
    audio: [
      { footage: 'interview', volume: 1 },                   // the clip's own sound
      { src: 'media/music.mp3', volume: 0.3, fadeOut: 2 },   // start, from, duration, fadeIn also work
    ],
  });

  Studio.onFrame((t) => {
    // Set every moving thing from t (seconds). May be async.
  });
</script>
```

Rules that keep renders exact:

- **CSS animations and `element.animate()` just work.** They are paused and
  scrubbed to each frame's time, delays included. Use `animation-fill-mode: both`.
- **Everything else moves from `t`.** Don't use `Date`, `performance.now()`,
  `setTimeout` or `requestAnimationFrame` loops to drive motion. For GSAP,
  build a paused timeline and call `tl.seek(t)` in `onFrame`.
- **Use `Studio.random(seed)`**, not `Math.random()`.
- **Footage:** `Studio.footage('name')` returns an element to draw or upload as a
  texture — `<img>` while rendering, `<video>` in preview. It is always already
  on the current frame. `start` places the clip on the timeline, `from` sets
  its in-point, and `duration` limits how much is used (the clip then holds its
  last frame).
- **Footage you time yourself:** declare `{ src, from, duration, manual: true }`
  and call `await Studio.footageAt('name', seconds)` in `onFrame` — it puts the
  element on that moment of the source file (absolute seconds, clamped to
  `from…from + duration`) and resolves once the frame is decoded (in preview it
  seeks the `<video>`). Manual clips are never moved by the timeline. For speed
  ramps, stutters and reversing.
- **Slow assets:** wrap loads in `Studio.wait(promise)` so rendering waits for them.
- Helpers: `Studio.progress(t, start, end)`, `Studio.lerp(a, b, x)`,
  `Studio.ease.{in,out,inOut,outBack}`.

How footage is prepared: frames are extracted at the source's own frame rate
(capped at the composition's — a 30 fps clip in a 120 fps edit is not stored
four times over), scaled with Lanczos but never enlarged, lightly sharpened
(contrast-adaptive, luma only; `sharpen: 0…1` per entry, default 0.4, `0` = off)
and cached in `out/.cache/footage/`, so later stills, drafts and parallel chunks
reuse them. Entries with the same source and window share one extraction.
Delete the folder to reclaim space.

How audio is mixed: each entry plays from `from` for `duration` (or to the end)
with `fadeIn`/`fadeOut` shaped as quarter-sine curves (`curve` picks another
ffmpeg `afade` curve; a 5 ms fade is always applied so cuts never click). The
mix gets 1 dB of headroom and a lookahead limiter at −1 dBFS, then AAC 256k at
48 kHz — songs mastered past full scale no longer clip.

## Footage in Three.js: `lib/footage.js`

An ES module that imports `three` (the page needs the usual import map). It
speaks the plan.js segment vocabulary (`layout`, `look`, `stutter`, `speed`,
`in`, `bg`, shots with `src`, `from`, `fx`, `band`, `look`). See
`lib/footage-test.html` for every feature in 4 s.

```js
import { createFootageLayer, footageEntries } from '../../lib/footage.js';
Studio.setup({ ..., footage: footageEntries({ clean: 'media/clean.mp4' }) });  // manual clips, 3 slots each
const layer = createFootageLayer(W, H);
Studio.onFrame(async (t) => { await layer.render(renderer, segment, t); });
```

- `createFootageMaterial()` — one ShaderMaterial: crop `rect`, `look` (0 natural,
  1 ice, 2 chrome, 3 mono, 4 invert — all in the white / black / light-blue /
  light-purple palette, all keeping faces readable), `sharpen` (CAS), `prism`,
  `flash`, `dip`, `kaleido` (folds) + `spin`, `iris`, `opacity`, `amount`, `texel`, `aspect`.
- `fitRect(shot, aspect)` crop honouring `band`, `fx` (`fy`, `zoom`); church and
  fireworks get their clean bands by default. `layout(name, W, H, { width, bottomSafe, gap })`
  → pixel rects for `full`, `strip`, `stack2`, `stack3` (strips 1040 px wide, bottom
  80 px kept for the watermark).
- `shotTime(seg, shot, t, beat)` → source seconds with `speed`, `stutter` (loop the
  first N beats), `hold`. `footageTexture(el)` re-uploads only when the frame changed.
- `transitionIn(seg, t)` → `{ flash, prism, dip, iris }` for `in: 'flash' | 'prism' |
  'iris' | 'cut'` over ~0.14–0.2 s; `'shatter'` (a 3D effect) falls back to a prismatic white hit.

## Examples

- `examples/arabic-quote` — HTML + CSS only; vertical 1080×1920 with an Arabic
  quote revealed word by word.
- `examples/three-scene` — Three.js with bloom post-processing, HTML titles over
  the WebGL canvas.
- `examples/footage-fx` — a video clip through a WebGL2 shader: before/after
  wipe, split-tone grade, grain, vignette, chromatic aberration, glitch, lower
  third, and the clip's audio.
