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
 *   --transparent       keep the background transparent (.mov → ProRes 4444, .webm → VP9 alpha)
 *   --still S           save a single PNG of time S instead of a video
 */
import { chromium } from 'playwright';
import { spawn, spawnSync } from 'node:child_process';
import { once } from 'node:events';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));

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
    else if (a === '--still') opts.still = +next();
    else if (a === '--transparent') opts.transparent = true;
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

function hasAudio(src) {
  const r = spawnSync('ffprobe', ['-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=index', '-of', 'csv=p=0', src], { encoding: 'utf8' });
  return r.status === 0 && r.stdout.trim() !== '';
}

function serve(footageDir) {
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, 'http://x');
    let file;
    if (url.pathname.startsWith('/__footage/')) {
      file = path.join(footageDir, decodeURIComponent(url.pathname.slice('/__footage/'.length)));
    } else {
      file = path.join(ROOT, decodeURIComponent(url.pathname));
    }
    if (!file.startsWith(ROOT) && !file.startsWith(footageDir)) {
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

function encoderArgs(out, transparent, crf) {
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
  return ['-c:v', 'libx264', '-preset', 'medium', '-crf', crf ?? '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart'];
}

/** Build ffmpeg inputs and an amix filter for every audio entry in the config. */
function audioArgs(config, footage, pageUrl, origin, rangeStart, rangeEnd) {
  const inputs = [];
  const filters = [];
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
    if (!hasAudio(src)) {
      console.warn(`render: no audio stream in ${a.src}, skipping`);
      continue;
    }
    // Shift everything so the rendered range starts at 0.
    const start = a.start - rangeStart;
    const from = a.from + Math.max(0, -start);
    const delay = Math.max(0, start);
    const len = rangeEnd - rangeStart - delay;
    if (len <= 0) continue;
    const idx = inputs.length / 4 + 1;
    inputs.push('-ss', String(from), '-i', src);
    const chain = [`atrim=0:${len}`, 'asetpts=PTS-STARTPTS', `volume=${a.volume ?? 1}`];
    if (a.fadeIn) chain.push(`afade=t=in:st=0:d=${a.fadeIn}`);
    if (a.fadeOut) chain.push(`afade=t=out:st=${Math.max(0, len - a.fadeOut)}:d=${a.fadeOut}`);
    chain.push(`adelay=${Math.round(delay * 1000)}:all=1`);
    filters.push(`[${idx}:a]${chain.join(',')}[a${idx}]`);
  }
  if (!filters.length) return { inputs: [], map: [] };
  const labels = filters.map((_, i) => `[a${i + 1}]`).join('');
  const graph = `${filters.join(';')};${labels}amix=inputs=${filters.length}:normalize=0:duration=longest[aout]`;
  return { inputs, map: ['-filter_complex', graph, '-map', '0:v', '-map', '[aout]'] };
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
  fs.mkdirSync(path.dirname(out), { recursive: true });

  const footageDir = fs.mkdtempSync(path.join(os.tmpdir(), 'studio-footage-'));
  const server = await serve(footageDir);
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
    const probe = await open({});
    const config = await probe.evaluate(() => window.Studio.config);
    await probe.context().close();

    const fps = opts.fps || config.fps;
    const duration = opts.duration || config.duration;
    const { width, height } = config;
    const scale = opts.scale || 1;
    const page = await open({ viewport: { width, height }, deviceScaleFactor: scale });
    await page.evaluate((f) => { window.Studio.config.fps = f; }, fps);

    // Extract footage frames once, at the composition's frame rate.
    const footage = Object.fromEntries(Object.entries(config.footage || {}).map(([k, v]) => [k, normalizeFootage(v)]));
    const counts = {};
    for (const [key, f] of Object.entries(footage)) {
      const dir = path.join(footageDir, key);
      fs.mkdirSync(dir, { recursive: true });
      const src = resolveMedia(f.src, pageUrl, origin);
      if (!/^https?:/.test(src) && !fs.existsSync(src)) fail(`footage "${key}" not found: ${f.src}`);
      process.stdout.write(`render: extracting footage "${key}"… `);
      run('ffmpeg', ['-v', 'error', '-ss', String(f.from), '-i', src, '-t', String(Math.max(0.1, duration - f.start + 1)),
        '-vf', `fps=${fps},scale=w='min(iw,${Math.round(width * scale)})':h='min(ih,${Math.round(height * scale)})':force_original_aspect_ratio=decrease`,
        '-q:v', '2', path.join(dir, '%06d.jpg')]);
      counts[key] = fs.readdirSync(dir).length;
      console.log(`${counts[key]} frames`);
    }
    await page.evaluate((c) => window.Studio._setFootageFrames(c), counts);
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

    const rangeStart = Math.max(0, opts.from || 0);
    const rangeEnd = Math.min(duration, opts.to ?? duration);
    const first = Math.round(rangeStart * fps);
    const last = Math.round(rangeEnd * fps);
    const total = last - first;
    if (total <= 0) fail('nothing to render (check --from/--to)');

    const audio = audioArgs(config, footage, pageUrl, origin, rangeStart, rangeEnd);
    const ffArgs = [
      '-y', '-v', 'error',
      '-f', 'image2pipe', '-framerate', String(fps), '-i', '-',
      ...audio.inputs,
      ...audio.map,
      ...encoderArgs(out, opts.transparent, opts.crf),
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
    console.log(`render: done in ${((Date.now() - t0) / 1000).toFixed(1)}s → ${path.relative(process.cwd(), out)}`);
  } finally {
    await browser.close();
    server.close();
    fs.rmSync(footageDir, { recursive: true, force: true });
  }
}

main().catch((e) => fail(e.stack || e.message));
