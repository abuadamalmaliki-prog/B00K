#!/usr/bin/env python3
"""Beat-synced AMV edit v2: Reze clips + song chorus.
Every single cut lands on a beat. No gaps, no overlong holds."""
import subprocess, json, os, sys
import numpy as np

CLIP = "/home/user/B00K/edit_project/clip.mp4"
SONG = "/home/user/B00K/edit_project/song.webm"
OUT_DIR = "/home/user/B00K/edit_project/edit"
CLIPS_DIR = os.path.join(OUT_DIR, "clips_v2")
FINAL = os.path.join(OUT_DIR, "reze_edit_v2.mp4")
os.makedirs(CLIPS_DIR, exist_ok=True)

SONG_START = 60.0
SONG_END = 93.0
EDIT_DURATION = SONG_END - SONG_START

with open(os.path.join(OUT_DIR, "song_analysis_v2.json")) as f:
    analysis = json.load(f)

all_beats = analysis["beats"]  # ~172 BPM half-beats
downbeats = [all_beats[i] for i in range(0, len(all_beats), 2)]  # ~86 BPM

intervals = np.diff(downbeats)
print(f"Downbeats: {len(downbeats)}, interval: {np.mean(intervals)*1000:.0f}ms")

# Clip source segments - 48 segments to fill all 48 downbeat slots
# Each: (clip_start, clip_end)
# We need exactly as many segments as downbeat intervals
# downbeats has 48 entries → 47 intervals + final to EDIT_DURATION = 48 windows

sources = [
    # Atmospheric opener (2-beat windows, 4 cuts)
    (0.0,  1.2),   # city dark rain
    (1.2,  2.3),   # reze walking rain
    (2.3,  3.8),   # reze with flower
    (3.8,  5.4),   # reze face rain close
    # Building energy (1-beat windows, ~12 cuts)
    (5.4,  6.0),   # reze looking up
    (6.0,  6.8),   # reze contemplative
    (7.0,  7.8),   # reze and denji
    (8.0,  8.5),   # reze walking
    (8.5,  9.2),   # reze denji side
    (9.2, 10.0),   # walking together
    (10.0, 10.8),  # reze turning
    (11.0, 11.8),  # street scene
    (12.0, 12.8),  # reze front walk
    (12.8, 13.5),  # arcade entrance
    (14.0, 14.8),  # arcade walk
    (15.0, 16.0),  # reze arcade deep
    # Peak energy (1-beat windows, ~12 cuts)
    (16.0, 16.8),  # cafe interior
    (17.0, 17.8),  # reze at counter
    (18.0, 19.0),  # reze serving
    (19.0, 20.0),  # sitting down
    (20.0, 20.8),  # reze close sit
    (20.8, 21.5),  # reze emotion
    (21.5, 22.2),  # reze denji cafe
    (22.5, 23.2),  # reze smile
    (23.5, 24.2),  # reze portrait
    (24.5, 25.2),  # reze gentle
    (25.5, 26.2),  # reze warm look
    (26.5, 27.2),  # reze deep
    # Rapid fire half-beat (remaining cuts)
    (27.5, 28.0),  # reze close
    (28.0, 28.5),  # reze pensive
    (3.0,  3.5),   # rain detail
    (29.0, 29.5),  # reze down
    (5.0,  5.5),   # reze eyes up
    (30.0, 30.5),  # reze look away
    (30.5, 31.0),  # reze window
    (31.5, 32.0),  # reze turn
    (32.0, 32.5),  # reze gesture
    (33.0, 33.5),  # reze reach
    (34.0, 34.5),  # reze hair
    (34.5, 35.0),  # reze smile 2
    (35.0, 35.5),  # reze eyes close
    (35.5, 36.0),  # reze final close
    (36.0, 37.0),  # reze last smile
    (37.0, 38.0),  # reze ending
    (0.5,  1.5),   # city callback
    (6.5,  7.5),   # flower callback
]

