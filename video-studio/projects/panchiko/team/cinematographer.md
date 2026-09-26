# Cinematographer / Art Director: proposal

**Headline:** we see everything through his eyes, with few cuts. A cold, humming shop gives way to sun-blown open land. The texture is a rotting CD-R, used sparingly.

## 1. Camera language
- Eye height 1.68 m (a 1.80 m man). **Vertical FOV 60°** in 4:5 (about 50° horizontal, roughly a 28 mm lens). Never use a 90° game FOV: it is the "tech demo" giveaway. FOV changes only on cuts: 45° for inserts (CD in hands), 66° for the landscape.
- Head motion is seeded and deterministic. Breathing at 0.25 Hz (±3 mm, ±0.3° pitch). Walk bob: ±1.5 cm vertical, ±1 cm lateral, ±0.4° roll, with **footfalls locked to the verified beat grid**. Micro-sway is three incommensurate sines, each ≤0.2°. No per-frame noise. Head turns ease in and out at ≤60°/s (no strobing at 60 fps, so no motion blur is needed). The head leads, the body follows, with 2–3% overshoot.
- Hands: he **looks first, then reaches**. The camera settles on the object about 0.3 s before the right hand enters from the bottom-right edge (pale forearm, grey sleeve cuff). Idle hands leave the frame; never a floating viewmodel.
- **Stillness means attention.** The camera stops dead twice: when he spots the CD, and when he first sees the land.
- We glimpse his body once, reflected in dark fridge glass, backlit, with the face soft.
- 5–6 cuts in total. Each lands on a downbeat and has a motive: a blink (lids close over 4 frames), a look-down insert, or a match cut. Everything else is long takes.

## 2. Look
- **Shop:** flat overhead tubes at 4500 K with a green-cyan cast. Whites #EEF6F1, shadows teal-grey #1E3433. The only warm source is the hot-food cabinet (#FFB35C). One tube flickers on a seeded, irregular pattern, so you can see the hum. A second-hand box by the till nods to the real find (Oxfam, Sherwood, Nottingham, 21 July 2016, per Wikipedia).
- **The CD:** a burnt CD-R (Wikipedia: about 30 copies) in a slim case with the supplied cover used as-is. The underside is cyan dye with pinhole rot.
- **Outside:** sodium-orange lamps (#FF9A3C) against cyan shop spill on wet tarmac, under a navy sky (#0B1426). Kept desaturated, not blockbuster teal and orange.
- **"Nowhere":** high sun. Sky runs #3F7FD6 → #CFE8F6, grass #5DA83A → #A6D160, with big cumulus clouds, slightly overexposed with warm bloom. It should feel like a remembered early-2000s wallpaper, not a copy of one. Every axis flips: ceiling to none, cold to warm, tubes to sun, hum to air.
- **Era texture (global, subtle), using existing kit3d post:**
  - grain 0.04, refreshed every 2 frames
  - vignette 0.15
  - high-threshold bloom for halation around tubes
  - dispersion ≤0.1
  - lifted blacks and rolled highlights, like MiniDV or an early digicam
- **Signature: disc-rot blocks.** Small square macroblock tears and tint patches that echo the cover's collage squares. They appear only while the disc spins and during the transition.
- **Avoid:** VHS scanlines, fake REC HUDs, vaporwave grids, lens flares, god-rays, depth-of-field blur (the "blurry" complaint), glossy plastic PBR, a floaty camera.

## 3. Transition
It lands on the verified downbeat where the music opens up. The song's RMS lifts at about 0:54 and again at about 2:00; the editor should confirm by ear.
- **A. Look-down swap (recommended).** Outside, he looks down at the Discman in his hands and his thumb presses play. Rot blocks spread across the frame. He looks up and the car park is open land. The world swaps while it is hidden, all in one continuous take, and it is cheap to render.
- **B. Door threshold.** He pushes the door, overexposed sun floods in, and one step takes him onto grass. The hum cuts to the music.
- **C. Into the disc.** A macro push into the iridescent (thin-film) disc surface; the rainbow whites out, and the centre hole match-cuts to the sun.

## 4. Typography
- **Text lives in the world, not on the screen:** sunlit, moving with parallax, with grass hiding its base. Two options: pale mown letters across the hillside, read from the crest, or flat white boards on the ridge. Secondary lines fade in letter by letter on beats, low in the sky.
- Rendering: troika-three-text (MIT, SDF, stays crisp at full resolution).
- Fonts (OFL):
  - Archivo ExtraCondensed Black Italic for display, echoing the energy of the cover's wordmark
  - Inter for facts
  - VT323 for the Discman LCD
- **Watermark:** screen-space, bottom centre, 72 px up. Inter Medium 26 px, white at 55% with a soft shadow. It stays static for all 60 s.

## 5. Aspect
**4:5, 1080×1350.** It is native to the user's Instagram feed and matches earlier posts. It has 30% fewer pixels than 1080×1920, which matters on a renderer with no GPU; the saved budget goes into detail. It is tall enough for hands below the horizon and wide enough for landscape. For a 9:16 TikTok version, add sky and ground padding and keep text inside the central 4:5.
