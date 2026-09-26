#!/usr/bin/env node
/*
 * render.mjs — render an HTML composition (see studio.js) to a video file.
 *
 *   node render.mjs examples/three-scene/index.html -o out/three.mp4
 *
 * Options:
 *   -o, --out FILE      output file (.mp4, .mov, .webm). Default: out/<name>.mp4
 *   --fps N             override frames per second
 *   --duration S        override duration in seconds
 *   --from S --to S     render only part of the timeline
 *   --scale X           render at a fraction of full size (0.5 = quick draft)
 *   --crf N             quality for .mp4/.webm: lower is better and bigger (default 18 / 28)
 *   --preset P          x264 speed preset for .mp4 (default medium)
 *   --no-audio          video only (render-parallel.mjs adds the audio once, at the end)
 *   --transparent       keep the background transparent (.mov → ProRes 4444, .webm → VP9 alpha)
 *   --still S           save a single PNG of time S instead of a video
 *   --audio-only FILE   write only the mixed, limited audio track (.m4a) — no frames
 *   --prepare           extract all footage into the cache (out/.cache/footage) and exit
 *   --info FILE         write the composition's size, fps and duration as JSON and exit
 */
import { chromium } from 'playwright';
import { spawn, spawnSync } from 'node:child_process';
import crypto from 'node:crypto';
import { once } from 'node:events';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
// Extracted footage frames, shared by every render (stills, drafts, parallel chunks).
const CACHE = path.join(ROOT, 'out', '.cache', 'footage');
// Bump when the extraction filters change, so stale cached frames are not reused.
const EXTRACT_VERSION = 2;

// Master bus: 1 dB of headroom, then a lookahead limiter with a −1 dBFS ceiling.
// Songs are often mastered past full scale; without this the AAC encoder clips them.
const HEADROOM_DB = 1;
const CEILING = 0.891;
const AAC = ['-c:a', 'aac', '-b:a', '256k', '-ar', '48000'];

const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.mjs': 'text/javascript',
  '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png',
  '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.gif': 'image/gif',
  '.mp4': 'video/mp4', '.webm': 'video/webm', '.mov': 'video/quicktime', '.mp3': 'audio/mpeg',
  '.wav': 'audio/wav', '.m4a': 'audio/mp4', '.ttf': 'font/ttf', '.otf': 'font/otf',
  '.woff': 'font/woff', '.woff2': 'font/woff2', '.glb': 'model/gltf-binary', '.gltf': 'model/gltf+json',
};

function parseArgs(argv) {
  const opts = { input: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = () => argv[++i];
    if (a === '-o' || a === '--out') opts.out = next();
    else if (a === '--fps') opts.fps = +next();
    else if (a === '--duration') opts.duration = +next();
    else if (a === '--from') opts.from = +next();
    else if (a === '--to') opts.to = +next();
    else if (a === '--scale') opts.scale = +next();
    else if (a === '--crf') opts.crf = next();
    else if (a === '--preset') opts.preset = next();
    else if (a === '--no-audio') opts.noAudio = true;
    else if (a === '--still') opts.still = +next();
    else if (a === '--transparent') opts.transparent = true;
    else if (a === '--audio-only') opts.audioOnly = next();
    else if (a === '--prepare') opts.prepare = true;
    else if (a === '--info') opts.info = next();
    else if (a === '-h' || a === '--help') opts.help = true;
    else if (!opts.input) opts.input = a;
    else throw new Error(`Unexpected argument: ${a}`);
  }
  return opts;
}

function fail(msg) {
  console.error(`render: ${msg}`);
  process.exit(1);
}

function requireFfmpeg() {
  if (spawnSync('ffmpeg', ['-version']).status !== 0) {
    fail('ffmpeg not found. Install it with: apt-get install -y ffmpeg');
  }
}

function run(cmd, args) {
  const r = spawnSync(cmd, args, { encoding: 'utf8' });
  if (r.status !== 0) throw new Error(`${cmd} failed:\n${r.stderr}`);
  return r.stdout;
}

const ratio = (s) => { const [a, b = 1] = String(s || '').split('/').map(Number); return b ? a / b : 0; };

