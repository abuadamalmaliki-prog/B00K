/*
 * studio.js — turns an HTML page into a frame-accurate video composition.
 *
 * Put everything visible inside <div id="stage">, call Studio.setup({...})
 * and drive motion from Studio.onFrame((t) => ...). CSS animations and
 * Web Animations are scrubbed automatically, so they need no extra code.
 *
 * Opened normally in a browser the page plays as a preview with a scrub bar.
 * Opened by render.mjs (with ?render in the URL) nothing moves on its own:
 * the renderer seeks to each frame's time and screenshots it.
 */
(() => {
  const params = new URLSearchParams(location.search);
  const rendering = params.has('render');
  const transparent = params.has('transparent');

  let config = { width: 1920, height: 1080, fps: 30, duration: 5, footage: {}, audio: [] };
  const handlers = [];
  const waits = [];
  const footage = {}; // name -> { el, src, start, from, duration, manual }
  let footageInfo = {}; // name -> { count, fps } of the extracted frames, filled in by render.mjs

  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

  const Studio = {
    rendering,
    time: 0,
    frame: 0,
    get config() { return config; },

    /** Declare size, fps, duration, footage and audio for this composition. */
    setup(opts) {
      config = { ...config, ...opts };
      for (const [name, spec] of Object.entries(config.footage || {})) {
        const { src, start = 0, from = 0, duration, manual = false } = typeof spec === 'string' ? { src: spec } : spec;
        let el;
        if (rendering) {
          el = new Image();
        } else {
          el = document.createElement('video');
          Object.assign(el, { src, muted: true, playsInline: true, preload: 'auto' });
          waits.push(new Promise((r) => el.addEventListener('loadeddata', r, { once: true })));
        }
        footage[name] = { el, src, start, from, duration, manual };
      }
      layout();
      return Studio;
    },

    /** Run fn(t) on every frame. May be async (return a promise). */
    onFrame(fn) { handlers.push(fn); return Studio; },

    /** Hold rendering until this promise settles (textures, models, data). */
    wait(promise) { waits.push(promise); return promise; },

    /** Drawable element (<img> when rendering, <video> in preview) for a footage clip. */
    footage(name) { return entry(name).el; },

    /**
     * Put a footage element on the frame at `seconds` of its source file
     * (absolute source time, clamped into the declared from…from+duration).
     * Meant for entries declared with `manual: true`, which the timeline never
     * moves by itself. Resolves to the element once that frame is decoded.
     */
    async footageAt(name, seconds) {
      const f = entry(name);
      await showFrame(name, f, seconds - f.from, true);
      return f.el;
    },

    /** 0→1 as t goes from start to end, clamped. */
    progress(t, start, end) { return clamp((t - start) / (end - start), 0, 1); },

    ease: {
      linear: (x) => x,
      in: (x) => x * x * x,
      out: (x) => 1 - Math.pow(1 - x, 3),
      inOut: (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2),
      outBack: (x) => 1 + 2.70158 * Math.pow(x - 1, 3) + 1.70158 * Math.pow(x - 1, 2),
    },

    lerp: (a, b, x) => a + (b - a) * x,

    /** Seeded random generator, so every render is identical. */
    random(seed = 1) {
      return () => {
        seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
        let x = Math.imul(seed ^ (seed >>> 15), 1 | seed);
        x = (x + Math.imul(x ^ (x >>> 7), 61 | x)) ^ x;
        return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
      };
    },

    // ---- used by render.mjs -------------------------------------------------
    async _whenReady() {
      await Promise.all(waits);
      await document.fonts.ready;
    },
    _setFootage(info) { footageInfo = info; },
    async _seek(t) { await seek(t); await nextPaint(); },
  };

  function entry(name) {
    if (!footage[name]) throw new Error(`Unknown footage "${name}" — declare it in Studio.setup({ footage })`);
    return footage[name];
  }

  // Show the frame `rel` seconds after the clip's in-point (`from`).
  async function showFrame(name, f, rel, exact) {
    if (rendering) {
      // render.mjs extracts frames from `from` at the source's own rate (capped at
      // the composition's), so index by source time at that rate.
      const { count = 1, fps = config.fps } = footageInfo[name] || {};
      const index = clamp(Math.floor(rel * fps + 1e-4), 0, count - 1) + 1;
      const url = `/__footage/${encodeURIComponent(name)}/${String(index).padStart(6, '0')}.jpg`;
      if (f.el.getAttribute('src') !== url) {
        f.el.src = url;
        // A newer footageAt() on the same element cancels this decode; that's fine.
        try { await f.el.decode(); } catch (e) { if (f.el.getAttribute('src') === url) throw e; }
      }
    } else if (exact) {
      const end = Math.min(f.from + (f.duration ?? Infinity), (f.el.duration || Infinity) - 0.01);
      const time = clamp(f.from + rel, f.from, end);
      if (Math.abs(f.el.currentTime - time) > 0.02) {
        f.el.currentTime = time;
        await new Promise((r) => { f.el.addEventListener('seeked', r, { once: true }); setTimeout(r, 400); });
      }
    } else {
      const time = Math.min(rel + f.from, (f.el.duration || Infinity) - 0.01);
      if (Math.abs(f.el.currentTime - time) > 0.15 || f.el.paused) f.el.currentTime = time;
    }
  }

  async function seek(t) {
    Studio.time = t;
    Studio.frame = Math.round(t * config.fps);
    // A clip placed at `start` on the timeline follows it; manual clips wait for footageAt().
    await Promise.all(Object.entries(footage).filter(([, f]) => !f.manual)
      .map(([n, f]) => showFrame(n, f, Math.max(0, t - f.start))));
    for (const fn of handlers) await fn(t, Studio);
    for (const a of document.getAnimations()) {
      a.pause();
      a.currentTime = t * 1000;
    }
  }

  const nextPaint = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));

  // ---- layout ---------------------------------------------------------------
  const style = document.createElement('style');
  document.head.appendChild(style);

  function stage() { return document.getElementById('stage'); }

  function layout() {
    const { width, height } = config;
    style.textContent = `
      html, body { margin: 0; padding: 0; }
      #stage { position: relative; overflow: hidden; width: ${width}px; height: ${height}px; }
      ${rendering ? `
        html, body { overflow: hidden; ${transparent ? 'background: transparent !important;' : ''} }
        #studio-bar { display: none !important; }
      ` : `
        html, body { background: #111; height: 100%; overflow: hidden; }
        #stage { position: absolute; left: 50%; top: calc(50% - 28px); transform-origin: 0 0; }
        #studio-bar { position: fixed; left: 0; right: 0; bottom: 0; height: 56px; display: flex; gap: 12px;
          align-items: center; padding: 0 16px; background: #1b1b1b; color: #ddd; z-index: 2147483647;
          font: 14px/1 ui-monospace, SFMono-Regular, Menlo, monospace; box-sizing: border-box; }
        #studio-bar button { background: #333; color: #fff; border: 0; border-radius: 6px; width: 44px; height: 36px;
          font-size: 16px; cursor: pointer; }
        #studio-bar input { flex: 1; accent-color: #7c9cff; }
      `}
    `;
    if (!rendering) fitPreview();
  }

  // ---- preview player (only when opened in a normal browser) ---------------
  let playing = false;
  let playStart = 0;
  let busy = false;
  let bar;

  function fitPreview() {
    const s = stage();
    if (!s) return;
    const { width, height } = config;
    const scale = Math.min(innerWidth / width, (innerHeight - 56) / height);
    s.style.transform = `scale(${scale}) translate(-50%, -50%)`;
  }

  function fmt(t) { return `${t.toFixed(2)}s / ${config.duration.toFixed(2)}s`; }

  async function show(t) {
    if (busy) return;
    busy = true;
    try {
      await seek(t);
      if (bar) {
        bar.range.value = String(t);
        bar.label.textContent = fmt(t);
      }
    } finally {
      busy = false;
    }
  }

  function tick(now) {
    if (playing) show(((now - playStart) / 1000) % config.duration);
    requestAnimationFrame(tick);
  }

  function buildBar() {
    const el = document.createElement('div');
    el.id = 'studio-bar';
    el.innerHTML = `<button aria-label="Play">▶</button><input type="range" min="0" step="0.001"><span></span>`;
    document.body.appendChild(el);
    const [button, range, label] = el.children;
    range.max = String(config.duration);
    const toggle = () => {
      playing = !playing;
      button.textContent = playing ? '❚❚' : '▶';
      playStart = performance.now() - Studio.time * 1000;
      for (const f of Object.values(footage)) {
        if (f.manual) continue;
        playing ? f.el.play().catch(() => {}) : f.el.pause();
      }
    };
    button.onclick = toggle;
    range.oninput = () => { if (playing) toggle(); show(+range.value); };
    addEventListener('keydown', (e) => { if (e.code === 'Space') { e.preventDefault(); toggle(); } });
    bar = { range, label };
  }

  if (!rendering) {
    addEventListener('resize', fitPreview);
    addEventListener('load', async () => {
      await Studio._whenReady();
      buildBar();
      fitPreview();
      await show(0);
      requestAnimationFrame(tick);
    });
  }

  window.Studio = Studio;
})();
