#!/usr/bin/env node
/*
 * render-parallel.mjs — render a composition as time chunks in parallel, then
 * join them into one file with a single, continuous audio track.
 *
 *   node render-parallel.mjs projects/reze2/index.html -o out/rz-02.mp4
 *
 * Each chunk is a render.mjs child process drawing an exact frame range to a
 * video-only intermediate (x264 CRF 12). The audio is mixed once for the whole
 * range (render.mjs --audio-only), so chunk joins can never click. The chunks
 * are then encoded (HEVC by default) and joined with the concat demuxer.
 *
 * Resumable: finished chunks are kept in out/.parallel/<name>/ and reused, so
 * a long render can be spread over several runs that each stop within
 * --budget seconds (exit code 75 = not finished yet, run the same command
 * again). Editing any file the page loads (or render.mjs) starts over.
 *
 * Options:
 *   -o, --out FILE      output .mp4. Default: out/<name>.mp4
 *   --jobs N            chunks rendered at once (default 3)
 *   --chunk S           chunk length in seconds (default 1; shrunk if chunks run slow)
 *   --codec C           final codec: hevc (default, CRF 24) or h264 (CRF 20)
 *   --crf N, --preset P final encode quality / speed (default preset medium)
 *   --budget S          stop starting work after S seconds and exit 75 (default 280; 0 = no limit)
 *   --timeout S         kill a chunk after S seconds, split it in half and retry once (default 300)
 *   --fresh             throw away finished chunks and start over
 *   --keep              keep the chunks after a successful render
 *   --fps, --duration, --from, --to, --scale   as for render.mjs
 */
import { spawn, spawnSync } from 'node:child_process';
import crypto from 'node:crypto';
import { once } from 'node:events';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const RENDER = path.join(ROOT, 'render.mjs');
const CHUNK_TIMEOUT = 300; // seconds; a chunk running longer is killed, split in half and retried once
const CHUNK_ENCODE = ['--crf', '12', '--preset', 'veryfast', '--no-audio'];
const ENCODE_SPF = { hevc: 0.04, h264: 0.015 }; // final-encode seconds per frame at 1080p on 4 cores, until measured
const T0 = Date.now();

function parseArgs(argv) {
  const opts = { jobs: 3, chunk: 1, codec: 'hevc', preset: 'medium', budget: 280, pass: [], range: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = () => argv[++i];
    if (a === '-o' || a === '--out') opts.out = next();
    else if (a === '--jobs') opts.jobs = Math.max(1, +next());
    else if (a === '--chunk') opts.chunk = +next();
    else if (a === '--codec') opts.codec = next();
    else if (a === '--crf') opts.crf = next();
    else if (a === '--preset') opts.preset = next();
    else if (a === '--budget') opts.budget = +next();
    else if (a === '--timeout') opts.timeout = +next();
    else if (a === '--fresh') opts.fresh = true;
    else if (a === '--keep') opts.keep = true;
    else if (['--fps', '--duration', '--scale'].includes(a)) opts.pass.push(a, next());
    else if (a === '--from' || a === '--to') opts.range.push(a, next());
    else if (a === '-h' || a === '--help') opts.help = true;
    else if (!opts.input) opts.input = a;
    else throw new Error(`Unexpected argument: ${a}`);
  }
  if (!['hevc', 'h264'].includes(opts.codec)) throw new Error(`--codec must be hevc or h264, not ${opts.codec}`);
  return opts;
}

const log = (msg) => console.log(`parallel: ${msg}`);
const elapsed = () => (Date.now() - T0) / 1000;
const pad = (n) => String(n).padStart(6, '0');

function fail(msg) {
  console.error(`parallel: ${msg}`);
  killAll();
  process.exit(1);
}

/** Frames in a video file, by counting packets (no decoding). */
function frameCount(file) {
  const r = spawnSync('ffprobe', ['-v', 'error', '-select_streams', 'v:0', '-count_packets', '-show_entries', 'stream=nb_read_packets',
    '-of', 'csv=p=0', file], { encoding: 'utf8' });
  return r.status === 0 ? parseInt(r.stdout, 10) : -1;
}

