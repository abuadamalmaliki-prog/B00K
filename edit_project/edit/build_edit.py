#!/usr/bin/env python3
"""Beat-synced AMV edit: Reze clips + song.
Cuts on beat, speed ramps, color grade, crossfades."""
import subprocess, json, os, math

CLIP = "/home/user/B00K/edit_project/clip.mp4"
SONG = "/home/user/B00K/edit_project/song.webm"
OUT_DIR = "/home/user/B00K/edit_project/edit"
CLIPS_DIR = os.path.join(OUT_DIR, "clips_graded")
FINAL = os.path.join(OUT_DIR, "reze_edit.mp4")
os.makedirs(CLIPS_DIR, exist_ok=True)

# Song section to use (seconds into the song)
SONG_START = 5.0
SONG_END = 38.0
EDIT_DURATION = SONG_END - SONG_START  # ~33s

# Load beat analysis
with open(os.path.join(OUT_DIR, "song_analysis.json")) as f:
    analysis = json.load(f)

# Get beats within our song section (offset to 0-based edit time)
beats_raw = [b for b in analysis["beats"] if SONG_START <= b <= SONG_END]
beats = [b - SONG_START for b in beats_raw]
print(f"Using {len(beats)} beats over {EDIT_DURATION:.1f}s")

# Best Reze moments from the clip (hand-picked from timeline views)
# Each: (clip_start, clip_end, description, speed_factor)
# speed_factor: 1.0 = normal, 0.6 = slow-mo, 1.5 = slightly sped up
segments = [
    # Intro - city establishing (slow, atmospheric)
    (0.0,   1.8,  "city establishing",     0.7),
    # Reze walking in the rain/station
    (1.8,   3.2,  "reze station close",    0.8),
    # Close-up contemplative
    (3.2,   4.8,  "reze looking down",     0.7),
    # Eating scene
    (4.8,   5.8,  "reze eating",           0.9),
    # Close face
    (5.8,   6.8,  "reze face close",       0.8),
    # Reze + Denji meeting
    (7.0,   8.2,  "reze denji meet",       1.0),
    # Walking together
    (8.5,  10.0,  "walking together",      1.0),
    # Street scenes
    (10.0, 11.5,  "street talking",        1.0),
    # More walking
    (11.5, 13.0,  "denji reze street",     1.0),
    # Indoor scenes - pace picks up
    (13.5, 14.8,  "indoor entrance",       1.0),
    (15.0, 16.5,  "cafe scene 1",          1.0),
    (17.0, 18.5,  "cafe interaction",      1.0),
    (19.0, 20.0,  "sitting together",      1.1),
    (20.5, 21.5,  "reze gesture",          1.0),
    # Emotional close-ups - faster cuts
    (22.0, 23.2,  "reze emotional 1",      0.8),
    (23.5, 24.5,  "reze smile",            0.8),
    (25.0, 26.0,  "reze close indoor",     0.9),
    (26.5, 27.5,  "reze laughing",         0.8),
    (27.5, 28.8,  "reze talking",          0.9),
    (29.0, 30.0,  "phone scene",           1.0),
    (30.5, 32.0,  "quiet moment",          0.7),
    (32.0, 33.5,  "reze window",           0.7),
    (34.0, 35.5,  "reze looking up",       0.8),
    (35.5, 37.0,  "final close",           0.6),
]

# Map segments to beats: distribute segments across beat groups
# Early beats get longer segments (slow pacing), later beats get shorter (faster cuts)
def assign_segments_to_beats(beats, segments):
    """Assign clip segments to beat intervals, pacing up as energy builds."""
    edl = []
    n_beats = len(beats)
    n_segs = len(segments)

    if n_beats < 2:
        return []

    # Create beat intervals
    intervals = []
    for i in range(len(beats) - 1):
        intervals.append((beats[i], beats[i+1]))
    # Add final interval to end
    intervals.append((beats[-1], EDIT_DURATION))

    # First third: 1 segment per 2-3 beats (slow)
    # Middle third: 1 segment per 1-2 beats
    # Final third: 1 segment per beat (fast cuts)
    seg_idx = 0
    beat_idx = 0

    while seg_idx < n_segs and beat_idx < len(intervals):
        # How far through the edit are we?
        progress = beat_idx / len(intervals)

        if progress < 0.3:
            # Slow section: span 3 beats
            span = 3
        elif progress < 0.6:
            # Medium: span 2 beats
            span = 2
        else:
            # Fast: 1 beat per cut
            span = 1

        # Calculate output time range
        out_start = intervals[beat_idx][0]
        end_beat = min(beat_idx + span, len(intervals)) - 1
        out_end = intervals[end_beat][1]

        seg = segments[seg_idx]
        edl.append({
            "clip_start": seg[0],
            "clip_end": seg[1],
            "out_start": out_start,
            "out_end": out_end,
            "speed": seg[3],
            "desc": seg[2],
        })

        seg_idx += 1
        beat_idx += span

    return edl

