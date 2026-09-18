/* CARETRACE frontend core: API client, state, router, shared renderers.
   No framework and no build step — the app is served as static files by the
   same process that serves the API, so the whole system runs from one command.

   The rendering rule enforced throughout: any element that displays a finding
   must also render its provenance control. `prov()` is the only way a source is
   drawn, so a screen cannot accidentally present an untraceable result. */

const API = {
  async req(path, opts = {}) {
    const res = await fetch(path, opts);
    if (!res.ok) {
      let detail = res.statusText;
      try { detail = (await res.json()).detail || detail; } catch (e) {}
      throw new Error(detail);
    }
    return res.status === 204 ? null : res.json();
  },
  get:  (p) => API.req(p),
  post: (p, body) => API.req(p, {
    method: 'POST',
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : null,
  }),
  del:  (p) => API.req(p, { method: 'DELETE' }),
  upload(p, files) {
    const fd = new FormData();
    for (const f of files) fd.append('files', f, f.name);
    return API.req(p, { method: 'POST', body: fd });
  },
};

const State = {
  caseId: null,
  summary: null,
  meta: null,
  cache: {},          // per-case view cache, cleared on reprocess
  route: 'landing',

  clearCache() { this.cache = {}; },

  async view(name) {
    if (this.cache[name]) return this.cache[name];
    const map = {
      documents: 'documents', facts: 'facts', claims: 'claims',
      medications: 'medications', changes: 'changes', series: 'series',
      conflicts: 'conflicts', gaps: 'evidence-gaps', timeline: 'timeline',
      graph: 'graph', brief: 'brief', codings: 'codings',
      patients: 'patients',
    };
    const data = await API.get(`/api/cases/${this.caseId}/${map[name]}`);
    this.cache[name] = data;
    return data;
  },

  async refreshSummary() {
    this.summary = await API.get(`/api/cases/${this.caseId}`);
    return this.summary;
  },
};

/* ---------- DOM helpers ---------- */

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') node.className = v;
    else if (k === 'html') node.innerHTML = v;
    else if (k === 'text') node.textContent = v;
    else if (k.startsWith('on') && typeof v === 'function') {
      node.addEventListener(k.slice(2).toLowerCase(), v);
    } else if (k === 'dataset') Object.assign(node.dataset, v);
    else node.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return node;
}

const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

/* ---------- Formatting ---------- */

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

function fmtDate(iso, precision) {
  if (!iso) return '—';
  const [y, m, d] = iso.split('-').map(Number);
  if (precision === 'month') return `${MONTHS[m - 1]} ${y}`;
  if (precision === 'year') return String(y);
  return `${String(d).padStart(2, '0')} ${MONTHS[m - 1]} ${y}`;
}
function fmtDateShort(iso) {
  if (!iso) return '—';
  const [, m, d] = iso.split('-').map(Number);
  return `${String(d).padStart(2, '0')} ${MONTHS[m - 1]}`;
}
function fmtNum(v) {
  if (v === null || v === undefined) return '—';
  return Number.isInteger(v) ? String(v) : String(parseFloat(v.toFixed(4)));
}
function titleCase(s) {
  return String(s || '').replace(/_/g, ' ').toLowerCase()
    .replace(/\b\w/g, c => c.toUpperCase());
}

/* ---------- Shared components ---------- */

function chip(status, label) {
  const s = String(status || 'DOCUMENTED').toLowerCase();
  return el('span', { class: `chip s-${s}` }, label || String(status).replace(/_/g, ' '));
}

/** The provenance control. Every displayed finding routes its source through
 *  here, which is what makes "no result without a source" structural. */
function prov(p, opts = {}) {
  if (!p) return el('span', { class: 'tiny muted' }, 'no source');
  const label = opts.label || `${p.filename} · p${p.page}`;
  return el('button', {
    class: 'prov', type: 'button', title: 'View source document and page',
    onclick: (e) => { e.stopPropagation(); Drawer.openSource(p); },
  }, el('span', { html: '&#9906;' }), label);
}

function metric(value, label, opts = {}) {
  const cls = ['metric', opts.tone ? `is-${opts.tone}` : '', opts.onClick ? 'clickable' : '']
    .filter(Boolean).join(' ');
  return el('div', {
    class: cls,
    onclick: opts.onClick || null,
    role: opts.onClick ? 'button' : null,
    tabindex: opts.onClick ? '0' : null,
    onkeydown: opts.onClick ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); opts.onClick(); } } : null,
  },
    el('div', { class: 'value' }, value),
    el('div', { class: 'label' }, label),
    opts.note ? el('div', { class: 'note' }, opts.note) : null);
}

function empty(msg, sub, icon = '\u25CB') {
  return el('div', { class: 'empty' },
    el('div', { class: 'ico' }, icon),
    el('div', { class: 'msg' }, msg),
    sub ? el('div', { class: 'sub' }, sub) : null);
}

function pageHead(title, sub, actions) {
  return el('div', { class: 'page-head row' },
    el('div', {}, el('h1', {}, title), sub ? el('div', { class: 'sub' }, sub) : null),
    el('div', { class: 'spacer', style: 'flex:1' }),
    actions ? el('div', { class: 'row no-print' }, actions) : null);
}