/** Frame rate (as ffmpeg's exact rational), duration and whether there is sound — once per source. */
const probes = new Map();
function probe(src) {
  if (!probes.has(src)) {
    const r = spawnSync('ffprobe', ['-v', 'error', '-show_entries', 'stream=codec_type,avg_frame_rate,r_frame_rate:format=duration',
      '-of', 'json', src], { encoding: 'utf8' });
    const j = r.status === 0 ? JSON.parse(r.stdout) : {};
    const streams = j.streams || [];
    const video = streams.find((s) => s.codec_type === 'video');
    const rate = video && [video.avg_frame_rate, video.r_frame_rate].find((x) => ratio(x) > 0 && ratio(x) <= 240);
    probes.set(src, { rate, duration: +j.format?.duration || Infinity, audio: streams.some((s) => s.codec_type === 'audio') });
  }
  return probes.get(src);
}

function serve(footageDirs) {
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, 'http://x');
    let root = ROOT;
    let file;
    if (url.pathname.startsWith('/__footage/')) {
      // /__footage/<name>/<frame>.jpg → that clip's directory in the cache.
      const [name, frame = ''] = url.pathname.slice('/__footage/'.length).split('/').map(decodeURIComponent);
      root = footageDirs[name];
      file = root && path.join(root, frame);
    } else {
      file = path.join(ROOT, decodeURIComponent(url.pathname));
    }
    if (!file || !file.startsWith(root)) {
      res.writeHead(403).end();
      return;
    }
    if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file, 'index.html');
    fs.readFile(file, (err, data) => {
      if (err) { res.writeHead(404).end(); return; }
      res.writeHead(200, { 'content-type': MIME[path.extname(file).toLowerCase()] || 'application/octet-stream' });
      res.end(data);
    });
  });
  return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve(server)));
}

/** Map a src used inside the composition to something ffmpeg can open. */
function resolveMedia(src, pageUrl, origin) {
  const url = new URL(src, pageUrl);
  if (url.origin === origin) return path.join(ROOT, decodeURIComponent(url.pathname));
  return url.href;
}

function normalizeFootage(spec) {
  return typeof spec === 'string' ? { src: spec, start: 0, from: 0 } : { start: 0, from: 0, ...spec };
}

/**
 * How each footage entry is extracted. Entries with the same source, window,
 * rate and size share one cache directory, so declaring a clip several times
 * (e.g. three slots of one source for a stacked layout) costs nothing extra.
 */
function planFootage(footage, { fps, duration, box, pageUrl, origin }) {
  const plans = {};
  for (const [name, f] of Object.entries(footage)) {
    const src = resolveMedia(f.src, pageUrl, origin);
    const remote = /^https?:/.test(src);
    if (!remote && !fs.existsSync(src)) fail(`footage "${name}" not found: ${f.src}`);
    const info = probe(src);
    // The source's own frame rate, capped at the composition's: at 120 fps a 30 fps
    // clip would otherwise be extracted as four identical copies of every frame.
    const rate = info.rate && ratio(info.rate) < fps ? info.rate : String(fps);
    // Manual clips keep everything from `from` to the end of the source unless `duration` says otherwise.
    const span = Math.max(0.1, f.duration ?? (f.manual && isFinite(info.duration) ? info.duration - f.from : duration - f.start + 1));
    const sharpen = f.sharpen ?? 0.4;
    const stat = remote ? {} : fs.statSync(src);
    const key = crypto.createHash('sha1')
      .update(JSON.stringify([EXTRACT_VERSION, src, stat.size, stat.mtimeMs, f.from, span, rate, box, sharpen]))
      .digest('hex').slice(0, 20);
    plans[name] = { src, from: f.from, span, rate, fps: ratio(rate), box, sharpen, dir: path.join(CACHE, key) };
  }
  return plans;
}

/** Extract one clip's frames into its cache directory, unless an earlier render already did. */
async function extract(p) {
  if (fs.existsSync(p.dir)) return { count: fs.readdirSync(p.dir).length, cached: true };
  const tmp = `${p.dir}.tmp-${process.pid}-${crypto.randomBytes(3).toString('hex')}`;
  fs.mkdirSync(tmp, { recursive: true });
  // Lanczos and never upscaling (the GPU does any enlarging), then light
  // contrast-adaptive sharpening on luma only: crisp edges without halos or colour fringes.
  const vf = [
    `fps=${p.rate}`,
    `scale=w='min(iw,${p.box})':h='min(ih,${p.box})':force_original_aspect_ratio=decrease:flags=lanczos`,
    p.sharpen > 0 && `cas=strength=${p.sharpen}:planes=1`,
  ].filter(Boolean).join(',');
  const ff = spawn('ffmpeg', ['-v', 'error', '-ss', String(p.from), '-i', p.src, '-t', String(p.span), '-an',
    '-vf', vf, '-q:v', '2', path.join(tmp, '%06d.jpg')], { stdio: ['ignore', 'ignore', 'pipe'] });
  let err = '';
  ff.stderr.on('data', (d) => { err += d; });
  const [code] = await once(ff, 'exit');
  const count = code === 0 ? fs.readdirSync(tmp).length : 0;
  if (!count) {
    fs.rmSync(tmp, { recursive: true, force: true });
    throw new Error(`could not extract frames from ${p.src} at ${p.from}s${err ? `:\n${err}` : ' (is `from` past the end?)'}`);
  }
  // Another render may have finished the same clip meanwhile; then keep theirs.
  try { fs.renameSync(tmp, p.dir); } catch { fs.rmSync(tmp, { recursive: true, force: true }); }
  return { count, cached: false };
}

