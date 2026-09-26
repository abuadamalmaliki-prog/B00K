# PANCHIKO "Found" — BUILD (decisions locked by the lead + user)

Read `CONTEXT.md` and all of `team/*.md` first. This file overrides them where
they differ.

## User decisions (26 Sep)
1. **Beat approved** ("on beat, I can't find any flaw") — and "be more
   detailed": sync *details* to the music, not just cuts — footsteps on beats,
   CD flicks on snare hits, light flickers on fills, the press-play on the slam.
2. **Setting: a music & media store** at night — CDs, albums, DVDs, Blu-rays,
   racks, listening posts, posters. Invented store name and invented products
   (no real brands/logos/band names except Panchiko's own cover as supplied).
   A "PRE-OWNED / DONATED CDs" bargain bin is where he finds it (nods to the
   true charity-shop story).
3. **Landscape text: the lead decides, it must be 3D** → the EP title
   `D>E>A>T>H>M>E>T>A>L` as huge 3D letters rising out of the grass, one letter
   per beat during 44.14–52.40 s; small true-story end cards (3D) at the end.
   Never lyrics.

## Format
1080×1350 (4:5), **60 fps**, audio window **176.016 → 236.706 s** of
`media/song.mp4` (60.69 s, ends on the song's hard stop). Beat = 0.68966 s,
bar = 2.7586 s. Timing data: `work/music/timing.json` (88 beats, 22 downbeats).
Watermark every frame, bottom-centre pill as in `projects/reze2/index.html`.

## Shot plan (film seconds)
| # | time | shot |
|---|------|------|
| 1 | 0 – 5.52 | Night, rain. Walk up the wet street to the glowing shop window full of CDs/DVDs. Right hand pushes the door on a downbeat; bell. Small 3D card: "Nottingham · 2016". |
| 2 | 5.52 – 11.03 | Inside. Fluorescent aisle of CD racks / DVD & Blu-ray shelves / posters; head turns to the bargain bin on a snare hit. |
| 3 | 11.03 – 17.24 | Fingers flick CDs in the bin, one flick per snare/hat accent; flicking stops; push in — the cover (as supplied) catches the light. |
| 4 | 17.24 – 22.07 | Quiet drop-out: turn the case over, open it, disc into a portable CD player, headphones on, thumb hovers… |
| 5 | 22.07 | **SLAM** — thumb presses play; fluorescent white blooms into sky. |
| 6 | 22.07 – 41.38 | "Nowhere on earth": green hills, blue sky, walking, hand brushing grass. |
| 7 | 41.38 – 44.14 | Breath: stop, look up. |
| 8 | 44.14 – 52.40 | 3D title letters rise from the grass, one per beat. |
| 9 | 52.41 – 57.24 | Cymbal wash: the disc throws a rainbow; true-story cards in 3D. |
| 10 | 57.24 – 60.69 | "PANCHIKO" end card on the final hits; cut to black at 60.69. |

**First delivery to the user: a 10 s preview = shots 1–2 (0–10 s).**

## Code layout (ES modules in `projects/panchiko/src/`, Three.js r170 via the import map)
- `store.js` — **engine lead**: `createStore({ renderer })` → `{ root, exterior, interior, anchors: { door, doorHinge, bin, counter, window }, update(t, ctx) }` (rain, flicker, door angle via `ctx.door` 0..1).
- `body.js` — **asset scout**: `await createBody({ renderer })` → `{ root, update(t, pose) }`; the first-person rig (Quaternius CC0 male, light skin tone, dark jacket sleeves/jeans by material or simple geometry) attached to the camera; poses `walk`, `reachDoor`, `pushDoor`, `flick`, `holdCase` with a blend weight; right-hand IK target.
- `camera.js` + `look.js` — **cinematographer**: `cameraAt(t)` → `{ position, quaternion, fov }` for shots 1–2 now (keyframes, footsteps on beats from timing.json); `createLook(renderer, W, H)` → `{ render(scene, camera, params) }` (grade, subtle grain, low-res bloom).
- `copy.js` — **screenwriter**: all invented store/product/poster names and card texts (`export default { storeName, sign, posters: [...], cdSpines: [...], dvdTitles: [...], cards: {...} }`).
- `sync.js` — **music editor**: `export default { beats, downbeats, snares, accents, fills, sections }` in film seconds (window-relative), plus helpers `pulse(t, list, decay)`.
- `index.html` — **lead** integrates. **Production/QA** reviews stills + the preview before the user sees it.

Rules: every command < 5 min (`timeout 300`), ≤ 2 retries, no lyrics anywhere,
no real brands. Assets from `work/assets/` (licences in `team/assets.md`); copy
what you use into `projects/panchiko/assets/` and keep it < 40 MB total.
Test your module with a tiny page under `work/<role>/` and `node render.mjs … --still T --scale 0.5`.
