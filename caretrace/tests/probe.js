/* Ad-hoc diagnostic: dump what a single route actually renders. */
const fs = require('fs');
const { JSDOM, VirtualConsole } = require('/tmp/ctcheck/node_modules/jsdom');
const html = fs.readFileSync(process.argv[2] || 'caretrace_demo.html', 'utf8');
const route = process.argv[3] || '#/dashboard';

const errs = [];
const vc = new VirtualConsole();
vc.on('jsdomError', e => errs.push('jsdomError ' + (e.stack || e.message)));
vc.on('error', (...a) => errs.push('console.error ' + a.join(' ')));
vc.on('warn', (...a) => errs.push('warn ' + a.join(' ')));

function pre(win) {
  for (const k of ['Response', 'Request', 'Headers', 'Blob', 'FormData', 'File',
                   'URL', 'URLSearchParams'])
    if (!win[k] && globalThis[k]) win[k] = globalThis[k];
  win.scrollTo = () => {};
  win.HTMLElement.prototype.scrollIntoView = () => {};
  win.requestAnimationFrame = cb => setTimeout(() => cb(Date.now()), 16);
  win.cancelAnimationFrame = id => clearTimeout(id);
  win.ResizeObserver = class { observe() {} disconnect() {} unobserve() {} };
  win.HTMLCanvasElement.prototype.getContext = function () {
    const noop = () => {};
    return new Proxy({ canvas: this, measureText: () => ({ width: 40 }) },
      { get: (t, k) => (k in t ? t[k] : noop), set: (t, k, v) => (t[k] = v, true) });
  };
}

const DUMP_CHARS = Number(process.env.DUMP_CHARS || 700);
(async () => {
  const dom = new JSDOM(html, { runScripts: 'dangerously', pretendToBeVisual: true,
    url: 'https://caretrace.local/', virtualConsole: vc, beforeParse: pre });
  const w = dom.window;
  await new Promise(r => setTimeout(r, 700));
  console.log('offline case_id :', w.__CARETRACE_OFFLINE__.case_id);
  console.log('State.caseId   :', w.State && w.State.caseId);
  console.log('routes         :', w.Router && Object.keys(w.Router.routes).join(','));
  w.location.hash = route;
  await new Promise(r => setTimeout(r, 800));
  console.log(`--- ${route} text ---`);
  console.log(w.document.getElementById('app').textContent.trim().slice(0, DUMP_CHARS));
  console.log('--- errors ---');
  errs.slice(0, 6).forEach(e => console.log(e.split('\n').slice(0, 3).join(' | ').slice(0, 260)));
  process.exit(0);
})();