edl = assign_segments_to_beats(beats, segments)
print(f"EDL has {len(edl)} cuts")

# Color grade filter — warm cinematic with slight teal/orange push
GRADE = (
    "eq=contrast=1.08:brightness=0.02:saturation=1.15,"
    "curves=r='0/0 0.25/0.22 0.5/0.52 0.75/0.79 1/1'"
    ":g='0/0 0.25/0.24 0.5/0.50 0.75/0.76 1/1'"
    ":b='0/0.02 0.25/0.27 0.5/0.52 0.75/0.74 1/0.96'"
)

# Extract each segment with grade + audio fades
print("\nExtracting segments...")
seg_files = []
for i, cut in enumerate(edl):
    out_duration = cut["out_end"] - cut["out_start"]
    clip_duration = cut["clip_end"] - cut["clip_start"]

    # Calculate PTS factor to fit clip segment into output duration
    # If speed < 1, we slow down (need more clip time)
    # We adjust setpts to match the output duration
    pts_factor = clip_duration / out_duration

    out_file = os.path.join(CLIPS_DIR, f"seg_{i:03d}.mp4")

    # Video filter: grade + speed adjust + 30ms audio fades
    vf = f"setpts=PTS/{pts_factor},{GRADE}"

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(cut["clip_start"]),
        "-t", str(clip_duration),
        "-i", CLIP,
        "-vf", vf,
        "-an",  # We'll use the song audio, not clip audio
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        out_file,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  WARN seg {i}: {result.stderr[-200:]}")
    else:
        # Verify actual duration
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", out_file],
            capture_output=True, text=True
        )
        actual_dur = float(probe.stdout.strip()) if probe.stdout.strip() else 0
        seg_files.append((out_file, out_duration, actual_dur))
        print(f"  seg_{i:03d}: {cut['desc']:20s} clip[{cut['clip_start']:.1f}-{cut['clip_end']:.1f}] "
              f"→ out[{cut['out_start']:.2f}-{cut['out_end']:.2f}] ({out_duration:.2f}s) actual={actual_dur:.2f}s")

# Build concat file — use the exact output durations by trimming each segment
print(f"\nBuilding concat from {len(seg_files)} segments...")
concat_list = os.path.join(OUT_DIR, "concat.txt")
trimmed_files = []

for i, (seg_file, target_dur, actual_dur) in enumerate(seg_files):
    trimmed = os.path.join(CLIPS_DIR, f"trim_{i:03d}.mp4")
    # Trim to exact target duration + apply 30ms audio fades at boundaries
    cmd = [
        "ffmpeg", "-y",
        "-i", seg_file,
        "-t", str(target_dur),
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-an",
        trimmed,
    ]
    subprocess.run(cmd, capture_output=True)
    trimmed_files.append(trimmed)

with open(concat_list, "w") as f:
    for tf in trimmed_files:
        f.write(f"file '{tf}'\n")

# Concat all video segments
concat_video = os.path.join(OUT_DIR, "concat_video.mp4")
cmd = [
    "ffmpeg", "-y",
    "-f", "concat", "-safe", "0",
    "-i", concat_list,
    "-c", "copy",
    concat_video,
]
result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode != 0:
    print(f"Concat error: {result.stderr[-300:]}")
else:
    # Check concat duration
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", concat_video],
        capture_output=True, text=True
    )
    print(f"Concat video duration: {probe.stdout.strip()}s")

# Extract song section and mix with video
print("\nMixing with song...")
song_extract = os.path.join(OUT_DIR, "song_section.aac")
cmd = [
    "ffmpeg", "-y",
    "-ss", str(SONG_START),
    "-t", str(EDIT_DURATION),
    "-i", SONG,
    "-c:a", "aac", "-b:a", "192k",
    # Fade in first 0.5s, fade out last 1s
    "-af", f"afade=t=in:st=0:d=0.5,afade=t=out:st={EDIT_DURATION-1.5}:d=1.5",
    song_extract,
]
subprocess.run(cmd, capture_output=True)

# Final compose: video + song
cmd = [
    "ffmpeg", "-y",
    "-i", concat_video,
    "-i", song_extract,
    "-c:v", "libx264", "-preset", "slow", "-crf", "18",
    "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "192k",
    "-shortest",
    "-movflags", "+faststart",
    FINAL,
]
result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode != 0:
    print(f"Final mix error: {result.stderr[-300:]}")
else:
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration,size",
         "-of", "json", FINAL],
        capture_output=True, text=True
    )
    info = json.loads(probe.stdout)
    dur = float(info["format"]["duration"])
    size_mb = int(info["format"]["size"]) / 1024 / 1024
    print(f"\n✓ Final edit: {dur:.1f}s, {size_mb:.1f}MB → {FINAL}")

print("\nDone.")
