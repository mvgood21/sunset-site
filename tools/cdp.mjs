// Headless Chrome helper for the site tools — Node 22+ (global WebSocket/fetch), no npm packages.
//
//   node tools/cdp.mjs jobs <jobs.json>        run a list of jobs in one browser
//
// Job kinds (JSON objects):
//   {"kind":"shot",   "url":..., "out":"a.png", "w":360, "h":800, "dark":false, "full":true, "reduced":false}
//   {"kind":"render", "url":"file:///.../x.html", "out":"x.png", "w":390, "h":844, "scale":2, "transparent":false}
//   {"kind":"audit",  "url":..., "w":360, "h":800, "dark":false}  -> bytes, requests, external hosts, overflow, fallback fonts
//   {"kind":"glyphs", "url":...}                                  -> {weight: "chars"} for text set in the site font
//
// Results are printed as one JSON array on stdout.
// CHROME env var overrides the browser path.

import { spawn } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync, existsSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const CANDIDATES = [
  process.env.CHROME,
  process.env.LOCALAPPDATA && join(process.env.LOCALAPPDATA, 'Google/Chrome/Application/chrome.exe'),
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  '/usr/bin/google-chrome', '/usr/bin/chromium',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
].filter(Boolean);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function launch() {
  const exe = CANDIDATES.find((p) => existsSync(p));
  if (!exe) throw new Error('Chrome not found; set CHROME');
  const dir = mkdtempSync(join(tmpdir(), 'sunset-cdp-'));
  const proc = spawn(exe, [
    '--headless=new', '--remote-debugging-port=0', `--user-data-dir=${dir}`,
    '--no-first-run', '--no-default-browser-check', '--disable-extensions', '--hide-scrollbars',
    '--allow-file-access-from-files', '--autoplay-policy=no-user-gesture-required', '--mute-audio',
    'about:blank',
  ], { stdio: 'ignore' });
  const portFile = join(dir, 'DevToolsActivePort');
  for (let i = 0; i < 200 && !existsSync(portFile); i++) await sleep(50);
  const port = readFileSync(portFile, 'utf8').split('\n')[0].trim();
  return { proc, dir, base: `http://127.0.0.1:${port}` };
}

class Page {
  static async open(base) {
    const t = await (await fetch(`${base}/json/new?about:blank`, { method: 'PUT' })).json();
    const p = new Page(t, base);
    await p.ready;
    return p;
  }
  constructor(target, base) {
    this.target = target; this.base = base; this.id = 0; this.pending = new Map(); this.handlers = [];
    this.ws = new WebSocket(target.webSocketDebuggerUrl);
    this.ready = new Promise((res) => this.ws.addEventListener('open', res));
    this.ws.addEventListener('message', (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id && this.pending.has(m.id)) {
        const { res, rej } = this.pending.get(m.id); this.pending.delete(m.id);
        m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result);
      } else if (m.method) { for (const h of this.handlers) h(m); }
    });
  }
  send(method, params = {}) {
    const id = ++this.id;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((res, rej) => this.pending.set(id, { res, rej }));
  }
  on(fn) { this.handlers.push(fn); }
  async close() { try { this.ws.close(); await fetch(`${this.base}/json/close/${this.target.id}`); } catch { /* ignore */ } }
  async eval(expr) {
    const r = await this.send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails));
    return r.result.value;
  }
  async setup({ w = 1440, h = 900, dark = false, reduced = false, scale = 1, transparent = false, mobile = w < 600 }) {
    await this.send('Page.enable');
    await this.send('Runtime.enable');
    await this.send('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: scale, mobile });
    await this.send('Emulation.setEmulatedMedia', { features: [
      { name: 'prefers-color-scheme', value: dark ? 'dark' : 'light' },
      { name: 'prefers-reduced-motion', value: reduced ? 'reduce' : 'no-preference' },
    ] });
    if (transparent) await this.send('Emulation.setDefaultBackgroundColorOverride', { color: { r: 0, g: 0, b: 0, a: 0 } });
  }
  async goto(url, settle = 600) {
    const loaded = new Promise((res) => this.on((m) => { if (m.method === 'Page.loadEventFired') res(); }));
    await this.send('Page.navigate', { url });
    await Promise.race([loaded, sleep(15000)]);
    await this.eval('document.fonts ? document.fonts.ready.then(() => true) : true');
    await sleep(settle);
  }
}