/** Extract every distinct clip, a few at a time. Returns name -> { count, fps } for studio.js. */
async function extractAll(plans, jobs = 3) {
  const distinct = [...new Map(Object.values(plans).map((p) => [p.dir, p])).values()];
  const queue = [...distinct];
  const done = new Map();
  const t0 = Date.now();
  await Promise.all(Array.from({ length: Math.min(jobs, queue.length) }, async () => {
    while (queue.length) {
      const p = queue.shift();
      done.set(p.dir, await extract(p));
    }
  }));
  const fresh = [...done.values()].filter((r) => !r.cached);
  if (distinct.length) {
    const frames = fresh.reduce((n, r) => n + r.count, 0);
    console.log(`render: footage — ${Object.keys(plans).length} clips, ${distinct.length - fresh.length} cached` +
      (fresh.length ? `, ${fresh.length} extracted (${frames} frames) in ${((Date.now() - t0) / 1000).toFixed(1)}s` : ''));
  }
  return Object.fromEntries(Object.entries(plans).map(([name, p]) => [name, { count: done.get(p.dir).count, fps: p.fps }]));
}

function encoderArgs(out, transparent, crf, preset) {
  const ext = path.extname(out).toLowerCase();
  if (ext === '.mov') {
    return transparent
      ? ['-c:v', 'prores_ks', '-profile:v', '4444', '-pix_fmt', 'yuva444p10le', '-c:a', 'pcm_s16le']
      : ['-c:v', 'prores_ks', '-profile:v', '3', '-pix_fmt', 'yuv422p10le', '-c:a', 'pcm_s16le'];
  }
  if (ext === '.webm') {
    return ['-c:v', 'libvpx-vp9', '-b:v', '0', '-crf', crf ?? '28', '-pix_fmt', transparent ? 'yuva420p' : 'yuv420p', '-c:a', 'libopus'];
  }
  if (transparent) fail('transparent output needs a .mov or .webm file');
  return ['-c:v', 'libx264', '-preset', preset ?? 'medium', '-crf', crf ?? '18', '-pix_fmt', 'yuv420p', ...AAC, '-movflags', '+faststart'];
}

/**
 * ffmpeg inputs and a filter graph mixing every audio entry of the config into [aout],
 * covering rangeStart…rangeEnd of the timeline. Input numbering starts at firstInput.
 */