function ffmpeg(args) {
  const r = spawnSync('ffmpeg', ['-y', '-v', 'error', ...args], { encoding: 'utf8', timeout: CHUNK_TIMEOUT * 1000 });
  if (r.status !== 0) fail(`ffmpeg failed: ${r.stderr || r.error?.message || `status ${r.status}`}`);
}

/**
 * A hash of everything that decides what the frames look like: the options,
 * render.mjs, and every file the page loaded (render.mjs --info lists them) —
 * so edits elsewhere, e.g. to another page in lib/, don't restart a render.
 * Big files count by size and date; footage isn't loaded by the page, so use
 * --fresh after replacing it.
 */
function fingerprint(opts, files) {
  const hash = crypto.createHash('sha1').update(JSON.stringify([opts.pass, opts.range, CHUNK_ENCODE]));
  for (const f of ['render.mjs', ...files]) {
    const p = path.join(ROOT, f);
    const st = fs.existsSync(p) ? fs.statSync(p) : null;
    hash.update(f).update(!st ? 'missing' : st.size > 2e6 ? `${st.size}:${st.mtimeMs}` : fs.readFileSync(p));
  }
  return hash.digest('hex').slice(0, 16);
}

// ---- child processes --------------------------------------------------------------

const children = new Set();

/** Run render.mjs with args; output goes to logFile. Each child leads its own process group. */
function renderChild(args, logFile) {
  const fd = fs.openSync(logFile, 'w');
  const child = spawn(process.execPath, [RENDER, ...args], { cwd: ROOT, detached: true, stdio: ['ignore', fd, fd] });
  fs.closeSync(fd);
  children.add(child);
  const done = once(child, 'exit').then(([code, signal]) => { children.delete(child); return { code, signal }; });
  return { child, done };
}

/** Kill a child with its Chromium and ffmpeg. */
function kill(child) {
  try { process.kill(-child.pid, 'SIGKILL'); } catch { /* already gone */ }
}

function killAll() { for (const c of children) kill(c); }
process.on('exit', killAll);
process.on('SIGINT', () => { killAll(); process.exit(130); });
process.on('SIGTERM', () => { killAll(); process.exit(143); });

const tail = (file, n = 8) => (fs.existsSync(file) ? fs.readFileSync(file, 'utf8').trim().split('\n').slice(-n).join('\n') : '');

// ---- planning -----------------------------------------------------------------------

/** Finished chunks in the work dir, as sorted [a, b, file]. */
function finishedChunks(work) {
  return fs.readdirSync(work).map((f) => f.match(/^c-(\d+)-(\d+)\.mp4$/)).filter(Boolean)
    .map((m) => [+m[1], +m[2], path.join(work, m[0])]).sort((x, y) => x[0] - y[0]);
}

/** Frame ranges of [first, last) not covered by finished chunks, cut into pieces of at most size frames. */
function pendingRanges(first, last, done, size) {
  const out = [];
  let at = first;
  const cut = (a, b) => { for (let x = a; x < b; x += size) out.push([x, Math.min(b, x + size)]); };
  for (const [a, b] of done) {
    if (a > at) cut(at, Math.min(a, last));
    at = Math.max(at, b);
  }
  if (at < last) cut(at, last);
  return out;
}

