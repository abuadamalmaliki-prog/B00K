# Cinematographer / Art Director

**Headline:** his eyes, few cuts; a cold humming shop, then sun-blown open land. Texture: a rotting CD-R, used sparingly.

## 1. Camera
- Eye height 1.68 m. **Vertical FOV 60°** (≈28 mm feel); 45° for inserts, 66° for the landscape. Change FOV only on cuts. Never 90°: that reads as a game.
- Seeded, deterministic motion:
  - breathing 0.25 Hz, ±0.3°
  - walk bob ±1.5 cm, **footfalls on the verified beats**
  - micro-sway from 3 sines, ≤0.2°
  - no per-frame noise; turns ease in/out, ≤60°/s
- **Look first, then reach.** The right hand enters bottom-right after the gaze settles, and leaves when idle.
- **Stillness means attention.** The camera stops dead when he spots the CD and when he first sees the land.
- 5–6 cuts, each on a downbeat with a motive: a blink, a look-down insert, or a match cut. Otherwise long takes.

## 2. Look
- **Shop:** flat 4500 K tubes with a green-cyan cast, teal-grey shadows (#1E3433). One warm source: the hot-food cabinet (#FFB35C). One tube flickers irregularly, so the hum shows.
- **CD:** a burnt CD-R (≈30 copies, Wikipedia) with the supplied cover as-is; cyan dye with pinhole rot.
- **Outside:** sodium-orange lamps against cyan shop spill on wet tarmac, navy sky.
- **Nowhere:** high sun, sky #3F7FD6→#CFE8F6, grass #5DA83A→#A6D160, cumulus, slightly overexposed. Cold to warm, enclosed to open.
- **Texture** (existing kit3d post): grain 0.04, vignette 0.15, halation-style bloom, dispersion ≤0.1, lifted blacks, rolled highlights (MiniDV feel).
- **Disc-rot blocks:** square tears echoing the cover's collage, only while the disc spins and at the transition.
- **Avoid:** VHS scanlines, vaporwave grids, lens flares, depth-of-field blur, a floaty camera.

## 3. Transition
On the verified downbeat where the music opens (RMS lifts ≈0:54, ≈2:00; confirm by ear).
- **A. Look-down swap (recommended):** he looks down at the Discman and presses play; rot blocks spread; he looks up and the car park is open land.
- **B. Door:** overexposed sun floods through the door, and one step puts him on grass.
- **C. Into the disc:** push into the iridescent disc; it whites out and the centre hole match-cuts to the sun.

## 4. Typography
- **Text lives in the world, not on the screen:** sunlit, with parallax, grass hiding its base. Mown letters on the hillside or boards on the ridge.
- troika-three-text (MIT, SDF: crisp at full resolution).
- Fonts (OFL): Archivo ExtraCondensed Black Italic (display), Inter (facts), VT323 (Discman LCD).
- **Watermark:** screen-space, bottom centre, Inter Medium 26 px, white at 55%, static.

## 5. Aspect
**4:5, 1080×1350.** Native to Instagram and 30% fewer pixels than 9:16 on a CPU-only renderer, so more detail per frame.
