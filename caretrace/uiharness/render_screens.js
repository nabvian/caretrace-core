/* Renders every registered CARETRACE screen in jsdom against captured API
 * fixtures, and reports what each screen actually put in the DOM.
 *
 * Why this exists: `node --check` proves a file parses. It does not catch a
 * missing view-map entry, a helper that was never defined, or a field the API
 * does not return — which is where screen defects actually live. This executes
 * every screen for real.
 *
 * Fixtures come from snapshot_api.py, so the harness needs no listening socket.
 *
 * Usage: node render_screens.js [screen ...]
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const WEB = path.join(__dirname, '..', 'caretrace', 'web');
const SCRIPTS = ['core.js', 'screens_entry.js', 'screens_audit.js',
                 'screen_graph.js', 'screen_brief.js', 'screens_registry.js',
                 'screens_terminology.js'];

const fx = JSON.parse(fs.readFileSync(
  path.join(__dirname, 'fixtures', 'api.json'), 'utf8'));

const dom = new JSDOM('<!DOCTYPE html><body><div id="app"></div></body>', {
  url: 'http://localhost/', pretendToBeVisual: true, runScripts: 'outside-only',
});
const { window } = dom;

const errors = [];
window.addEventListener('error', (e) => errors.push('window.error: ' + e.message));
window.console = { log: () => {}, warn: () => {}, info: () => {}, debug: () => {},
  error: (...a) => errors.push('console.error: ' + a.join(' ')) };

/* Fixture-backed fetch. An unfixtured path is reported rather than silently
   returning empty, since a screen calling an endpoint nobody captured is
   itself a finding. */
const unfixtured = new Set();
window.fetch = async (url, opts = {}) => {
  const p = new URL(url, 'http://localhost').pathname;
  const method = (opts.method || 'GET').toUpperCase();
  if (method !== 'GET') {
    return { ok: true, status: 200, json: async () => ({}) };
  }
  const hit = fx.responses[p];
  if (!hit) {
    unfixtured.add(p);
    return { ok: false, status: 404, json: async () => ({ detail: 'no fixture' }) };
  }
  return { ok: hit.status === 200, status: hit.status,
           json: async () => hit.body };
};

// All screen modules share one global scope in the browser; concatenating
// keeps `const Router = …` in core.js visible to the files that use it.
// `const` at the top level of eval'd code is scoped to the eval, not to the
// global object, so the harness cannot see it. A trailing shim publishes the
// handful of objects it needs to drive. This does not alter the modules.
const bundle = SCRIPTS.map(f =>
  fs.readFileSync(path.join(WEB, 'js', f), 'utf8')).join('\n;\n')
  + '\n;\nwindow.__h = { State, Router, API, Drawer: typeof Drawer !== "undefined" ? Drawer : null };\n';
try {
  window.eval(bundle);
} catch (e) {
  console.log('LOADFAIL: ' + e.message);
  process.exit(1);
}

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

const H = window.__h;

(async () => {
  window.localStorage.setItem('caretrace.case', fx.case_id);
  H.State.caseId = fx.case_id;

  const args = process.argv.slice(2);
  const DUMP = args.includes('--dump');
  const screens = args.filter(a => a !== '--dump').length
    ? args.filter(a => a !== '--dump')
    : Object.keys(H.Router.routes || H.Router._routes || {});
  if (!screens.length) { console.log('no routes discovered'); process.exit(2); }

  let failed = 0, skipped = 0;
  for (const name of screens) {
    errors.length = 0;
    unfixtured.clear();
    H.State.clearCache();
    H.State.summary = null;
    const app = window.document.getElementById('app');
    app.replaceChildren();
    try {
      await H.Router.routes[name](app);
      for (let i = 0; i < 40 && /\u2026|Loading/.test(app.textContent); i++) {
        await sleep(25);
      }
      const txt = app.textContent || '';
      const bad = /undefined|NaN|\[object Object\]|Something went wrong/.exec(txt);
      const nodes = app.querySelectorAll('*').length;
      const ok = nodes > 5 && !bad && !errors.length && !unfixtured.size;
      if (!ok) failed++;
      console.log(
        `${ok ? 'OK  ' : 'FAIL'} ${name.padEnd(13)} nodes=${String(nodes).padStart(5)}`
        + ` chars=${String(txt.length).padStart(6)}`
        + (bad ? `  suspect="${bad[0]}"` : '')
        + (unfixtured.size ? `  unfixtured=${[...unfixtured]}` : '')
        + (errors.length ? `  ${JSON.stringify(errors.slice(0, 1))}` : ''));
      if (DUMP) {
        console.log(txt.replace(/\s*\n\s*/g, '\n').replace(/^/gm, '    | ')
          .slice(0, 3000) + '\n');
      }
    } catch (e) {
      // jsdom implements no 2D canvas context. A screen that draws to canvas
      // cannot be exercised here; that is a harness limit, not a defect, and
      // is reported as SKIP so it is never mistaken for a pass.
      if (/getContext|setTransform|canvas/i.test(e.message)) {
        skipped++;
        console.log(`SKIP ${name.padEnd(13)} canvas unavailable in jsdom`);
      } else {
        failed++;
        console.log(`FAIL ${name.padEnd(13)} threw: ${e.message}`);
      }
    }
  }
  const clean = screens.length - failed - skipped;
  console.log(`\n${clean}/${screens.length} rendered clean, ${skipped} skipped, `
    + `${failed} failed`);
  process.exit(failed ? 1 : 0);
})().catch(e => { console.log('HARNESS ERROR: ' + e.stack); process.exit(2); });
