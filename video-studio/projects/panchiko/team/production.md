# Production & QA: Panchiko

## 1. Post-mortem (rz-02)

- **Beat.** We used a fixed-tempo formula, and the validator only checked that cuts snapped to it. Weak onsets (0.15–0.30) on grid beats went unheard. **Fix:** a real downbeat tracker, cross-checked. The user approves a beat-flash test, then the grid is frozen.
- **Random.** 108 cuts, each justified by onset strength, not story. **Fix:** 8–14 shots, each with a `story:` reason. Cut on phrases.
- **Blurry.** We accepted 1.9× upscales, 120 fps halved the bits per frame, and we checked stills scaled down. **Fix:** nothing above 1:1 (the 1000 px cover stays ≤ 900 px on screen). Stills checked at 100 %.
- **Effort.** Plan to final took 51 min, and the user saw nothing before the final. **Fix:** user gates.

## 2. Gates and roles

Screenwriter: story and text. Cinematographer: camera and light. Director: look and storyboard. Music: beat map. 3D: build. Production: renders and QA. Lead: user contact.

| Gate | User sees |
|-|-|
| G1 | Outline + beat-flash test: sync? song part? aspect? text? |
| G2 | 8–14 full-res stills + animatic |
| G3 | 60 s draft (720×900, 30 fps) |
| G4 | Final, after QA |

## 3. Render budget

3600 frames: the render takes as many hours as the seconds per frame (3 jobs). About 230 s of each 280 s run is rendering; HEVC encode ≈ 150 s.

| s/frame | runs | wall |
|-|-|-|
| 0.20 | 4–5 | 0.35 h |
| 0.35 | 6–7 | 0.55 h |
| 0.60 | 10–11 | 0.85 h |

- **Drafts:** `--scale 0.5 --fps 30 --codec h264 -o out/pk-draft-vN.mp4` take 1–2 runs. Single shots: `--from/--to`.
- **Output names:** use a new `-o` for each draft; a changed fingerprint wipes chunks.
- **During the final:** freeze the page and run with `--keep`, so a size fix is a re-encode with `--crf 26`.
- **Speed gate at G2:** each shot ≤ 0.35 s/frame.
- **Size:** 28 MB ≈ 3.4 Mbps video. Expect ~18–25 MB.

## 4. QA before the user sees anything

Stills (every shot):
- [ ] Sharp at 100 %; no shimmer or sky banding
- [ ] Continuity of hands, sleeves and the CD
- [ ] Text ≥ 40 px, contrast ≥ 4.5:1, **no lyrics**
- [ ] No trademarks, no band likenesses
- [ ] Watermark exact on every frame

Draft and final:
- [ ] Beat spot-checks at `floor(beat·fps)` ± 1 frame
- [ ] 3600 frames, 60 fps
- [ ] True peak ≤ −1 dBTP (the source is +1.8)
- [ ] Under 28 MB; plays on iPad
- [ ] Flag: Wikipedia says the CD came from an Oxfam, not a 7-Eleven. Lead to settle at G1.

## 5. Tools

- **`beat_this`** (MIT): state-of-the-art beats and downbeats on CPU. Cross-check with librosa.
- **GSAP**: `tl.seek(t)`, downbeat labels, one nested timeline per shot.
- **Rejected:** theatre.js (GUI-only benefit, and we render headless) and all-in-one (too slow on CPU).
