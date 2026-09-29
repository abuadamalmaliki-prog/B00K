#!/usr/bin/env node
// Usage: node render.mjs <project.json> <out.mp4> [--from S] [--to S] [--still T] [--scale N] [--crf N]
// Renders scene.html (Three.js + HTML/CSS) frame by frame with Playwright and pipes JPEGs into ffmpeg.
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const flag = (n, d) => { const i = args.indexOf('--' + n); return i < 0 ? d : args[i + 1]; };
const [projectFile, outFile] = args.filter((a, i) => !a.startsWith('--') && !args[i - 1]?.startsWith('--'));
if (!projectFile || !outFile) { console.error('usage: node render.mjs project.json out.mp4 [--from S] [--to S] [--still T] [--scale N] [--crf N]'); process.exit(1); }

const projPath = path.resolve(projectFile), projDir = path.dirname(projPath);
const project = JSON.parse(fs.readFileSync(projPath, 'utf8'));
const fps = project.fps ?? 30;
const outW = Number(flag('width', project.width ?? 1696));                 // design space is 848x464; DSF does the scaling
const dsf = outW / 848, outH = Math.round(464 * dsf / 2) * 2;
const ffmpegBin = process.env.FFMPEG || 'ffmpeg';

const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.svg': 'image/svg+xml', '.ttf': 'font/ttf', '.otf': 'font/otf', '.woff2': 'font/woff2' };
const server = http.createServer((req, res) => {
  const u = decodeURIComponent(req.url.split('?')[0]);
  const file = u.startsWith('/project/') ? path.join(projDir, u.slice(9)) : path.join(here, u === '/' ? 'scene.html' : u);
  fs.readFile(file, (e, d) => { if (e) { res.writeHead(404); res.end(); } else { res.writeHead(200, { 'content-type': MIME[path.extname(file)] || 'application/octet-stream' }); res.end(d); } });
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const origin = `http://127.0.0.1:${server.address().port}`;

const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--enable-webgl', '--font-render-hinting=none'] });
const page = await (await browser.newContext({ viewport: { width: 848, height: 464 }, deviceScaleFactor: dsf })).newPage();
page.on('pageerror', e => console.error('page error:', e.message));
page.on('console', m => { if (m.type() === 'error') console.error('console:', m.text()); });
await page.goto(origin + '/scene.html');
await page.waitForFunction(() => typeof window.setup === 'function');
const { duration } = await page.evaluate(([p, base]) => window.setup(p, base), [project, '/project/']);

const from = Number(flag('from', 0)), to = Math.min(Number(flag('to', duration)), duration);
const shot = () => page.screenshot({ type: 'jpeg', quality: 95 });

if (flag('still') !== undefined) {
  await page.evaluate(t => window.frame(t), Number(flag('still')));
  fs.mkdirSync(path.dirname(path.resolve(outFile)), { recursive: true });
  fs.writeFileSync(outFile, await page.screenshot(outFile.endsWith('.png') ? { type: 'png' } : { type: 'jpeg', quality: 95 }));
  console.log('still ->', outFile); await browser.close(); server.close(); process.exit(0);
}

fs.mkdirSync(path.dirname(path.resolve(outFile)), { recursive: true });
const ff = ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-'];
if (project.audio) ff.push('-ss', String(from), '-t', String(to - from), '-i', path.resolve(projDir, project.audio));
ff.push('-map', '0:v', ...(project.audio ? ['-map', '1:a?', '-c:a', 'aac', '-b:a', '160k'] : []),
  '-c:v', 'libx264', '-preset', flag('preset', 'medium'), '-crf', flag('crf', '18'), '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-shortest', outFile);
const enc = spawn(ffmpegBin, ff, { stdio: ['pipe', 'inherit', 'inherit'] });
const done = new Promise(r => enc.on('close', r));

const total = Math.round((to - from) * fps), t0 = Date.now();
for (let i = 0; i < total; i++) {
  await page.evaluate(t => window.frame(t), from + i / fps);
  if (!enc.stdin.write(await shot())) await new Promise(r => enc.stdin.once('drain', r));
  if (i % 30 === 0) process.stdout.write(`\rframe ${i}/${total}  ${((Date.now() - t0) / 1000 / (i + 1)).toFixed(2)}s/frame `);
}
enc.stdin.end(); const code = await done;
console.log(`\n${outFile}  ${outW}x${outH} @${fps}fps  ${(to - from).toFixed(1)}s  (ffmpeg exit ${code})`);
await browser.close(); server.close();
process.exit(code);
