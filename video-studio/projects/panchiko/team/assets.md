# Asset scout (Group B, Tech): findings

Every URL was checked with `curl -sIL`. Downloads (89 MB) are in `work/assets/`. Two SwiftShader smoke tests (`work/assets/_smoketest/index.html`, `body.html`, with screenshots) load all of it with three r170 from jsDelivr. Zero errors.

## 1. First-person body
- **Top pick: Quaternius Universal Base Characters male + Universal Animation Library 1 (both CC0).** 14k tris, UE-style 65-bone rig with full fingers, and 43 clips on the same bone names (Walk, Idle, PickUp_Table, Sitting…). Tested with `mixer.setTime(t)`.
  - Caveats: superhero build, underwear only. Clothes need a shader (shirt/jeans zones by bind-pose height) or procedural sleeves.
  - For first-person shots, scale the `Head` bone to 0. Use `T_Superhero_Male_Ligh.png` for the skin.
- **WebXR generic hands (MIT)** for close-ups. The joints ship flat: re-parent them with `attach()`, then `rotateX` curls the fingers (tested).
- **Grabbing the CD: procedural.** Keyframe a wrist target, solve two-bone IK, curl each finger with the thumb opposed, then `hand_r.attach(cdCase)` on the grip frame.
- **Mixamo is excluded** (not redistributable). The three.js example models Xbot, Soldier and Michelle are Mixamo.

## 2. Store
- Kenney **Mini Market** and **Food Kit** (CC0): freezers, shelves, register, onigiri, cans. Toy-like, so use them for blocking and background only.
- Poly Haven (CC0): fluorescent fixture, plastic crate (as the CD bin), wet-floor sign. Its cash register is vintage.
- **Procedural is better** for shelves, glass fridges (envmap + opacity, not transmission), counter, sliding doors, fascia, vinyl floor, invented labels and jewel cases. The hero case uses `cover.webp` as supplied.

## 3. Nature
- **Grass:** our own instanced blades with wind driven by `uTime = t`. MIT references: FluffyGrass, three-grass-demo, three-stylized. Avoid terra (CC BY-NC).
- A few Poly Haven hero plants (the dandelion is 55k tris) and **ez-tree** trees (MIT, 25k tris each).
- **Sky:** Poly Haven *kloofendal puresky*, 8192×4096 JPG. That is SwiftShader's max texture size, and at our frame size nothing is upscaled. Its 2k HDR is for lighting. Fallback: `Sky.js` plus fbm clouds.

## 4. Libraries (verified on r170)
- postprocessing 6.39.5 (Zlib).
- troika-three-text (needs 5 import-map entries).
- Loaders: GLTF, Draco, KTX2 (transcodes to ASTC on SwiftShader), meshopt, RGBELoader.
- Camera paths: `CatmullRomCurve3` plus our own easing. Theatre and GSAP aren't needed.
- **Tech lead:** Chromium warns that software-WebGL fallback is deprecated. Add `--enable-unsafe-swiftshader` to render.mjs.

## What failed
- Poly Pizza returned 403.
- The GitHub search API is blocked (used MCP search and raw files instead).
- Quaternius's official zip on itch.io is 122 MB. I took the CC0 Standard files from a GitHub mirror; its gltf names two missing textures, which I saved as copies.
- Poly Haven trees are 66–101 MB, so skipped.
- ambientCG has no linoleum.

| Name | URL | Licence | Size | For | Verified |
|---|---|---|---|---|---|
| Quaternius UBC male + UAL1 | github.com/NafisRayan/Animate-Rigged-Humanoid-No-Blender (mirror of quaternius.com) → `quaternius-ubc/` | CC0 | 24.5 MB | FP body, legs, reflection, clips | yes (200, rendered) |
| WebXR generic hand L/R | cdn.jsdelivr.net/npm/@webxr-input-profiles/assets@1.0.20/dist/profiles/generic-hand/ | MIT | 0.19 MB | close-up hands | yes (200, rendered) |
| Kenney Mini Market (20 GLB) | kenney.nl/assets/mini-market | CC0 | 0.88 MB | store blocking | yes (200, rendered) |
| Kenney Food Kit (22 GLB) | kenney.nl/assets/food-kit | CC0 | 0.40 MB | snacks/drinks | yes (200) |
| PH mounted_fluorescent_lights 1k | polyhaven.com/a/mounted_fluorescent_lights | CC0 | 1.86 MB | ceiling lights | yes (rendered) |
| PH plastic_crate_02 1k | polyhaven.com/a/plastic_crate_02 | CC0 | 1.84 MB | CD bin | yes (rendered) |
| PH WetFloorSign_01 1k | polyhaven.com/a/WetFloorSign_01 | CC0 | 0.27 MB | floor detail | yes (rendered) |
| PH CashRegister_01 1k | polyhaven.com/a/CashRegister_01 | CC0 | 1.04 MB | vintage (optional) | yes (200) |
| PH dandelion_01, flower_gazania, grass_medium_01 1k | polyhaven.com/a/… | CC0 | 3.1 / 2.85 / 3.07 MB | hero plants | yes (200) |
| PH kloofendal_48d_partly_cloudy_puresky | dl.polyhaven.org …/Tonemapped JPG/ + hdr/2k | CC0 | 22.2 + 5.45 MB | sky backdrop + light | yes (rendered) |
| PH phone_shop_1k, cobblestone_street_night_1k .hdr | polyhaven.com/a/phone_shop, /cobblestone_street_night | CC0 | 1.69 / 1.76 MB | interior/night reflections | yes (PMREM) |
| PH textures asphalt_02 2k, concrete_floor_worn_001 2k, laminate_floor_02 1k, leafy_grass 1k | polyhaven.com/a/… | CC0 | 9.32 / 2.00 / 1.83 / 3.67 MB | car park, pavement/floor breakup, counter, ground | yes (200) |
| Zen Maru Gothic Bold TTF, Inter 400/700 woff | github.com/google/fonts (ofl/), jsDelivr @fontsource/inter@5.3.0 | OFL-1.1 | 3.78 + 0.06 MB | invented signage, titles | yes (troika rendered Inter) |
| three@0.170.0 + addons, Draco, Basis, meshopt | cdn.jsdelivr.net/npm/three@0.170.0/ | MIT | CDN | core/loaders | yes (all 200, tested) |
| postprocessing 6.39.5 | cdn.jsdelivr.net/npm/postprocessing@6.39.5/build/index.js | Zlib | CDN | bloom/DOF/grade | yes (rendered) |
| troika-three-text 0.52.5 (+utils, worker-utils, webgl-sdf-generator, bidi-js) | cdn.jsdelivr.net/npm/troika-three-text@0.52.5/ | MIT | CDN | 3D text | yes (rendered) |
| @dgreenheck/ez-tree 1.1.0 | cdn.jsdelivr.net/npm/@dgreenheck/ez-tree@1.1.0/ | MIT | CDN, 3 MB | trees | yes (rendered) |
| three-mesh-bvh 0.9.15, simplex-noise 4.0.3 | jsDelivr | MIT | CDN | optional | yes (200) |
| FluffyGrass / three-grass-demo / three-stylized | github.com/thebenezer/FluffyGrass, James-Smyth/three-grass-demo, Steve245270533/three-stylized | MIT | reference | grass technique | yes (LICENSE 200) |
| spacejack/terra | github.com/spacejack/terra | CC BY-NC 4.0 | – | avoid | yes (licence read) |
| Poly Pizza (Quaternius mirror) | poly.pizza | CC0 | – | – | **no (403)** |