async function shot(page, job) {
  await page.setup(job);
  await page.goto(job.url, job.settle ?? 900);
  if (job.full) {
    // reveal-on-scroll content: mark everything visible before a full-page capture
    await page.eval(`document.querySelectorAll('.rv').forEach(e => e.classList.add('in')); true`);
    await sleep(500);
  }
  const params = { format: 'png' };
  if (job.full) {
    const m = await page.send('Page.getLayoutMetrics');
    const height = Math.ceil(m.cssContentSize.height);
    await page.send('Emulation.setDeviceMetricsOverride', { width: job.w, height, deviceScaleFactor: job.scale || 1, mobile: job.w < 600 });
    await sleep(400);
    params.captureBeyondViewport = true;
  }
  const r = await page.send('Page.captureScreenshot', params);
  writeFileSync(job.out, Buffer.from(r.data, 'base64'));
  return { kind: 'shot', out: job.out };
}

async function audit(page, job) {
  const reqs = new Map();
  page.on((m) => {
    if (m.method === 'Network.requestWillBeSent') reqs.set(m.params.requestId, { url: m.params.request.url, type: m.params.type, bytes: 0 });
    if (m.method === 'Network.responseReceived') { const r = reqs.get(m.params.requestId); if (r) { r.status = m.params.response.status; r.mime = m.params.response.mimeType; } }
    if (m.method === 'Network.loadingFinished') { const r = reqs.get(m.params.requestId); if (r) r.bytes = m.params.encodedDataLength; }
    if (m.method === 'Network.loadingFailed') { const r = reqs.get(m.params.requestId); if (r) r.failed = m.params.errorText; }
  });
  const errors = [];
  page.on((m) => {
    if (m.method === 'Runtime.exceptionThrown') errors.push(m.params.exceptionDetails.text);
    if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') errors.push(m.params.args.map((a) => a.value).join(' '));
  });
  await page.send('Network.enable');
  await page.send('Network.setCacheDisabled', { cacheDisabled: true });
  await page.setup(job);
  await page.goto(job.url, 1500);
  // scroll through so lazy media gets requested, as a reader would
  await page.eval(`(async () => { const H = document.documentElement.scrollHeight; for (let y = 0; y < H; y += innerHeight * 0.8) { scrollTo(0, y); await new Promise(r => setTimeout(r, 120)); } scrollTo(0, 0); return true; })()`);
  await sleep(1500);
  const layout = await page.eval(`(() => {
    const de = document.documentElement;
    const wide = [...document.querySelectorAll('body *')].filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && (r.right > de.clientWidth + 1); })
      .slice(0, 8).map(e => e.tagName.toLowerCase() + (e.className && typeof e.className === 'string' ? '.' + e.className.split(' ').join('.') : '') + ' right=' + Math.round(e.getBoundingClientRect().right));
    return { scrollWidth: de.scrollWidth, clientWidth: de.clientWidth, overflowing: wide };
  })()`);
  // fonts actually used to paint text: any non-site font means a glyph is missing from the subset
  await page.send('DOM.enable'); await page.send('CSS.enable');
  const { root } = await page.send('DOM.getDocument', { depth: -1 });
  const fallback = {};
  const visit = async (node) => {
    const attrs = node.attributes || [];
    const isSys = (n) => { const a = n.attributes || []; const i = a.indexOf('class'); return i >= 0 && i % 2 === 0 && /(^|\s)sys(\s|$)/.test(a[i + 1]); };
    // text set on purpose in the system font (e.g. "한국어" on /en/ pages) — skip it and its parent's report
    const intentionalSystem = isSys(node) || (node.children || []).some((c) => c.nodeType === 1 && isSys(c));
    if (!intentionalSystem && node.nodeType === 1 && node.children && node.children.some((c) => c.nodeType === 3 && c.nodeValue.trim())) {
      try {
        const f = await page.send('CSS.getPlatformFontsForNode', { nodeId: node.nodeId });
        for (const pf of f.fonts) {
          if (!/sunset/i.test(pf.familyName)) {
            const key = `${node.localName} -> ${pf.familyName}`;
            fallback[key] = (fallback[key] || 0) + pf.glyphCount;
          }
        }
      } catch { /* not rendered */ }
    }
    for (const c of node.children || []) await visit(c);
    if (node.contentDocument) await visit(node.contentDocument);
  };
  await visit(root);
  const list = [...reqs.values()];
  const origin = new URL(job.url).origin;
  return {
    kind: 'audit', url: job.url, w: job.w, dark: !!job.dark,
    totalBytes: list.reduce((s, r) => s + (r.bytes || 0), 0),
    requests: list.map((r) => ({ url: r.url.replace(origin, ''), type: r.type, bytes: r.bytes, status: r.status, failed: r.failed })),
    external: list.filter((r) => !r.url.startsWith(origin) && !r.url.startsWith('data:')).map((r) => r.url),
    layout, fallback, errors,
  };
}