def build_edl(downbeats, all_beats, sources, edit_duration):
    edl = []
    src_idx = 0

    # Phase 1: 2-downbeat cuts (0 → downbeat[8], 4 cuts spanning 2 downbeats each)
    beat_idx = 0
    for i in range(4):
        if src_idx >= len(sources):
            break
        out_start = downbeats[beat_idx]
        out_end = downbeats[beat_idx + 2] if beat_idx + 2 < len(downbeats) else edit_duration
        src = sources[src_idx]
        edl.append({
            "clip_start": src[0], "clip_end": src[1],
            "out_start": out_start, "out_end": out_end,
            "out_dur": out_end - out_start,
        })
        src_idx += 1
        beat_idx += 2

    # Phase 2: 1-downbeat cuts until we've used 28 sources (beat_idx 8 → ~30)
    target_phase2_end = 28
    while src_idx < target_phase2_end and src_idx < len(sources) and beat_idx + 1 <= len(downbeats):
        out_start = downbeats[beat_idx]
        out_end = downbeats[beat_idx + 1] if beat_idx + 1 < len(downbeats) else edit_duration
        src = sources[src_idx]
        edl.append({
            "clip_start": src[0], "clip_end": src[1],
            "out_start": out_start, "out_end": out_end,
            "out_dur": out_end - out_start,
        })
        src_idx += 1
        beat_idx += 1

    # Phase 3: half-beat rapid fire for the rest
    # Find position in all_beats
    current_time = downbeats[beat_idx] if beat_idx < len(downbeats) else edl[-1]["out_end"]
    ab_idx = 0
    for j, b in enumerate(all_beats):
        if b >= current_time - 0.01:
            ab_idx = j
            break

    while src_idx < len(sources) and ab_idx + 1 < len(all_beats):
        out_start = all_beats[ab_idx]
        out_end = all_beats[ab_idx + 1]
        if out_start >= edit_duration:
            break
        if out_end > edit_duration:
            out_end = edit_duration
        src = sources[src_idx]
        dur = out_end - out_start
        if dur > 0.05:
            edl.append({
                "clip_start": src[0], "clip_end": src[1],
                "out_start": out_start, "out_end": out_end,
                "out_dur": dur,
            })
        src_idx += 1
        ab_idx += 1

    # Fill any remaining time with the last source extended
    if edl and edl[-1]["out_end"] < edit_duration - 0.1:
        # Add remaining beats as 1-beat cuts recycling good moments
        fallback_sources = [
            (23.5, 24.5), (2.3, 3.5), (35.0, 36.5), (20.0, 21.0),
            (5.0, 6.5), (30.0, 32.0), (36.0, 38.0),
        ]
        fb_idx = 0
        last_end = edl[-1]["out_end"]

        # Find next downbeat after last_end
        for bi in range(len(downbeats)):
            if downbeats[bi] >= last_end - 0.01:
                beat_idx = bi
                break

        while beat_idx + 1 <= len(downbeats) and fb_idx < len(fallback_sources):
            out_start = downbeats[beat_idx]
            if out_start >= edit_duration:
                break
            out_end = downbeats[beat_idx + 1] if beat_idx + 1 < len(downbeats) else edit_duration
            if out_end > edit_duration:
                out_end = edit_duration
            src = fallback_sources[fb_idx]
            dur = out_end - out_start
            if dur > 0.05:
                edl.append({
                    "clip_start": src[0], "clip_end": src[1],
                    "out_start": out_start, "out_end": out_end,
                    "out_dur": dur,
                })
            fb_idx += 1
            beat_idx += 1

        # Final extension
        if edl[-1]["out_end"] < edit_duration - 0.1:
            edl[-1]["out_end"] = edit_duration
            edl[-1]["out_dur"] = edl[-1]["out_end"] - edl[-1]["out_start"]

    return edl

edl = build_edl(downbeats, all_beats, sources, EDIT_DURATION)
print(f"\nEDL: {len(edl)} cuts")
total = 0
for i, cut in enumerate(edl):
    print(f"  {i:2d}: [{cut['out_start']:6.3f}-{cut['out_end']:6.3f}] ({cut['out_dur']:.3f}s) "
          f"clip[{cut['clip_start']:5.1f}-{cut['clip_end']:5.1f}]")
    total += cut["out_dur"]
print(f"Total: {total:.2f}s / {EDIT_DURATION:.1f}s")