function audioGraph(config, footage, { pageUrl, origin, duration, rangeStart, rangeEnd, firstInput }) {
  const inputs = [];
  const chains = [];
  const entries = (config.audio || []).map((a) => {
    if (a.footage) {
      const f = footage[a.footage];
      if (!f) fail(`audio refers to unknown footage "${a.footage}"`);
      return { src: f.src, start: f.start, from: f.from, ...a };
    }
    return { start: 0, from: 0, ...a };
  });
  for (const a of entries) {
    const src = resolveMedia(a.src, pageUrl, origin);
    const info = probe(src);
    if (!info.audio) {
      console.warn(`render: no audio stream in ${a.src}, skipping`);
      continue;
    }
    // Shape the entry on its own clock (it plays from `from` for `duration`, or until
    // the composition or the source ends), then cut out the part inside the range —
    // so fades land in the same place whether the whole timeline or a slice is rendered.
    const len = Math.min(a.duration ?? Infinity, duration - a.start, info.duration - a.from);
    const cut0 = Math.max(0, rangeStart - a.start);
    const cut1 = Math.min(len, rangeEnd - a.start);
    if (!(cut1 > cut0)) continue;
    const delay = Math.max(0, a.start - rangeStart);
    const curve = a.curve || 'qsin';
    // Always a few milliseconds of fade: a waveform cut mid-cycle clicks.
    const fadeIn = Math.max(a.fadeIn || 0, 0.005);
    const fadeOut = Math.max(a.fadeOut || 0, 0.005);
    const idx = firstInput + inputs.length / 4;
    inputs.push('-ss', String(a.from), '-i', src);
    const chain = [
      'aresample=48000', 'aformat=sample_fmts=fltp:channel_layouts=stereo',
      `atrim=0:${len}`, 'asetpts=PTS-STARTPTS', `volume=${a.volume ?? 1}`,
      `afade=t=in:st=0:d=${fadeIn}:curve=${curve}`,
      `afade=t=out:st=${Math.max(0, len - fadeOut)}:d=${fadeOut}:curve=${curve}`,
      `atrim=${cut0}:${cut1}`, 'asetpts=PTS-STARTPTS',
      `adelay=${Math.round(delay * 48000)}S:all=1`,
    ];
    chains.push(`[${idx}:a]${chain.join(',')}[a${chains.length}]`);
  }
  if (!chains.length) return { inputs: [], graph: null };
  const len = rangeEnd - rangeStart;
  const master = [
    `volume=-${HEADROOM_DB}dB`,
    `alimiter=limit=${CEILING}:attack=1:release=50:level=false:latency=1`,
    `apad=whole_dur=${len}`, `atrim=0:${len}`,
    'aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo',
  ];
  const labels = chains.map((_, i) => `[a${i}]`).join('');
  const graph = `${chains.join(';')};${labels}amix=inputs=${chains.length}:normalize=0:duration=longest,${master.join(',')}[aout]`;
  return { inputs, graph };
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (opts.help || !opts.input) {
    console.log(fs.readFileSync(fileURLToPath(import.meta.url), 'utf8').split('*/')[0].replace(/^[\s\S]*?\/\*\n/, '').replace(/^ \* ?/gm, ''));
    process.exit(opts.help ? 0 : 1);
  }
  requireFfmpeg();

  const input = path.resolve(opts.input);
  if (!input.startsWith(ROOT + path.sep)) fail(`composition must live inside ${ROOT}`);
  if (!fs.existsSync(input)) fail(`not found: ${opts.input}`);

  const name = path.basename(input) === 'index.html' ? path.basename(path.dirname(input)) : path.basename(input, '.html');
  const out = path.resolve(opts.out || path.join(ROOT, 'out', opts.still != null ? `${name}.png` : `${name}.mp4`));
  const framesWanted = !(opts.info || opts.audioOnly || opts.prepare);
  if (framesWanted) fs.mkdirSync(path.dirname(out), { recursive: true });

  const footageDirs = {};
  const server = await serve(footageDirs);
  const origin = `http://127.0.0.1:${server.address().port}`;
  const rel = path.relative(ROOT, input).split(path.sep).map(encodeURIComponent).join('/');
  const pageUrl = `${origin}/${rel}?render${opts.transparent ? '&transparent' : ''}`;

  const browser = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required', '--font-render-hinting=none'] });
  try {
    const open = async (contextOpts) => {
      const page = await (await browser.newContext(contextOpts)).newPage();
      page.on('pageerror', (e) => console.error(`page error: ${e.message}`));
      page.on('console', (m) => { if (m.type() === 'error') console.error(`page console: ${m.text()}`); });
      await page.goto(pageUrl, { waitUntil: 'load', timeout: 120_000 });
      await page.waitForFunction(() => window.Studio, null, { timeout: 30_000 });
      return page;
    };

    // Load once to read the composition's size, then again at that exact size and scale.
    const probePage = await open({});
    const config = await probePage.evaluate(() => window.Studio.config);
    await probePage.context().close();

    const fps = opts.fps || config.fps;
    const duration = opts.duration || config.duration;
    const { width, height } = config;
    const scale = opts.scale || 1;
    const rangeStart = Math.max(0, opts.from || 0);
    const rangeEnd = Math.min(duration, opts.to ?? duration);
    const footage = Object.fromEntries(Object.entries(config.footage || {}).map(([k, v]) => [k, normalizeFootage(v)]));
    const audioFor = (firstInput) => audioGraph(config, footage, { pageUrl, origin, duration, rangeStart, rangeEnd, firstInput });

    if (opts.info) {
      const info = { name, width, height, fps, duration, footage: Object.keys(footage).length, audio: !!audioFor(0).graph };
      fs.mkdirSync(path.dirname(path.resolve(opts.info)), { recursive: true });
      fs.writeFileSync(opts.info, JSON.stringify(info, null, 2));
    }
    if (opts.audioOnly) {
      const audio = audioFor(0);
      if (!audio.graph) console.log('render: this composition has no audio');
      else {
        fs.mkdirSync(path.dirname(path.resolve(opts.audioOnly)), { recursive: true });
        run('ffmpeg', ['-y', '-v', 'error', ...audio.inputs, '-filter_complex', audio.graph, '-map', '[aout]',
          ...AAC, '-movflags', '+faststart', opts.audioOnly]);
        console.log(`render: wrote audio ${path.relative(process.cwd(), path.resolve(opts.audioOnly))} (${(rangeEnd - rangeStart).toFixed(2)}s)`);
      }
    }

    // Frames are extracted at the size they will be drawn, never above the source's own.
    const box = Math.round(Math.max(width, height) * scale);
    const plans = planFootage(footage, { fps, duration, box, pageUrl, origin });
    if (!framesWanted) {
      if (opts.prepare) await extractAll(plans);
      return;
    }

    // Open the render page while ffmpeg extracts the footage.
    const [page, info] = await Promise.all([open({ viewport: { width, height }, deviceScaleFactor: scale }), extractAll(plans)]);
    for (const [k, p] of Object.entries(plans)) footageDirs[k] = p.dir;
    await page.evaluate((f) => { window.Studio.config.fps = f; }, fps);
    await page.evaluate((i) => window.Studio._setFootage(i), info);
    await page.evaluate(() => window.Studio._whenReady());

    const shoot = () => page.screenshot({
      type: opts.transparent || opts.still != null ? 'png' : 'jpeg',
      quality: opts.transparent || opts.still != null ? undefined : 95,
      omitBackground: !!opts.transparent,
    });

    if (opts.still != null) {
      await page.evaluate((t) => window.Studio._seek(t), opts.still);
      fs.writeFileSync(out, await shoot());
      console.log(`render: wrote ${path.relative(process.cwd(), out)}`);
      return;
    }

    const first = Math.round(rangeStart * fps);
    const last = Math.round(rangeEnd * fps);
    const total = last - first;
    if (total <= 0) fail('nothing to render (check --from/--to)');

    const audio = opts.noAudio ? { inputs: [], graph: null } : audioFor(1);
    const ffArgs = [
      '-y', '-v', 'error',
      '-f', 'image2pipe', '-framerate', String(fps), '-i', '-',
      ...audio.inputs,
      ...(audio.graph ? ['-filter_complex', audio.graph, '-map', '0:v', '-map', '[aout]'] : ['-map', '0:v']),
      ...encoderArgs(out, opts.transparent, opts.crf, opts.preset),
      ...(audio.graph ? [] : ['-an']),
      '-r', String(fps), '-t', String(total / fps),
      out,
    ];
    const ff = spawn('ffmpeg', ffArgs, { stdio: ['pipe', 'inherit', 'inherit'] });
    const done = once(ff, 'exit');

    console.log(`render: ${width}×${height}${scale !== 1 ? ` @${scale}x` : ''}, ${fps} fps, ${total} frames → ${path.relative(process.cwd(), out)}`);
    const t0 = Date.now();
    let lastPct = -1;
    for (let f = first; f < last; f++) {
      await page.evaluate((t) => window.Studio._seek(t), f / fps);
      const buf = await shoot();
      if (!ff.stdin.write(buf)) await once(ff.stdin, 'drain');
      const pct = Math.floor(((f - first + 1) / total) * 10) * 10;
      if (pct !== lastPct) {
        lastPct = pct;
        const secs = (Date.now() - t0) / 1000;
        console.log(`render: ${String(pct).padStart(3)}%  (${f - first + 1}/${total} frames, ${secs.toFixed(1)}s)`);
      }
    }
    ff.stdin.end();
    const [code] = await done;
    if (code !== 0) fail(`ffmpeg exited with code ${code}`);
    const secs = (Date.now() - t0) / 1000;
    console.log(`render: done in ${secs.toFixed(1)}s (${(secs / total).toFixed(3)} s/frame) → ${path.relative(process.cwd(), out)}`);
  } finally {
    await browser.close();
    server.close();
  }
}

main().catch((e) => fail(e.stack || e.message));
