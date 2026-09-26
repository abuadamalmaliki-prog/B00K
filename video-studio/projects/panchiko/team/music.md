# Music editor: timing and window

**Check by ear first:** `out/panchiko-beat-test.mp4`. Beat flashes, a bar-"1" flash with the bar number, section labels. It is 540×676 (H.264 needs an even height). Nothing gets cut until the user confirms it.

## Tempo and grid
- **87.0 BPM, 4/4, no drift** from 55 s to the end. The beats fit a straight grid (7 ms rms error). Bar = 2.759 s.
- Tools: madmom 0.17 (built from GitHub) and essentia RhythmExtractor2013. **The two agree 100% inside the window** (F = 1.00 at ±70 ms).
- **87 vs 174:** madmom's downbeat tracker jumped to 174 after 50 s. But the snare hits every other 87-BPM beat (backbeat on 2 and 4) and the chords change once per 87-BPM bar, so 87 is the tapped tempo. librosa's 117.5 is 4:3 against it (syncopation): rejected.
- **Which beat is "1":** chord changes are strongest there in every 8-bar block, madmom's downbeat score agrees, and the drop-out and the slam line up with it. Confidence is medium-high.
- 33–55 s is unstable in every tracker. Avoid it.

## Window: 176.016 → 236.706 s (song bars 64–85)
22 bars (60.69 s). It starts on a phrase downbeat and ends where the climax releases. For exactly 60.00 s, start at 176.705 (beat 2).

| film s | moment |
|---|---|
| 0–17.2 | Heavy 2-bar groove: store and discovery. Cut every 5.52 s. |
| 17.24–22.07 | **Quiet:** bass and kick drop out, a riser comes in. The CD / a held breath. |
| **22.07** | **Biggest moment:** the full band slams in. Cut to the landscape. |
| 41.38–44.14 | Bass thins, a second breath. |
| 44.14–52.4 | Loudest part (-4 LUFS). On-screen text goes here. |
| 52.41 | Cymbal wash. |
| 57.24 | Final heavy hits: end card. |
| 60.69 | The wall stops. Cut to black. |

Best part = the climax (198.1–236.7 s). It is the loudest and most distinctive section, and it comes right after the only drop-out. Runner-up: 54.7–79.5 s.

## Song map
Silence to 2.2 · intro · 32.6 A1 · 54.7 C · 79.5 A2 · 120.8 B1 · 167.7 B2 · 193.3 drop-out · **198.1 climax** · 236.7 outro decay · 259.6 silence. Labels are descriptive (vocals not analysed).

## Files
`work/music/timing.json` has the tempo, window, 88 beats, 22 downbeats, sections, accents and quiet spans. Times are given relative and absolute, plus 60 fps frame numbers. Scripts: `work/music/*.py` (madmom needs `PYTHONPATH=work/music/madmom_src`).

Untested alternative: splice the quiet intro (bars 1–8) into bar 72 for a calmer store scene.
