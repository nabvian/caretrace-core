/* Loads the built single-file demo in jsdom and renders every screen from it.
 *
 * The offline file is a separate artifact from the served app: it inlines the
 * scripts and replaces fetch with a lookup against a captured response table.
 * A screen can work when served and fail here -- typically because the builder
 * did not capture an endpoint the screen calls. This checks the artifact that
 * actually ships. */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const file = process.argv[2] || path.join(__dirname, '..', 'caretrace_demo.html');
const errors = [];

process.on('unhandledRejection', (e) => {
  const m = (e && e.message) || String(e);
  if (/getContext|canvas|setTransform/i.test(m) || m === '') return;
  errors.push('unhandledRejection: ' + m);
});

/* jsdom implements no Fetch API, so `Response` -- which the offline shim
   constructs -- is absent. Every real browser has it. Supplying a minimal
   stand-in before the page scripts parse keeps the check about the artifact
   rather than about jsdom's coverage. The shipped file is untouched. */
function installFetchTypes(win) {
  if (win.Response) return;
  win.Response = class {
    constructor(body, init = {}) {
      this._body = body;
      this.status = init.status === undefined ? 200 : init.status;
      this.ok = this.status >= 200 && this.status < 300;
      this.headers = { get: (k) => (init.headers || {})[k] };
    }
    async json() {
      return typeof this._body === 'string' ? JSON.parse(this._body) : this._body;
    }
    async text() { return String(this._body); }
    async arrayBuffer() { return this._body; }
    async blob() { return this._body; }
  };
}

const dom = new JSDOM(fs.readFileSync(file, 'utf8'), {
  url: 'http://offline.test/demo.html', runScripts: 'dangerously', pretendToBeVisual: true,
  beforeParse: installFetchTypes,
  virtualConsole: new (require('jsdom').VirtualConsole)()
    .on('jsdomError', e => errors.push('jsdomError: ' + e.message))
    .on('error', (...a) => errors.push('console.error: ' + a.join(' '))),
});
const { window } = dom;

const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  await sleep(400);

  /* The bundle declares `const Router = ...` at the top level of a classic
     script, which lands in global lexical scope -- visible to a later script
     element, but not as a property of `window`. Injecting a script is how a
     browser would reach it, and needs no test hook in the shipped file. */
  const probe = window.document.createElement('script');
  probe.textContent =
    'window.__probe = { State, Router, API, ' +
    'Drawer: typeof Drawer !== "undefined" ? Drawer : null };';
  window.document.body.appendChild(probe);

  const H = window.__probe || {};
  const Router = H.Router;
  const State = H.State;
  if (!Router) { console.log('FAIL: no router in offline bundle'); process.exit(1); }

  const db = window.__CARETRACE_OFFLINE__;
  const caseKey = Object.keys(db.responses || {})
    .find(k => /^GET \/api\/cases\/[0-9a-f-]{36}$/.test(k));
  const cid = caseKey ? caseKey.split('/').pop() : null;
  if (cid) { window.localStorage.setItem('caretrace.case', cid); State.caseId = cid; }

  let failed = 0, skipped = 0;
  const names = Object.keys(Router.routes);
  for (const name of names) {
    errors.length = 0;
    State.clearCache && State.clearCache();
    State.summary = null;
    const app = window.document.getElementById('app');
    app.replaceChildren();
    try {
      await Router.routes[name](app);
      for (let i = 0; i < 40 && /\u2026|Loading/.test(app.textContent); i++) await sleep(25);
      const txt = app.textContent || '';
      const bad = /undefined|NaN|\[object Object\]|no fixture|not available/.exec(txt);
      const nodes = app.querySelectorAll('*').length;
      const ok = nodes > 5 && !bad && !errors.length;
      if (!ok) failed++;
      console.log(`${ok ? 'OK  ' : 'FAIL'} ${name.padEnd(13)} nodes=${String(nodes).padStart(5)}`
        + (bad ? `  suspect="${bad[0]}"` : '')
        + (errors.length ? `  ${JSON.stringify(errors.slice(0, 1))}` : ''));
    } catch (e) {
      if (/getContext|setTransform|canvas/i.test(e.message)) {
        skipped++; console.log(`SKIP ${name.padEnd(13)} canvas unavailable in jsdom`);
      } else { failed++; console.log(`FAIL ${name.padEnd(13)} threw: ${e.message}`); }
    }
  }
  console.log(`\n${names.length - failed - skipped}/${names.length} offline screens clean, `
    + `${skipped} skipped, ${failed} failed`);
  process.exit(failed ? 1 : 0);
})().catch(e => { console.log('HARNESS ERROR: ' + e.stack); process.exit(2); });
