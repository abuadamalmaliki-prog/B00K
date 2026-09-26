# Engine lead: feasibility and architecture

## Measured (1080×1350, 60 fps, SwiftShader; other agents rendered at the same time, ±25 %)
| Test | naive | optimized, end-to-end |
|---|---|---|
| (a) night shop aisle: 3 900 products, fridges, panel ceiling, glossy floor | 1.19 s/frame | **0.47** |
| (b) field: 60 k wind blades, terrain, clouds, troika text | 1.46 s/frame | **0.475** |
| empty page (capture overhead) | | 0.096 |
| (b) `render-parallel`, 3 jobs | | 0.545 overall |

Stills: `out/eng-store-full.png`, `out/eng-field-full.png`. Clips: `out/eng-store.mp4`, `out/eng-field.mp4`. Code: `work/engine/`.
My view: both read as real places. The shop is sterile and the far land is plain.

## SwiftShader rules (A/B measured in-page)
- Anisotropic filtering 16× costs **+380 ms**, so use 1×. Mip-nearest takes 108 ms vs trilinear 154 ms.
- Each instance costs about **10 µs**, even with zero area. Baking 90 k blades into one merged geometry cut them from 1 114 ms to 298 ms. Merge static props and grass.
- MSAA costs +130–200 ms. Use FXAA instead (+20–50 ms).
- Draw front to back: occluders first, floor and sky last (159 → 120 ms).
- Bake static light and AO when the page loads. Shade only view-dependent terms per frame.
- Post takes 50–100 ms. Next step: put FXAA into the tonemap pass.
- Parallel jobs barely help, because each SwiftShader process already uses all 4 cores.

## Architecture
- **Scene modules** (`street`, `store`, `field`) each expose `build(renderer)` and `update(t, shot)`. They share `eng.js` (post, head motion, lightmap baker). Everything is built once per process, and only the active scene renders.
- **Shots** live in a data file: Catmull-Rom position keys, yaw/pitch keys, fov. Footstep phase comes from arc length, and head sway and breath are added on top. The film is mostly continuous POV. Time skips are cuts or blinks on confirmed downbeats.
- **Hands**: procedural skinned hand plus two-bone IK to keyframed wrist targets, with grip presets. This has no licence risk. A CC0 glTF body also works if its rig is clean.
- **CD case**: the cover is sRGB, mip-mapped and trilinear (the hero object only). The camera distance is clamped so the 1 000 px cover stays ≤ ~950 px on screen. FXAA is masked there so the cover is not softened.
- **3D text**: troika-three-text renders in headless (verified; SDF, sharp, ~20 ms). Per-letter reveals via glyph bounds.

## Budget
Scene ≤ 170 ms + post ≤ 60 ms + capture 100 ms ≈ **0.33 s/frame**. Realistic today: 0.40–0.47 s/frame.
**3 600 frames: about 25–28 min wall clock** (≈6 resumable runs). Two jobs render as fast as three.

**Verdict: feasible** at full resolution with no upscaling. The limits are art time, not the engine.