function card(title, body, actions) {
  return el('div', { class: 'card' },
    title ? el('div', { class: 'card-head' },
      el('h3', {}, title),
      el('div', { style: 'flex:1' }),
      actions || null) : null,
    el('div', { class: 'card-body' + (body?.classList?.contains('table') ? ' tight' : '') }, body));
}

function toast(msg, isError = false) {
  let t = $('#toast');
  if (!t) { t = el('div', { class: 'toast', id: 'toast' }); document.body.append(t); }
  t.textContent = msg;
  t.className = 'toast show' + (isError ? ' err' : '');
  clearTimeout(t._timer);
  t._timer = setTimeout(() => { t.className = 'toast'; }, 3200);
}

/* ---------- Source drawer ---------- */

const Drawer = {
  node: null,
  backdrop: null,

  ensure() {
    if (this.node) return;
    this.backdrop = el('div', { class: 'drawer-backdrop', onclick: () => this.close() });
    this.node = el('aside', { class: 'drawer', role: 'dialog', 'aria-label': 'Source document' });
    document.body.append(this.backdrop, this.node);
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') this.close();
    });
  },

  close() {
    if (!this.node) return;
    this.node.classList.remove('open');
    this.backdrop.classList.remove('open');
  },

  open(content) {
    this.ensure();
    this.node.replaceChildren(content);
    this.node.classList.add('open');
    this.backdrop.classList.add('open');
  },

  /** Show a document page with the cited text highlighted in place. */
  async openSource(p) {
    this.ensure();
    this.open(el('div', { class: 'drawer-body' },
      el('div', { class: 'row' }, el('span', { class: 'spinner' }), 'Loading source…')));
    try {
      const data = await API.get(`/api/sources/${p.source_id}`);
      const { source, page_text, document: doc } = data;
      this.open(el('div', { style: 'display:flex;flex-direction:column;height:100%' },
        el('div', { class: 'drawer-head' },
          el('div', {},
            el('h2', {}, source.filename),
            el('div', { class: 'small muted' },
              `${titleCase(doc.doc_type)} · Page ${source.page_number} of ${doc.page_count}`)),
          el('div', { style: 'flex:1' }),
          el('button', { class: 'btn ghost', onclick: () => this.close(), 'aria-label': 'Close' }, '\u2715')),
        el('div', { class: 'drawer-body' },
          el('div', { class: 'card', style: 'margin-bottom:14px' },
            el('div', { class: 'card-body' },
              el('dl', { class: 'kv' },
                el('dt', {}, 'Document'), el('dd', {}, source.filename),
                el('dt', {}, 'Type'), el('dd', {}, titleCase(doc.doc_type)),
                el('dt', {}, 'Document date'), el('dd', {}, fmtDate(doc.doc_date)),
                el('dt', {}, 'Page'), el('dd', {}, `${source.page_number} of ${doc.page_count}`),
                el('dt', {}, 'Source ID'), el('dd', { class: 'mono' }, source.id.slice(0, 8)),
                el('dt', {}, 'Extracted text'),
                el('dd', {}, el('span', { class: 'mono' }, source.source_text))))),
          el('h4', { style: 'margin-bottom:8px' }, 'Page as extracted'),
          el('div', { class: 'small muted', style: 'margin-bottom:8px' },
            'The highlighted line is the exact text the finding was derived from.'),
          this.renderPage(page_text, source.source_text)),
        el('div', { class: 'drawer-foot no-print' },
          el('a', { class: 'btn', href: `/api/documents/${doc.id}/file`, target: '_blank' },
            'Open original file'),
          // The raw text layer is retained verbatim per document, so the
          // operator can keep the original report content outside CARETRACE.
          el('a', { class: 'btn', href: `/api/documents/${doc.id}/text?download=true` },
            'Download raw text'),
          el('button', { class: 'btn ghost', onclick: () => this.close() }, 'Close'))));
    } catch (err) {
      this.open(el('div', { class: 'drawer-body' },
        empty('Source unavailable', String(err.message))));
    }
  },

  renderPage(pageText, highlight) {
    const node = el('div', { class: 'page-render' });
    const idx = highlight ? pageText.indexOf(highlight) : -1;
    if (idx < 0) {
      node.textContent = pageText || '(no extractable text on this page)';
      return node;
    }
    node.append(
      document.createTextNode(pageText.slice(0, idx)),
      el('mark', {}, highlight),
      document.createTextNode(pageText.slice(idx + highlight.length)));
    return node;
  },
};

/* ---------- Router ---------- */

const Router = {
  routes: {},
  register(name, fn) { this.routes[name] = fn; },

  go(name, params = {}) {
    const q = new URLSearchParams(params).toString();
    location.hash = `#/${name}${q ? '?' + q : ''}`;
  },

  parse() {
    const raw = location.hash.replace(/^#\/?/, '') || 'landing';
    const [name, query] = raw.split('?');
    return { name: name || 'landing', params: Object.fromEntries(new URLSearchParams(query || '')) };
  },

  async render() {
    const { name, params } = this.parse();
    State.route = name;
    const fn = this.routes[name] || this.routes.landing;
    const root = $('#app');
    try {
      await fn(root, params);
    } catch (err) {
      console.error(err);
      root.replaceChildren(Shell.wrap(
        el('div', { class: 'content' }, empty('Something went wrong', String(err.message), '\u26A0'))));
    }
    window.scrollTo(0, 0);
  },

  start() {
    window.addEventListener('hashchange', () => this.render());
    this.render();
  },
};