async function glyphs(page, job) {
  await page.setup({ w: 1440, h: 900 });
  await page.goto(job.url, 300);
  const out = await page.eval(`(() => {
    const by = {};
    const add = (w, s) => { by[w] = (by[w] || '') + s; };
    const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = walk.nextNode())) {
      const el = n.parentElement; if (!el || !n.nodeValue.trim()) continue;
      if (el.closest('script,style,noscript,template')) continue;
      const cs = getComputedStyle(el);
      if (!/Sunset Sans/.test(cs.fontFamily.split(',')[0])) continue;
      let t = n.nodeValue;
      if (cs.textTransform === 'uppercase') t += t.toUpperCase();
      add(cs.fontWeight, t);
    }
    for (const el of document.querySelectorAll('*')) {
      for (const pseudo of ['::before', '::after', '::marker']) {
        const cs = getComputedStyle(el, pseudo);
        const c = cs.content;
        if (c && c !== 'none' && c !== 'normal' && /^"/.test(c)) add(cs.fontWeight, c.slice(1, -1));
        if (/counter/.test(c || '')) add(cs.fontWeight, '0123456789');
      }
    }
    for (const k of Object.keys(by)) by[k] = [...new Set(by[k])].join('');
    return by;
  })()`);
  return { kind: 'glyphs', url: job.url, weights: out };
}

async function main() {
  const [cmd, file] = process.argv.slice(2);
  if (cmd !== 'jobs' || !file) { console.error('usage: node tools/cdp.mjs jobs <jobs.json>'); process.exit(2); }
  const jobs = JSON.parse(readFileSync(file, 'utf8'));
  const b = await launch();
  const results = [];
  try {
    for (const job of jobs) {
      const page = await Page.open(b.base);
      try {
        if (job.kind === 'shot' || job.kind === 'render') results.push(await shot(page, job.kind === 'render' ? { full: false, mobile: false, ...job } : { full: true, ...job }));
        else if (job.kind === 'audit') results.push(await audit(page, job));
        else if (job.kind === 'glyphs') results.push(await glyphs(page, job));
        else if (job.kind === 'eval') { await page.setup(job); await page.goto(job.url, 300); results.push({ kind: 'eval', url: job.url, value: await page.eval(job.expr) }); }
        else throw new Error('unknown job ' + job.kind);
      } catch (e) {
        results.push({ kind: job.kind, url: job.url, error: String(e) });
      } finally { await page.close(); }
    }
  } finally {
    b.proc.kill();
    await sleep(300);
    try { rmSync(b.dir, { recursive: true, force: true }); } catch { /* chrome may hold files briefly */ }
  }
  process.stdout.write(JSON.stringify(results, null, 1));
}

main().catch((e) => { console.error(e); process.exit(1); });
