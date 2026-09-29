#!/usr/bin/env python3
"""Orkestrator video bantahan.

  python3 build.py prep            # selesaikan timeline + ekstrak frame klip pengkritik
  python3 build.py audio           # campur audio: nasyid (ducking) + suara klip
  python3 build.py render [--workers 4] [--only-still 30.5 out.png]
  python3 build.py encode out/final.mp4
  python3 build.py all out/final.mp4

Butuh: ffmpeg (env FFMPEG atau di PATH), node + playwright (npm install).
"""
import json, os, shutil, subprocess, sys, math

ROOT = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(ROOT, 'work')
FF = os.environ.get('FFMPEG', 'ffmpeg')
CARD_W = 900


def sh(cmd, **kw):
    r = subprocess.run(cmd, **kw)
    if r.returncode:
        sys.exit(f'gagal: {" ".join(map(str, cmd))[:200]}')


def resolve():
    P = json.load(open(os.path.join(ROOT, 'src', 'project.json'), encoding='utf-8'))
    t = 0.0
    for s in P['scenes']:
        if s['type'] == 'quote':
            clips = s['clips']
            lens = [b - a for a, b in clips]
            s['clipDur'] = sum(lens)
            s['cuts'] = [sum(lens[:i + 1]) for i in range(len(lens) - 1)]
            s['dur'] = s['lead'] + s['clipDur'] + s['tail']
            cum = [sum(lens[:i]) for i in range(len(lens))]
            for c in s['captions']:
                i = next(k for k, (a, b) in enumerate(clips) if a - 0.06 <= c['s'] <= b + 0.06)
                a, b = clips[i]
                c['ts'] = max(0.0, cum[i] + (c['s'] - a))
                c['te'] = min(cum[i] + (b - a), cum[i] + (c['e'] - a))
            s['_cum'] = cum
        s['start'] = t
        t += s['dur']
    P['total'] = t
    os.makedirs(WORK, exist_ok=True)
    json.dump(P, open(os.path.join(WORK, 'timeline.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return P


def prep():
    P = resolve()
    src = P['sources']['critic']
    fps = P['fps']
    for s in P['scenes']:
        if s['type'] != 'quote':
            continue
        d = os.path.join(WORK, 'frames', s['id'])
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(d)
        x, y, w, h = s['crop']
        H = round(CARD_W * h / w)
        n0 = 1
        for (a, b) in s['clips']:
            n = round((b - a) * fps)
            vf = f'fps={fps},crop={w}:{h}:{x}:{y},scale={CARD_W}:{H}:flags=lanczos,unsharp=5:5:0.55:3:3:0.0'
            sh([FF, '-hide_banner', '-loglevel', 'error', '-ss', f'{a:.3f}', '-i', src, '-frames:v', str(n), '-vf', vf,
                '-q:v', '3', '-start_number', str(n0), os.path.join(d, '%05d.jpg'), '-y'])
            n0 += n
        print(f"{s['id']}: {n0 - 1} frame, {s['clipDur']:.1f}s")
    print(f"total durasi: {P['total']:.1f}s ({P['total'] / 60:.2f} menit)")


def gain_expr(points):
    """piecewise-linear gain(t) sebagai ekspresi ffmpeg."""
    pts = sorted(points)
    e = f'{pts[-1][1]:.4f}'
    for (t0, g0), (t1, g1) in reversed(list(zip(pts, pts[1:]))):
        if t1 == t0:
            continue
        e = f"if(lt(t,{t1:.3f}),{g0:.4f}+({g1 - g0:.4f})*(t-{t0:.3f})/{t1 - t0:.3f},{e})"
    return f"if(lt(t,{pts[0][0]:.3f}),{pts[0][1]:.4f},{e})"


def audio():
    P = json.load(open(os.path.join(WORK, 'timeline.json'), encoding='utf-8'))
    T = P['total']
    critic = P['sources']['critic']
    nas = os.path.join(WORK, 'nasheed.wav')
    if not os.path.exists(nas):
        sh([FF, '-hide_banner', '-loglevel', 'error', '-i', P['sources']['nasheed'], '-vn', '-ac', '2', '-ar', '48000',
            '-af', 'loudnorm=I=-15:TP=-1.5:LRA=9', nas, '-y'])
    # --- kurva gain nasyid
    HI, LO = 0.85, 0.11
    pts = [(0, 0.0), (1.2, HI)]
    for s in P['scenes']:
        if s['type'] == 'quote':
            a = s['start']
            pts += [(a + 0.05, HI), (a + s['lead'] - 0.05, LO), (a + s['lead'] + s['clipDur'] + 0.1, LO), (a + s['lead'] + s['clipDur'] + 0.9, HI)]
    pts += [(T - 3.0, HI), (T, 0.0)]
    pts = sorted(set(pts))
    # --- suara klip
    inputs = ['-i', critic, '-i', nas, '-i', nas, '-i', nas, '-i', nas]
    fc, labels = [], []
    k = 0
    for s in P['scenes']:
        if s['type'] != 'quote':
            continue
        for i, (a, b) in enumerate(s['clips']):
            at = s['start'] + s['lead'] + s['_cum'][i]
            fc.append(f"[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.02,afade=t=out:st={b - a - 0.05:.3f}:d=0.05,"
                      f"aformat=sample_rates=48000:channel_layouts=stereo,adelay={int(at * 1000)}:all=1[v{k}]")
            labels.append(f'[v{k}]')
            k += 1
    fc.append(''.join(labels) + f'amix=inputs={len(labels)}:normalize=0:duration=longest,loudnorm=I=-14:TP=-1.5:LRA=7[voice]')
    # nasyid diulang dengan crossfade
    fc.append('[1:a][2:a]acrossfade=d=2.5:c1=tri:c2=tri[n12];[n12][3:a]acrossfade=d=2.5:c1=tri:c2=tri[n123];[n123][4:a]acrossfade=d=2.5:c1=tri:c2=tri[nloop]')
    fc.append(f"[nloop]atrim=0:{T:.3f},asetpts=PTS-STARTPTS,volume='{gain_expr(pts)}':eval=frame[music]")
    fc.append(f'[music][voice]amix=inputs=2:normalize=0:duration=first,apad,atrim=0:{T:.3f},alimiter=limit=0.94[out]')
    out = os.path.join(WORK, 'mix.m4a')
    sh([FF, '-hide_banner', '-loglevel', 'error', *inputs, '-filter_complex', ';'.join(fc), '-map', '[out]', '-c:a', 'aac', '-b:a', '192k', out, '-y'])
    print('audio ->', out)


def render(args):
    cmd = ['node', os.path.join(ROOT, 'src', 'render.mjs')] + args
    sh(cmd, cwd=ROOT)


def encode(outfile):
    P = json.load(open(os.path.join(WORK, 'timeline.json'), encoding='utf-8'))
    os.makedirs(os.path.dirname(os.path.abspath(outfile)), exist_ok=True)
    sh([FF, '-hide_banner', '-loglevel', 'error', '-framerate', str(P['fps']), '-i', os.path.join(WORK, 'out', '%06d.jpg'),
        '-i', os.path.join(WORK, 'mix.m4a'), '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', 'medium', '-crf', '17',
        '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-c:a', 'copy', '-shortest', outfile, '-y'])
    print('video ->', outfile)


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'all'
    rest = sys.argv[2:]
    if cmd == 'prep':
        prep()
    elif cmd == 'audio':
        audio()
    elif cmd == 'render':
        render(rest)
    elif cmd == 'encode':
        encode(rest[0])
    elif cmd == 'all':
        prep(); audio(); render([]); encode(rest[0] if rest else os.path.join(ROOT, 'out', 'final.mp4'))
    else:
        sys.exit(__doc__)
