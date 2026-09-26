# RZ—02 — Director's brief

## What does this user want?

A 60 s, 4:5 fan edit that feels designed, not templated. They loved v1's song window and its white "Sony 2000" calm. But v1 showed one small clip at a time on an empty stage, so it read as a slideshow ("too minimalist"). Its footage was upscaled 1.9×, shrunk onto 3D screens, scanlined and gradient-mapped, so faces went soft ("blurry").

- **Abstract**: non-figurative 3D (chrome/glass ribbons, mirror mandalas, crystal shards, sky) from their reference. It cuts between shots, never decorates them.
- **Elegant**: restraint in each frame. Hard cuts, clean geometry, real white or black space, and motion that drifts instead of shaking.
- **Aesthetic**: one tight palette. The only type is the watermark.
- **Below-average (= not mainstream)**: none of the CapCut/AMV moves listed below. The complexity comes from structure (layouts, rhythm, stutter, juxtaposition), not from presets.
- **Spam the clips**: many shots on the beat grid, stutter on strong hits, several moments per frame (stacks). That makes 108 segments, where v1 had about 25.

## Style bible

**Palette.** White `#FFFFFF` (paper `#F5F6FA`). Black `#000000` (dark stage `#07080C`). Light blue `#BFE3FF`. Light purple `#CDBBFF`. Electric-blue accent `#1437FF`, sampled from the reference at 0:09–0:11. Warm fireworks never play `natural`: use `ice`, `mono`, or a ≤1-beat `invert`, which turns orange into blue.

**Looks.** Faces get `natural` or a light `ice`. `mono`/`chrome` for the silver chapter and riser. No scanlines, grain or vignette.

**Layouts (sharpness first).**
- `strip`: 1080×608, a 0.84× downscale. This is the default.
- `stack2`: two strips about 1040 wide, 12 px gutter, bottom ~80 px left free.
- `stack3`: three 1080-wide bands at about 2.4:1.
- `glass`: pane ≥ 900 px wide.
- `kaleido`: only for fireworks and the eye.
- `full` (1.9× upscale): only dark/abstract shots or ≤ 2 beats. The plan uses 3.1 s in total.
- Church footage is always cropped to uv.y 0.13–0.86 (subtitles, a title logo, credits). Fireworks uses uv.y ≥ 0.1.
- Lanczos + CAS. Faces are ≥ 300 px tall and never sit in the bottom 90 px.

**Motion.** Cuts only on the grid. Inside a segment: slow push (1–3 %), drift, parallax or orbit. 3D may take one eased burst on a hit. Stutter is a hard repeat of the in-point window with no crossfade. Nothing shakes.

**Cutting.**
- Build: 1–2-beat cuts, per-beat spam on hit runs (beats 21–25, 57–61, 69–73), then a 0.5× hold.
- Drop: 1-beat cuts, half-beats to accelerate, stutter on hits ≥ .5, a 1-beat 3D hit ends each phrase.
- Breathe: the sky at 25.9–28.0 and slow smiles on quiet beats.
- **Black** (pure, hard): 0–0.62, 14.15–14.49, 30.79–31.14, 47.44–47.79, 59.58–60.
- Transitions: 96 of the 108 are `cut`. `flash` is used only on hits ≥ .69 (5 times), `prism` 3 times, `shatter` only on the two chorus launches, `iris` only into sky.

**Avoid.**
- velocity/speed-ramp edits
- beat zoom-punches or shake
- a flash on every beat
- RGB-split glitch
- spin, zoom-blur or whip transitions
- light leaks, film burn, dust
- VHS stamps, scanlines, grain
- lens-flare packs
- neon outlines on characters
- lyrics or captions
- letterbox bars
- saturated LUTs
- blurred-fill backgrounds
- hearts, sparkles, emoji

**Watermark.**
- One line, bottom-centre, baseline 40 px from the edge, on every frame including black: `Instagram: ihvyone_1   ·   Tiktok: rapidfirequestion`.
- IBM Plex Mono 400 at 20 px, +0.06em tracking. Labels are `#BFE3FF`, handles are white.
- It sits on a hairline pill: fill `rgba(7,8,12,.35)`, 1 px `rgba(255,255,255,.18)` border.
- No motion.

## Section map (beats as in work/beats.txt)

| s | bars | what | why |
|-|-|-|-|
| 0–0.62 | – | black | reference opens on black |
| 0.62–6.17 | 0–3 | pearl ribbons, then rain strips/stacks on white | abstract first; hits .71/.68/.65 |
| 6.17–11.72 | 4–7 | door/flower spam, first stutter, star tease, 0.5× spin | hit run at beats 21–25; beat 26 has no onset |
| 11.72–15.88 | 8–10 | silver kaleido, night school, black, electric shards | .48 dip, then the .88 slam |
| 15.88–22.82 | 11–15 | café on white, glass, stutter cluster, first face + blast frame | hits .79/.84/.71 |
| 22.82–28.37 | 16–19 | laugh spam, **sky breather**, white shatter | lowest onsets at beats 74–79; **1.00** at 28.02 |
| 28.37–31.14 | 20–21 | riser: green eye, half-beats, black | loudness .55 → .88 |
| **31.14**–36.69 | 22–25 | **DROP A**: prism shards carry the cyan blast; kaleido; electric mandala | centre of gravity; beat 95 = loudness 1.00 |
| 36.69–42.24 | 26–29 | **DROP B**: her vs the fireworks (date over bomb) | .79/.77 hits |
| 42.24–47.79 | 30–33 | **DROP C** silver chapter, black | contrast in the loud stretch; .54 dip |
| 47.79–53.34 | 34–37 | **DROP D** max spam, second shatter | loud .92 relaunch |
| 53.34–60 | 38–42 | eye mandala, recap on white, ribbons, smile pane in the sky, empty sky, black | resolves through the fade; bookends the open |

**Stats:** 108 segments. 3D is 29.5 % of runtime (24.9 % with no footage).

**Optional fields** (safe to ignore):
- `bg` on clips: `white` or `black`.
- `tone` on 3D segments:
  - `pearl`: white with light-blue/lilac glass
  - `silver`: chrome on black
  - `electric`: `#1437FF` on black
  - `prism`: blown-out white with dispersion edges

Validator: `work/validate-plan.mjs`. Storyboard: `work/storyboard.png`.