// ---- main ---------------------------------------------------------------------------

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (opts.help || !opts.input) {
    console.log(fs.readFileSync(fileURLToPath(import.meta.url), 'utf8').split('*/')[0].replace(/^[\s\S]*?\/\*\n/, '').replace(/^ \* ?/gm, ''));
    process.exit(opts.help ? 0 : 1);
  }
  const input = path.resolve(opts.input);
  if (!fs.existsSync(input)) fail(`not found: ${opts.input}`);
  const name = path.basename(input) === 'index.html' ? path.basename(path.dirname(input)) : path.basename(input, '.html');
  const out = path.resolve(opts.out || path.join(ROOT, 'out', `${name}.mp4`));
  const work = path.join(ROOT, 'out', '.parallel', path.basename(out, path.extname(out)));
  const budget = opts.budget > 0 ? opts.budget : Infinity;
  const left = () => budget - elapsed();

  // Start over when the composition or the options changed since the chunks were made.
  const infoFile = path.join(work, 'info.json');
  const audioFile = path.join(work, 'audio.m4a');
  const sigFile = path.join(work, 'signature');
  const read = (f) => (fs.existsSync(f) ? fs.readFileSync(f, 'utf8') : null);
  const previous = read(infoFile) && read(sigFile);
  if (opts.fresh || (previous && previous !== fingerprint(opts, JSON.parse(read(infoFile)).files || []))) {
    if (fs.existsSync(work)) log(opts.fresh ? 'starting fresh' : 'composition changed since the last run — starting over');
    fs.rmSync(work, { recursive: true, force: true });
  }
  fs.mkdirSync(work, { recursive: true });
  const statsFile = path.join(work, 'stats.json');
  const stats = fs.existsSync(statsFile) ? JSON.parse(fs.readFileSync(statsFile, 'utf8')) : {};
  const saveStats = () => fs.writeFileSync(statsFile, JSON.stringify(stats));

  // 1. Read the config, extract the footage into the shared cache and mix the audio — once.
  if (!fs.existsSync(infoFile) || !fs.existsSync(sigFile)) {
    const t = Date.now();
    const prep = renderChild([input, '--info', infoFile, '--prepare', '--audio-only', audioFile, ...opts.pass, ...opts.range],
      path.join(work, 'prepare.log'));
    const timer = setTimeout(() => kill(prep.child), CHUNK_TIMEOUT * 1000);
    const { code } = await prep.done;
    clearTimeout(timer);
    if (code !== 0 || !fs.existsSync(infoFile)) {
      fs.rmSync(infoFile, { force: true });
      fail(`preparing failed:\n${tail(path.join(work, 'prepare.log'))}`);
    }
    fs.writeFileSync(sigFile, fingerprint(opts, JSON.parse(read(infoFile)).files || []));
    log(`prepared config, footage and audio in ${((Date.now() - t) / 1000).toFixed(1)}s`);
  }
  const info = JSON.parse(fs.readFileSync(infoFile, 'utf8'));
  const { fps } = info;
  const rangeOpt = (k) => { const i = opts.range.indexOf(k); return i >= 0 ? +opts.range[i + 1] : undefined; };
  const first = Math.round(Math.max(0, rangeOpt('--from') ?? 0) * fps);
  const last = Math.round(Math.min(info.duration, rangeOpt('--to') ?? info.duration) * fps);
  const total = last - first;
  if (total <= 0) fail('nothing to render (check --from/--to)');

  // 2. Chunks. Their size shrinks when earlier chunks showed they would run close to the timeout.
  const timeout = opts.timeout > 0 ? opts.timeout : CHUNK_TIMEOUT;
  const limit = Math.min(timeout, budget);
  const startup = () => stats.startup ?? 10; // seconds a chunk spends before its first frame
  let size = Math.max(1, Math.round(opts.chunk * fps));
  if (stats.spf) size = Math.max(1, Math.min(size, Math.floor((0.6 * limit - startup()) / stats.spf)));
  const pending = pendingRanges(first, last, finishedChunks(work), size).map(([a, b]) => ({ a, b, tries: 0 }));
  const doneFrames = () => finishedChunks(work).reduce((n, [a, b]) => n + Math.max(0, Math.min(b, last) - Math.max(a, first)), 0);
  log(`${name} — ${info.width}×${info.height}, ${fps} fps, frames ${first}–${last} (${(total / fps).toFixed(2)}s); ` +
    `${pending.length} chunks to render (${total - doneFrames()} frames), ${opts.jobs} at a time` +
    (isFinite(budget) ? `, budget ${budget}s` : ''));

  let outOfTime = false;
  const running = new Set();
  const renderStart = Date.now();
  let rendered = 0;
  const estimate = (r) => startup() + (r.b - r.a) * (stats.spf ?? 0);
  const fits = (r) => (stats.spf ? estimate(r) <= left() : elapsed() < 0.5 * budget);
  const ema = (old, v) => (old == null ? v : 0.7 * old + 0.3 * v);

  function start(r) {
    const file = path.join(work, `c-${pad(r.a)}-${pad(r.b)}.mp4`);
    const part = file.replace(/\.mp4$/, '.part.mp4');
    const logFile = file.replace(/\.mp4$/, '.log');
    const job = renderChild([input, '--from', String(r.a / fps), '--to', String(r.b / fps), ...CHUNK_ENCODE, ...opts.pass, '-o', part], logFile);
    const started = Date.now();
    let timedOut = false;
    const timer = setTimeout(() => { timedOut = true; kill(job.child); }, timeout * 1000);
    const task = { r, child: job.child, started };
    task.done = job.done.then(({ code }) => {
      clearTimeout(timer);
      running.delete(task);
      const secs = (Date.now() - started) / 1000;
      const frames = r.b - r.a;
      if (code === 0 && frameCount(part) === frames) {
        fs.renameSync(part, file);
        // render.mjs reports its frame loop ("done in 19.6s (0.163 s/frame)"); the rest is startup.
        const m = fs.readFileSync(logFile, 'utf8').match(/done in ([\d.]+)s \(([\d.]+) s\/frame\)/);
        fs.rmSync(logFile, { force: true });
        const loop = m ? +m[1] : secs;
        stats.spf = ema(stats.spf, loop / frames);
        stats.startup = ema(stats.startup, Math.max(0, secs - loop));
        saveStats();
        rendered += frames;
        log(`chunk ${r.a}–${r.b} done in ${secs.toFixed(1)}s (${(loop / frames).toFixed(3)} s/frame + ${(secs - loop).toFixed(1)}s startup)` +
          ` — ${doneFrames()}/${total} frames`);
        return;
      }
      fs.rmSync(part, { force: true });
      if (outOfTime && !timedOut) {
        // Stopped for the budget, not broken; learn how slow it was so the next run plans smaller chunks.
        stats.spf = Math.max(stats.spf || 0, (secs - startup()) / frames);
        saveStats();
        return;
      }
      const why = timedOut ? `timed out after ${timeout}s` : `failed (exit ${code})`;
      if (r.tries >= 1 || frames < 2) fail(`chunk ${r.a}–${r.b} ${why} again:\n${tail(logFile)}`);
      const m = Math.floor((r.a + r.b) / 2);
      log(`chunk ${r.a}–${r.b} ${why} — splitting into ${r.a}–${m} and ${m}–${r.b}`);
      if (timedOut) { stats.spf = Math.max(stats.spf || 0, timeout / frames); saveStats(); }
      pending.unshift({ a: r.a, b: m, tries: r.tries + 1 }, { a: m, b: r.b, tries: r.tries + 1 });
    });
    running.add(task);
  }

  const budgetTimer = isFinite(budget) ? setTimeout(() => { outOfTime = true; for (const t of running) kill(t.child); }, Math.max(0, left()) * 1000) : null;
  while (pending.length || running.size) {
    while (!outOfTime && running.size < opts.jobs && pending.length && fits(pending[0])) start(pending.shift());
    if (!running.size) break;
    await Promise.race([...running].map((t) => t.done));
  }
  clearTimeout(budgetTimer);
  if (rendered) {
    const wall = (Date.now() - renderStart) / 1000;
    log(`rendered ${rendered} frames in ${wall.toFixed(1)}s — ${(wall / rendered).toFixed(3)} s/frame overall with ${opts.jobs} jobs`);
  }
  if (pending.length || (outOfTime && doneFrames() < total)) {
    log(`budget reached — ${doneFrames()}/${total} frames done. Run the same command again to continue.`);
    process.exit(75);
  }

  // 3. Encode. Consecutive chunks are grouped into segments small enough to encode
  //    within the budget; each segment reads its chunks through the concat demuxer.
  const chunks = finishedChunks(work).filter(([a, b]) => a >= first && b <= last);
  if (chunks[0]?.[0] !== first || chunks.some(([, b], i) => i + 1 < chunks.length && chunks[i + 1][0] !== b) || chunks.at(-1)[1] !== last) {
    fail('finished chunks do not tile the frame range — run with --fresh');
  }
  const crf = opts.crf ?? (opts.codec === 'hevc' ? '24' : '20');
  const codecArgs = opts.codec === 'hevc'
    ? ['-c:v', 'libx265', '-preset', opts.preset, '-crf', crf, '-tag:v', 'hvc1', '-pix_fmt', 'yuv420p', '-x265-params', 'log-level=error']
    : ['-c:v', 'libx264', '-preset', opts.preset, '-crf', crf, '-pix_fmt', 'yuv420p'];
  const encKey = crypto.createHash('sha1').update(JSON.stringify(codecArgs)).digest('hex').slice(0, 8);
  const encSpf = stats.encSpf?.[encKey] ?? ENCODE_SPF[opts.codec];
  const maxSeg = Math.max(1, Math.floor((0.7 * limit) / encSpf));
  const segments = [];
  for (const c of chunks) {
    const seg = segments.at(-1);
    if (seg && c[1] - seg[0][0] <= maxSeg) seg.push(c); else segments.push([c]);
  }
  const segFiles = [];
  for (const seg of segments) {
    const a = seg[0][0], b = seg.at(-1)[1];
    const file = path.join(work, `e-${encKey}-${pad(a)}-${pad(b)}.mp4`);
    segFiles.push(file);
    if (fs.existsSync(file)) continue;
    if ((b - a) * encSpf > left()) {
      log(`budget reached before encoding ${a}–${b} (~${Math.ceil((b - a) * encSpf)}s). Run the same command again to continue.`);
      process.exit(75);
    }
    const list = path.join(work, `e-${pad(a)}.txt`);
    fs.writeFileSync(list, seg.map(([, , f]) => `file '${path.basename(f)}'`).join('\n') + '\n');
    const t = Date.now();
    const part = file.replace(/\.mp4$/, '.part.mp4');
    ffmpeg(['-f', 'concat', '-safe', '0', '-i', list, '-map', '0:v:0', ...codecArgs, '-an', '-movflags', '+faststart', part]);
    if (frameCount(part) !== b - a) fail(`encoded segment ${a}–${b} has ${frameCount(part)} frames, expected ${b - a}`);
    fs.renameSync(part, file);
    const secs = (Date.now() - t) / 1000;
    stats.encSpf = { ...stats.encSpf, [encKey]: secs / (b - a) };
    saveStats();
    log(`encoded ${opts.codec} ${a}–${b} in ${secs.toFixed(1)}s`);
  }

  // 4. Join the segments (stream copy) and add the one audio track.
  const list = path.join(work, 'segments.txt');
  fs.writeFileSync(list, segFiles.map((f) => `file '${path.basename(f)}'`).join('\n') + '\n');
  const audio = fs.existsSync(audioFile);
  fs.mkdirSync(path.dirname(out), { recursive: true });
  ffmpeg(['-f', 'concat', '-safe', '0', '-i', list, ...(audio ? ['-i', audioFile] : []),
    '-map', '0:v:0', ...(audio ? ['-map', '1:a:0'] : []), '-c', 'copy',
    ...(opts.codec === 'hevc' ? ['-tag:v', 'hvc1'] : []), '-movflags', '+faststart', out]);
  const frames = frameCount(out);
  if (frames !== total) fail(`${path.relative(process.cwd(), out)} has ${frames} frames, expected ${total}`);

  const mb = fs.statSync(out).size / 1e6;
  log(`wrote ${path.relative(process.cwd(), out)} — ${frames} frames (${(frames / fps).toFixed(3)}s at ${fps} fps), ` +
    `${opts.codec}${audio ? ' + aac 256k' : ', no audio'}, ${mb.toFixed(1)} MB, ${elapsed().toFixed(1)}s this run`);
  if (!opts.keep) fs.rmSync(work, { recursive: true, force: true });
}

main().catch((e) => fail(e.stack || e.message));