# Verify no overlaps and no gaps
for i in range(len(edl) - 1):
    gap = edl[i+1]["out_start"] - edl[i]["out_end"]
    if abs(gap) > 0.05:
        print(f"  WARNING: gap/overlap at cut {i}-{i+1}: {gap:.3f}s")

GRADE = (
    "eq=contrast=1.10:brightness=0.01:saturation=1.20,"
    "curves=r='0/0 0.25/0.22 0.5/0.53 0.75/0.80 1/1'"
    ":g='0/0 0.25/0.23 0.5/0.50 0.75/0.76 1/1'"
    ":b='0/0.03 0.25/0.28 0.5/0.53 0.75/0.73 1/0.95'"
)

print("\nExtracting segments...")
seg_files = []
for i, cut in enumerate(edl):
    out_file = os.path.join(CLIPS_DIR, f"seg_{i:03d}.mp4")
    clip_dur = cut["clip_end"] - cut["clip_start"]
    out_dur = cut["out_dur"]
    pts_factor = clip_dur / out_dur

    vf = f"setpts=PTS/{pts_factor},{GRADE}"

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{cut['clip_start']:.4f}",
        "-t", f"{clip_dur:.4f}",
        "-i", CLIP,
        "-vf", vf,
        "-an",
        "-c:v", "libx264", "-preset", "fast", "-crf", "17",
        "-pix_fmt", "yuv420p", "-r", "30",
        "-video_track_timescale", "30000",
        out_file,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  WARN seg {i}: {result.stderr[-200:]}")
        continue

    trimmed = os.path.join(CLIPS_DIR, f"trim_{i:03d}.mp4")
    cmd = [
        "ffmpeg", "-y", "-i", out_file,
        "-t", f"{out_dur:.4f}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "17",
        "-pix_fmt", "yuv420p", "-an",
        "-video_track_timescale", "30000",
        trimmed,
    ]
    subprocess.run(cmd, capture_output=True)

    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", trimmed],
        capture_output=True, text=True
    )
    actual = float(probe.stdout.strip()) if probe.stdout.strip() else 0
    seg_files.append((trimmed, out_dur, actual))
    status = "OK" if abs(actual - out_dur) < 0.05 else "DRIFT"
    print(f"  {i:2d}: target={out_dur:.3f}s actual={actual:.3f}s [{status}]")

print(f"\nConcat {len(seg_files)} segments...")
concat_list = os.path.join(OUT_DIR, "concat_v2.txt")
with open(concat_list, "w") as f:
    for tf, _, _ in seg_files:
        f.write(f"file '{tf}'\n")

concat_video = os.path.join(OUT_DIR, "concat_video_v2.mp4")
subprocess.run([
    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
    "-i", concat_list, "-c", "copy", concat_video,
], capture_output=True, check=True)

probe = subprocess.run(
    ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
     "-of", "csv=p=0", concat_video],
    capture_output=True, text=True
)
print(f"Concat: {probe.stdout.strip()}s")

print("Song extract...")
song_extract = os.path.join(OUT_DIR, "song_section_v2.aac")
subprocess.run([
    "ffmpeg", "-y",
    "-ss", str(SONG_START), "-t", str(EDIT_DURATION),
    "-i", SONG,
    "-c:a", "aac", "-b:a", "192k",
    "-af", f"afade=t=in:st=0:d=0.3,afade=t=out:st={EDIT_DURATION-1.0}:d=1.0",
    song_extract,
], capture_output=True)

print("Final mix...")
result = subprocess.run([
    "ffmpeg", "-y",
    "-i", concat_video, "-i", song_extract,
    "-c:v", "libx264", "-preset", "slow", "-crf", "17",
    "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "192k",
    "-shortest", "-movflags", "+faststart",
    FINAL,
], capture_output=True, text=True)
if result.returncode != 0:
    print(f"Error: {result.stderr[-300:]}")
    sys.exit(1)

probe = subprocess.run(
    ["ffprobe", "-v", "quiet", "-show_entries", "format=duration,size",
     "-of", "json", FINAL],
    capture_output=True, text=True
)
info = json.loads(probe.stdout)
dur = float(info["format"]["duration"])
size_mb = int(info["format"]["size"]) / 1024 / 1024
print(f"\n=== DONE: {dur:.1f}s, {size_mb:.1f}MB → {FINAL} ===")
