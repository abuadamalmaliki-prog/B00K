# video-style

Renders the dark cinematic explainer style: 3D chrome logo intro, starfield/haze WebGL background, avatar + red ghost heading,
glowing word-by-word subtitles with gold/red highlights, and torn-paper source cards with animated highlighter marks.

Stack: Three.js (WebGL background + logo), HTML/CSS (all text and cards), Playwright (frame capture), ffmpeg (encode + audio).
Every frame is a pure function of time (`window.frame(t)`), so renders are deterministic.

## Run

```bash
npm install
export FFMPEG=/path/to/ffmpeg          # or have ffmpeg on PATH
node render.mjs project.example.json out/demo.mp4
node render.mjs project.example.json out/check.png --still 12     # single frame, for quick layout checks
node render.mjs project.example.json out/part.mp4 --from 10 --to 19 --width 848
```

Flags: `--width` (default 1696; design space is 848x464 and scales), `--from/--to` seconds, `--still T`, `--crf`, `--preset`.
About 0.2 s/frame at 1696 wide on CPU software GL.

## Project file

- `audio`: voice-over / original video (audio track is used), path relative to the project file.
- `brand`: `logo` (PNG with alpha, optional; otherwise a teardrop with `logoText`), `handles` (two lines, top-left).
- `fonts`: `[{ "family": "Amiri", "file": "fonts/Amiri-Regular.ttf" }]` to use your own fonts.
- `intro.duration`: seconds of logo intro.
- `scenes[]` with `start`/`end` in seconds:
  - `type: "speaker"`: `avatar` (image), `name`, `label`, `ghost` (`*bold*` allowed), `subtitle`, `tint` (0-1 red glow).
  - `type: "card"`: `source` (title above the paper), `body` (wrap highlights as `[[text]]`), `dir` (`rtl` for Arabic), `subtitle`,
    `dockAt` (seconds into the scene when the card shrinks left), `dock: false` to keep it centered, `tilt`, `seed` (torn edge).
- Subtitle markup: `{g|gold}`, `{r|red}`, `{i|italic}`. Words are revealed evenly across the scene (`revealDuration` overrides).
