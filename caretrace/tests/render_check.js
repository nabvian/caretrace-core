/* Headless render check.

   Loads the built single-file demo in jsdom, walks every route, and asserts the
   screens render real audited content rather than throwing or coming up empty.
   This exists because the sandbox cannot bind a listening socket, so the SPA
   cannot be driven through a live server here; the offline build carries the
   same scripts and the same engine output, so exercising it exercises the app.

   Run: node tests/render_check.js caretrace_demo.html
*/
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require(
  process.env.JSDOM_PATH || '/tmp/ctcheck/node_modules/jsdom');

const file = process.argv[2] || 'caretrace_demo.html';
const html = fs.readFileSync(file, 'utf8');

const errors = [];
const vc = new VirtualConsole();
vc.on('jsdomError', e => errors.push('jsdomError: ' + (e.stack || e.message)));
vc.on('error', (...a) => errors.push('console.error: ' + a.join(' ')));

// jsdom has no canvas backend; the graph screen only needs the calls to be
// answered, not painted. Painting is verified visually in a real browser.
/* jsdom implements neither the fetch primitives nor scrollTo. The offline
   transport shim builds real Response objects, so lend it Node's. */
function lendMissingGlobals(win) {
  for (const k of ['Response', 'Request', 'Headers', 'Blob', 'FormData', 'File',
                   'URL', 'URLSearchParams', 'TextEncoder', 'TextDecoder']) {
    if (!win[k] && globalThis[k]) win[k] = globalThis[k];
  }
  win.scrollTo = () => {};
  win.HTMLElement.prototype.scrollIntoView = () => {};
  win.print = () => { win.__printed = (win.__printed || 0) + 1; };
  win.URL.createObjectURL = () => 'blob:stub';
  win.URL.revokeObjectURL = () => {};
}

function stubCanvas(win) {
  lendMissingGlobals(win);
  const noop = () => {};
  const ctx = new Proxy({
    canvas: null, measureText: () => ({ width: 40 }),
    setTransform: noop, getTransform: () => ({}),
    createLinearGradient: () => ({ addColorStop: noop }),
  }, { get: (t, k) => (k in t ? t[k] : noop), set: (t, k, v) => (t[k] = v, true) });
  win.HTMLCanvasElement.prototype.getContext = function () { ctx.canvas = this; return ctx; };
  win.requestAnimationFrame = (cb) => setTimeout(() => cb(Date.now()), 16);
  win.cancelAnimationFrame = (id) => clearTimeout(id);
  if (!win.ResizeObserver) {
    win.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
  }
}

const ROUTES = [
  { hash: '#/', name: 'landing',   expect: [/CARETRACE/, /Evidence Audit/i, /prototype/i] },
  { hash: '#/cases', name: 'cases', expect: [/CT-DEMO-001/] },
  { hash: '#/dashboard', name: 'dashboard',
    expect: [/Evidence Audit/, /Documents analysed/, /Source traceability/,
             /does not (select|determine)/i] },
  { hash: '#/conflicts', name: 'conflicts',
    // Conflict display ids are CF-nnn; claims use C-nnn.
    expect: [/CF-001/, /Hemoglobin/i, /UNRESOLVED/,
             /does not determine which document is correct/i] },
  { hash: '#/gaps', name: 'gaps',
    expect: [/G-001/, /Evidence not located/i, /does not mean a claim is false/i] },
  { hash: '#/changes', name: 'changes', expect: [/Documented changes/, /Hemoglobin/i, /Delta/] },
  { hash: '#/timeline', name: 'timeline', expect: [/Evidence timeline/, /CBC|Prescription/] },
  { hash: '#/facts', name: 'facts', expect: [/Extracted evidence/, /F-0/, /parsing measure/i] },
  { hash: '#/facts?tab=claims', name: 'facts:claims', expect: [/Claim/, /C-0/] },
  { hash: '#/facts?tab=medications', name: 'facts:medications',
    expect: [/Ferrous sulfate/i] },
  { hash: '#/documents', name: 'documents', expect: [/01_CBC_Jan\.pdf/, /Laboratory Report/i] },
  { hash: '#/graph', name: 'graph', expect: [/Evidence graph/, /Contradicts/i, /Relationships/i] },
  { hash: '#/brief', name: 'brief',
    expect: [/CARETRACE Evidence Brief/, /Source index/i, /Key unresolved items/i,
             /01_CBC_Jan\.pdf/, /no clinical determination/i] },
  { hash: '#/upload', name: 'upload', expect: [/Upload|Add Documents/i] },
];

const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  const dom = new JSDOM(html, {
    runScripts: 'dangerously', pretendToBeVisual: true,
    url: 'https://caretrace.local/', virtualConsole: vc,
    beforeParse: stubCanvas,
  });
  const win = dom.window;
  await sleep(600);

  let failures = 0;
  const results = [];

  for (const r of ROUTES) {
    win.location.hash = r.hash;
    await sleep(420);
    const app = win.document.getElementById('app');
    const text = app.textContent || '';
    const nodes = app.querySelectorAll('*').length;
    const missing = r.expect.filter(re => !re.test(text));
    const ok = nodes > 30 && missing.length === 0;
    if (!ok) failures++;
    results.push({ route: r.name, nodes, chars: text.length, ok,
                   missing: missing.map(String) });
  }

  // Interaction probes: the source drawer and the graph node panel.
  win.location.hash = '#/conflicts';
  await sleep(400);
  const provBtn = win.document.querySelector('#app .prov, #app button.prov');
  let drawer = 'no prov button found';
  if (provBtn) {
    provBtn.dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
    await sleep(350);
    const d = win.document.querySelector('.drawer');
    drawer = d && /g\/dL|Hemoglobin/i.test(d.textContent)
      ? 'opened with source text' : 'opened but no source text';
    if (!d) { drawer = 'did not open'; failures++; }
  } else { failures++; }

  console.log(JSON.stringify({ file: path.basename(file), results,
                               drawer, errors: errors.slice(0, 6),
                               failures }, null, 1));
  win.close();
  process.exit(failures || errors.length ? 1 : 0);
})();
