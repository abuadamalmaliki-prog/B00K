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
| `--transparent` | Keep the background transparent (needs `.mov` or `.webm`) |
| `--still S` | Write a single PNG of time `S` |

Opened directly in a browser, a composition plays as a preview with a scrub bar.

## Writing a composition

```html
<script src="../../studio.js"></script>
<div id="stage"> …everything visible goes here… </div>
<script>
  Studio.setup({
    width: 1920, height: 1080, fps: 30, duration: 10,
    footage: { interview: 'media/interview.mp4' },          // or { src, start, from }
    audio: [
      { footage: 'interview', volume: 1 },                   // the clip's own sound
      { src: 'media/music.mp3', volume: 0.3, fadeOut: 2 },   // start, from, fadeIn also work
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
  on the current frame. `start` places the clip on the timeline and `from` sets
  its in-point.
- **Slow assets:** wrap loads in `Studio.wait(promise)` so rendering waits for them.
- Helpers: `Studio.progress(t, start, end)`, `Studio.lerp(a, b, x)`,
  `Studio.ease.{in,out,inOut,outBack}`.

## Examples

- `examples/arabic-quote` — HTML + CSS only; vertical 1080×1920 with an Arabic
  quote revealed word by word.
- `examples/three-scene` — Three.js with bloom post-processing, HTML titles over
  the WebGL canvas.
- `examples/footage-fx` — a video clip through a WebGL2 shader: before/after
  wipe, split-tone grade, grain, vignette, chromatic aberration, glitch, lower
  third, and the clip's audio.
