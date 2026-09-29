// Render frame-per-frame dengan Playwright (Chromium tanpa WebGL: hanya CSS/Canvas2D).
// Pemakaian: node src/render.mjs [--workers 4] [--from 0] [--to N] [--still T out.png]
import { chromium } from 'playwright';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const flag = (n, d) => { const i = args.indexOf('--' + n); return i < 0 ? d : args[i + 1]; };
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg', '.woff2': 'font/woff2' };

const server = http.createServer((req, res) => {
  const u = decodeURIComponent(req.url.split('?')[0]);
  const file = path.join(ROOT, u === '/' ? 'src/scene.html' : u);
  if (!file.startsWith(ROOT)) { res.writeHead(403); return res.end(); }
  fs.readFile(file, (e, d) => { if (e) { res.writeHead(404); res.end(); } else { res.writeHead(200, { 'content-type': MIME[path.extname(file)] || 'application/octet-stream', 'cache-control': 'max-age=3600' }); res.end(d); } });
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const origin = `http://127.0.0.1:${server.address().port}`;

const tl = JSON.parse(fs.readFileSync(path.join(ROOT, 'work/timeline.json'), 'utf8'));
const fps = tl.fps, total = tl.total, nFrames = Math.round(total * fps);

const browser = await chromium.launch({ args: ['--disable-gpu', '--disable-webgl', '--font-render-hinting=none', '--force-color-profile=srgb'] });
async function open() {
  const ctx = await browser.newContext({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  page.on('pageerror', e => console.error('page error:', e.message));
  page.on('console', m => { if (m.type() === 'error') console.error('console:', m.text()); });
  await page.goto(origin + '/src/scene.html');
  await page.waitForFunction(() => typeof window.setup === 'function');
  await page.evaluate(() => window.setup());
  return page;
}

const still = flag('still');
if (still !== undefined) {
  const out = args[args.indexOf('--still') + 2];
  const page = await open();
  await page.evaluate(t => window.frame(t), Number(still));
  await page.screenshot({ path: out, type: out.endsWith('.png') ? 'png' : 'jpeg', ...(out.endsWith('.png') ? {} : { quality: 92 }) });
  console.log('still ->', out); await browser.close(); server.close(); process.exit(0);
}

const workers = Number(flag('workers', 4)), from = Number(flag('from', 0)), to = Math.min(Number(flag('to', nFrames)), nFrames);
const outDir = path.join(ROOT, 'work/out'); fs.mkdirSync(outDir, { recursive: true });
let done = 0; const t0 = Date.now();
async function worker(w) {
  const page = await open();
  for (let i = from + w; i < to; i += workers) {
    await page.evaluate(t => window.frame(t), i / fps);
    await page.screenshot({ path: path.join(outDir, String(i + 1).padStart(6, '0') + '.jpg'), type: 'jpeg', quality: 93 });
    if (++done % 100 === 0) { const el = (Date.now() - t0) / 1000; console.log(`${done}/${to - from}  ${(done / el).toFixed(1)} fps  eta ${(((to - from) - done) / (done / el) / 60).toFixed(1)} mnt`); }
  }
  await page.context().close();
}
await Promise.all(Array.from({ length: workers }, (_, w) => worker(w)));
console.log(`selesai ${to - from} frame dalam ${((Date.now() - t0) / 60000).toFixed(1)} menit`);
await browser.close(); server.close();
