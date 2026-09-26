# PANCHIKO — short 3D film — team brief (DISCUSSION ROUND)

Read this first. This round is **research and proposals only** — the user said
"discuss before doing anything". Do not build the film yet.

## The user and what went wrong before

The user edits from an iPad, posts to a private Instagram (friends), has no
editing experience. Our last fan edit (projects/reze2, `out/rz-02.mp4`) was
judged honestly as: "bad, really random, parts blurry, zero effort, the beat is
really really bad". What they *did* like: the 3D. Lessons we must apply:
- **Beat**: our beat grid came from a naive detector nobody checked by ear.
  This time: robust beat/downbeat tracking (a proper library), and a
  beat-flash test the user confirms before anything is cut to it.
- **Random**: cuts had no story reason. This time every shot serves the story.
- **Blurry**: never enlarge low-res material; 3D rendered at full resolution.
- **Effort**: craft over quantity — composition, lighting, pacing, details.

## The brief (user's words, condensed)

A 1-minute first-person **3D short film** about how the band **Panchiko** was
discovered — replicate the discovery story from Wikipedia
(https://en.wikipedia.org/wiki/Deathmetal_(EP)). "Make it like a movie."
1. Inside and outside a **7-Eleven** (see constraints).
2. First person; the viewer's body is a **white adult man** (hands/arms/legs
   seen in first person, maybe a reflection).
3. Story from the Wikipedia article (read it; cite what you use).
4. Uses all agents: two groups of three, the lead coordinates.
5. Think fundamentals (story, cinematography, pacing, emotion), not just tech.
6. Use GitHub packages/resources that genuinely help.
7. The user wants lyrics written in the green landscape (sky/land) at the best
   part — **see constraints: we cannot reproduce lyrics**.
8. **60 fps**, 9. **1 minute**, 11. **3D**, 12. HTML/CSS/WebGL/Three.js +
   our tooling (`video-studio/`: README.md, studio.js, render.mjs,
   render-parallel.mjs, lib/footage.js, lib/kit3d.js).
Earlier idea from the user: after finding the CD, he listens to it in nature
"almost like nowhere on earth — blue sky, green land".
Later, if it does well, a full 4:22 version may follow — design scenes that can
extend.

## Materials (projects/panchiko/media/)

- `song.mp4` — the song, 261.97 s (4:22), AAC 44.1 kHz (video track is a static 360×360 image; ignore it).
- `cover.webp` — the EP cover image the user supplied. It may be shown **as
  provided** (e.g. as a texture on the CD case/disc). Do not redraw, trace or
  recreate it.
- Watermark from earlier edits must stay: `Instagram: ihvyone_1 · Tiktok: rapidfirequestion`.
- Format: 60 fps, 60 s. Aspect not yet confirmed — earlier edits were 4:5
  1080×1350 for Instagram; propose if you think otherwise.

## Constraints (non-negotiable)

- **No song lyrics**, anywhere: not on screen, not in files, not in reports. Do
  not transcribe them. You may propose *where and how* on-screen text appears in
  the landscape, and what *original* text could go there (e.g. the song title,
  facts from Wikipedia, original lines); the lead will discuss this with the user.
- **No 7-Eleven logo/trademark reproduced.** Build an original convenience store
  that reads as a Japanese/UK-style konbini/corner shop (layout, fridges,
  shelves, fluorescent light, striped fascia in original colours, invented
  store name). Products get invented labels.
- Characters/people: an original generic adult male body. Don't depict the real
  band members' likenesses.
- Assets from outside must be openly licensed (CC0/CC-BY/MIT etc.) with the
  licence recorded; prefer CC0. No ripped game assets.

## Machine limits and rules

4 CPU cores, no GPU (Chromium SwiftShader WebGL2). 60 s × 60 fps = 3600 frames.
Past measurement: 0.10–0.19 s/frame overall with 3 parallel jobs on moderate
scenes. **Every shell command must finish in < 5 minutes** (`timeout 300`, Bash
tool timeout ≤ 300000); never retry a failing command more than twice; no
waiting loops. Network goes through a proxy: npm, pip, GitHub, jsDelivr work.
Write only your own file `projects/panchiko/team/<your-role>.md` (plus scratch
files in `projects/panchiko/work/<your-role>/`). Don't edit shared code. Don't commit.
