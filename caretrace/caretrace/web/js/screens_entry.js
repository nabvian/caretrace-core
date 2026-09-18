/* Shell chrome plus the screens a user meets before the audit exists:
   landing, case list, upload, and the processing view. */

const NAV = [
  { section: 'Audit' },
  { id: 'dashboard', label: 'Evidence Audit', icon: '\u25EB' },
  { id: 'conflicts', label: 'Conflicts', icon: '\u26A1', badge: 'conflicts', tone: 'alert' },
  { id: 'gaps', label: 'Evidence Gaps', icon: '\u25CC', badge: 'evidence_gaps', tone: 'miss' },
  { id: 'changes', label: 'Changes', icon: '\u2197', badge: 'changes' },
  { section: 'Evidence' },
  { id: 'registry', label: 'Patient Registry', icon: '\u26AF',
    badge: 'identity_review', tone: 'miss' },
  { id: 'timeline', label: 'Timeline', icon: '\u2637' },
  { id: 'graph', label: 'Evidence Graph', icon: '\u25C7' },
  { id: 'facts', label: 'Facts & Claims', icon: '\u2261', badge: 'facts' },
  { id: 'documents', label: 'Documents', icon: '\u25A4', badge: 'documents' },
  { id: 'codings', label: 'Codings', icon: '\u2317', badge: 'codings' },
  { section: 'Output' },
  { id: 'brief', label: 'Evidence Brief', icon: '\u25A7' },
  { section: 'Settings' },
  { id: 'terminology', label: 'Terminology', icon: '\u2699' },
];

const Shell = {
  wrap(content) {
    const m = State.summary?.metrics || {};
    const nav = el('nav', { class: 'nav' });
    for (const item of NAV) {
      if (item.section) { nav.append(el('div', { class: 'nav-section' }, item.section)); continue; }
      const n = item.badge ? m[item.badge] : null;
      nav.append(el('a', {
        href: `#/${item.id}`,
        class: State.route === item.id ? 'active' : '',
      },
        el('span', { class: 'ico' }, item.icon),
        el('span', {}, item.label),
        (n !== null && n !== undefined)
          ? el('span', { class: 'count ' + (n > 0 && item.tone ? item.tone : '') }, n)
          : null));
    }

    const caseRef = State.summary?.case?.case_ref;
    return el('div', { class: 'shell' },
      el('aside', { class: 'sidebar no-print' },
        el('a', { class: 'brand', href: '#/landing', style: 'text-decoration:none;display:block' },
          el('span', { class: 'name' }, 'CARETRACE'),
          el('span', { class: 'tag' }, 'Evidence Audit')),
        nav,
        el('div', { class: 'foot' },
          'Research/prototype software. Not a diagnostic or treatment system.')),
      el('main', { class: 'main' },
        el('header', { class: 'topbar no-print' },
          caseRef ? el('span', { class: 'case-ref' }, caseRef) : null,
          State.summary?.case?.subject_label
            ? el('span', { class: 'tag' }, State.summary.case.subject_label) : null,
          State.summary?.case?.is_synthetic
            ? el('span', { class: 'chip s-documented plain' }, 'Synthetic data') : null,
          el('div', { class: 'spacer' }),
          el('a', { class: 'btn sm', href: '#/upload' }, 'Add documents'),
          el('a', { class: 'btn sm', href: '#/cases' }, 'Cases')),
        content));
  },
};

/** Guard: screens that need an audited case route through here. */
async function requireCase(root, render) {
  const stored = State.caseId || localStorage.getItem('caretrace.case');
  if (!stored) { Router.go('landing'); return; }
  State.caseId = stored;
  if (!State.summary || State.summary.case.id !== stored) {
    try { await State.refreshSummary(); }
    catch (e) { localStorage.removeItem('caretrace.case'); Router.go('landing'); return; }
  }
  if (!State.summary.metrics.processed) {
    root.replaceChildren(Shell.wrap(el('div', { class: 'content' },
      pageHead('Case not yet audited',
        `${State.summary.metrics.documents} documents ingested.`),
      card(null, el('div', { class: 'stack' },
        el('p', { class: 'muted' },
          'The evidence engine has not run for this case. No facts, conflicts or '
          + 'gaps exist until it does.'),
        el('div', {}, el('button', {
          class: 'btn primary',
          onclick: () => Router.go('processing'),
        }, 'Run Evidence Audit')))))));
    return;
  }
  await render(root);
}

/* ---------- Landing ---------- */

Router.register('landing', async (root) => {
  const flow = ['Documents', 'Facts', 'Relationships', 'Changes', 'Conflicts',
                'Gaps', 'Evidence brief'];
  const flowNodes = [];
  flow.forEach((s, i) => {
    if (i) flowNodes.push(el('span', { class: 'arr' }, '\u2192'));
    flowNodes.push(el('span', { class: 'step' }, s));
  });

  const openDemo = async (btn) => {
    btn.disabled = true;
    btn.replaceChildren(el('span', { class: 'spinner' }), document.createTextNode(' Loading demo case…'));
    try {
      const data = await API.post('/api/demo');
      State.caseId = data.case.id;
      localStorage.setItem('caretrace.case', data.case.id);
      State.clearCache();
      State.summary = data;
      Router.go('processing');
    } catch (err) {
      toast(err.message, true);
      btn.disabled = false;
      btn.textContent = 'Open Demo Case';
    }
  };

  root.replaceChildren(el('div', { class: 'landing' },
    el('div', { class: 'landing-nav' },
      el('div', {},
        el('div', { style: 'font-size:17px;font-weight:700;letter-spacing:.13em' }, 'CARETRACE'),
        el('div', { class: 'tiny muted', style: 'letter-spacing:.04em' },
          'Evidence audit for fragmented medical records')),
      el('div', { style: 'flex:1' }),
      el('a', { class: 'btn sm', href: '#/cases' }, 'Existing cases')),

    el('div', { class: 'landing-hero' },
      el('div', { class: 'eyebrow' }, 'Evidence infrastructure prototype'),
      el('h1', {}, 'Connect the evidence. Expose the gaps. Preserve the source.'),
      el('p', { class: 'lede' },
        'Turn scattered medical records into an auditable evidence map.'),
      el('p', { class: 'support' },
        'CARETRACE extracts documented facts, connects related evidence, identifies '
        + 'changes and contradictions, exposes missing information, and preserves '
        + 'source provenance back to the original document and page.'),
      el('div', { class: 'landing-flow' }, flowNodes),
      el('div', { class: 'row', style: 'gap:12px' },
        el('button', { class: 'btn primary', style: 'padding:10px 20px;font-size:14px',
          onclick: (e) => openDemo(e.currentTarget) }, 'Open Demo Case'),
        el('a', { class: 'btn', style: 'padding:10px 20px;font-size:14px', href: '#/upload' },
          'Upload Records')),
      el('div', { style: 'margin-top:34px;max-width:660px' },
        el('div', { class: 'disclaimer-bar' },
          el('span', { class: 'ico' }, '\u26A0'),
          el('span', {},
            'Research/prototype software. Not a diagnostic or treatment system. '
            + 'CARETRACE reports what the supplied documents state; it does not '
            + 'determine which record is correct and has not been clinically validated.')))),

    el('div', { class: 'landing-foot' },
      'CARETRACE reports only what the supplied documents state. '
      + 'Demonstration data is entirely synthetic.')));
});

/* ---------- Case list ---------- */

Router.register('cases', async (root) => {
  const cases = await API.get('/api/cases');
  const rows = cases.map(c => el('tr', {
    class: 'clickable',
    onclick: () => {
      State.caseId = c.id; localStorage.setItem('caretrace.case', c.id);
      State.clearCache(); State.summary = null;
      Router.go(c.processed ? 'dashboard' : 'processing');
    },
  },
    el('td', { class: 'mono' }, c.case_ref),
    el('td', {}, c.subject_label || '—'),
    el('td', { class: 'num' }, c.document_count),
    el('td', {}, c.processed ? chip('VERIFIED', 'Audited') : chip('MISSING', 'Not audited')),
    el('td', { class: 'small muted' }, c.created_at?.slice(0, 16).replace('T', ' ')),
    el('td', { class: 'right' },
      el('button', {
        class: 'btn sm danger',
        onclick: async (e) => {
          e.stopPropagation();
          if (!confirm(`Delete case ${c.case_ref} and all its documents?`)) return;
          await API.del(`/api/cases/${c.id}`);
          if (State.caseId === c.id) {
            localStorage.removeItem('caretrace.case');
            State.caseId = null; State.summary = null; State.clearCache();
          }
          toast('Case deleted'); Router.render();
        },
      }, 'Delete'))));

  const table = el('table', { class: 'table' },
    el('thead', {}, el('tr', {},
      el('th', {}, 'Case'), el('th', {}, 'Subject'), el('th', {}, 'Docs'),
      el('th', {}, 'Status'), el('th', {}, 'Created'), el('th', {}))),
    el('tbody', {}, rows));

  root.replaceChildren(Shell.wrap(el('div', { class: 'content' },
    pageHead('Cases', `${cases.length} case${cases.length === 1 ? '' : 's'} on this instance`,
      [el('a', { class: 'btn', href: '#/upload' }, 'New case from upload'),
       el('button', { class: 'btn primary', onclick: async (e) => {
         e.currentTarget.disabled = true;
         const d = await API.post('/api/demo');
         State.caseId = d.case.id; localStorage.setItem('caretrace.case', d.case.id);
         State.clearCache(); State.summary = d; Router.go('processing');
       } }, 'Open Demo Case')]),
    cases.length
      ? el('div', { class: 'card' }, el('div', { class: 'card-body tight' }, table))
      : el('div', { class: 'card' }, empty('No cases yet',
          'Open the demo case or upload documents to create one.')))));
});

/* ---------- Upload ---------- */

Router.register('upload', async (root) => {
  const meta = State.meta || (State.meta = await API.get('/api/meta'));
  let pending = [];

  const listNode = el('div', { class: 'stack' });
  const status = el('div', {});

  function renderPending() {
    listNode.replaceChildren();
    if (!pending.length) return;
    listNode.append(el('div', { class: 'card' },
      el('div', { class: 'card-head' }, el('h3', {}, `${pending.length} file${pending.length === 1 ? '' : 's'} ready`)),
      el('div', { class: 'card-body tight' },
        el('table', { class: 'table' },
          el('thead', {}, el('tr', {}, el('th', {}, 'File'), el('th', {}, 'Size'), el('th', {}))),
          el('tbody', {}, pending.map((f, i) => el('tr', {},
            el('td', {}, f.name),
            el('td', { class: 'num' }, `${(f.size / 1024).toFixed(0)} KB`),
            el('td', { class: 'right' }, el('button', {
              class: 'btn sm ghost',
              onclick: () => { pending.splice(i, 1); renderPending(); },
            }, 'Remove')))))))));
  }

  const input = el('input', {
    type: 'file', multiple: true, accept: '.pdf,.png,.jpg,.jpeg',
    style: 'display:none',
    onchange: (e) => { pending = pending.concat(Array.from(e.target.files)); renderPending(); },
  });

  const dz = el('div', {
    class: 'dropzone',
    onclick: () => input.click(),
    ondragover: (e) => { e.preventDefault(); dz.classList.add('dragover'); },
    ondragleave: () => dz.classList.remove('dragover'),
    ondrop: (e) => {
      e.preventDefault(); dz.classList.remove('dragover');
      pending = pending.concat(Array.from(e.dataTransfer.files));
      renderPending();
    },
  },
    el('div', { class: 'big' }, 'Drop medical documents here'),
    el('div', { class: 'sub' }, 'PDF \u00B7 PNG \u00B7 JPG \u2014 up to 25 MB each'),
    el('div', { style: 'margin-top:14px' },
      el('span', { class: 'btn primary' }, '+ Add Documents')),
    input);

  const caseRefInput = el('input', {
    type: 'text', placeholder: 'e.g. CT-2026-014',
    style: 'padding:7px 10px;border:1px solid var(--ink-300);border-radius:4px;width:200px;font-family:var(--mono);font-size:13px',
  });
  const subjectInput = el('input', {
    type: 'text', placeholder: 'Subject label (optional)',
    style: 'padding:7px 10px;border:1px solid var(--ink-300);border-radius:4px;width:240px;font-size:13px',
  });

  const submit = el('button', { class: 'btn primary', onclick: async () => {
    if (!pending.length) { toast('Add at least one document first', true); return; }
    submit.disabled = true;
    submit.replaceChildren(el('span', { class: 'spinner' }), document.createTextNode(' Uploading…'));
    try {
      const ref = caseRefInput.value.trim() || `CT-${Date.now().toString(36).toUpperCase()}`;
      const c = await API.post('/api/cases', {
        case_ref: ref, subject_label: subjectInput.value.trim() || null,
      });
      const res = await API.upload(`/api/cases/${c.id}/documents`, pending);
      const notes = [];
      if (res.rejected.length) {
        notes.push(`${res.rejected.length} file(s) rejected: `
          + res.rejected.map(r => `${r.filename} — ${r.reason}`).join('; '));
      }
      if ((res.duplicates || []).length) {
        // Reported, never silently dropped: the operator must be able to see
        // that a file was already present rather than wonder where it went.
        notes.push(`${res.duplicates.length} file(s) skipped as identical content: `
          + res.duplicates.map(d => `${d.filename} (same as ${d.duplicate_of})`).join('; '));
      }
      if (notes.length) {
        status.replaceChildren(...notes.map(t =>
          el('div', { class: 'disclaimer-bar', style: 'margin-top:12px' },
            el('span', { class: 'ico' }, '\u26A0'), el('span', {}, t))));
      }
      if (!res.accepted.length) {
        submit.disabled = false; submit.textContent = 'Create case and audit';
        return;
      }
      State.caseId = c.id; localStorage.setItem('caretrace.case', c.id);
      State.clearCache(); State.summary = null;
      Router.go('processing');
    } catch (err) {
      toast(err.message, true);
      submit.disabled = false; submit.textContent = 'Create case and audit';
    }
  } }, 'Create case and audit');

  root.replaceChildren(Shell.wrap(el('div', { class: 'content' },
    pageHead('Upload records',
      'Documents are parsed for structured values. Nothing is inferred that the text does not state.'),
    el('div', { class: 'grid cols-2' },
      el('div', { class: 'stack' },
        dz,
        listNode,
        status,
        el('div', { class: 'card' },
          el('div', { class: 'card-body' },
            el('div', { class: 'row wrap', style: 'gap:12px' },
              el('div', {}, el('div', { class: 'tiny upper muted', style: 'margin-bottom:4px' }, 'Case reference'), caseRefInput),
              el('div', {}, el('div', { class: 'tiny upper muted', style: 'margin-bottom:4px' }, 'Subject'), subjectInput)),
            el('div', { style: 'margin-top:14px' }, submit)))),
      el('div', { class: 'stack' },
        el('div', { class: 'disclaimer-bar' },
          el('span', { class: 'ico' }, '\u26A0'),
          el('span', {}, meta.disclaimer)),
        card('What CARETRACE extracts', el('div', {},
          el('p', { class: 'small muted' },
            'The MVP recognises these laboratory concepts by name and synonym, plus '
            + 'medications by arbitrary name. Anything it cannot parse is reported as '
            + 'extraction-incomplete rather than guessed.'),
          el('div', { class: 'row wrap', style: 'gap:5px' },
            ...meta.concepts.map(c => el('span', { class: 'tag' }, c.label))))),
        card('Document types', el('div', { class: 'row wrap', style: 'gap:5px' },
          ...Object.entries(meta.doc_types).map(([k, v]) =>
            el('span', { class: 'tag mono', title: v }, k)))))))));
});

/* ---------- Processing ---------- */

Router.register('processing', async (root) => {
  const cid = State.caseId || localStorage.getItem('caretrace.case');
  if (!cid) { Router.go('landing'); return; }
  State.caseId = cid;

  const STAGES = [
    ['INGEST', 'Read documents and pages'],
    ['CLASSIFY', 'Assign document types'],
    ['EXTRACT', 'Locate values in page text'],
    ['NORMALIZE', 'Map wording to concepts'],
    ['CREATE_FACTS', 'Build observation facts'],
    ['CREATE_CLAIMS', 'Separate claims from facts'],
    ['CREATE_EVENTS', 'Record document events'],
    ['RESOLVE_ENTITIES', 'Reconcile medications'],
    ['DETECT_CHANGES', 'Compare values over time'],
    ['DETECT_CONFLICTS', 'Compare values within episodes'],
    ['RESOLVE_CLAIMS', 'Search evidence for each claim'],
    ['BUILD_RELATIONSHIPS', 'Link evidence'],
    ['DETECT_GAPS', 'Find absent evidence'],
    ['GENERATE_AUDIT', 'Assemble audit'],
  ];

  const stageNodes = new Map();
  const list = el('div', { class: 'pipeline' });
  for (const [name, desc] of STAGES) {
    const ct = el('span', { class: 'ct' });
    const node = el('div', { class: 'stage' },
      el('span', { class: 'dot' }),
      el('span', { class: 'nm' }, name),
      el('span', { class: 'muted small' }, desc),
      ct);
    stageNodes.set(name, { node, ct });
    list.append(node);
  }

  const headline = el('div', { class: 'row' },
    el('span', { class: 'spinner' }),
    el('span', { class: 'strong' }, 'Running deterministic evidence audit…'));

  root.replaceChildren(Shell.wrap(el('div', { class: 'content' },
    pageHead('Processing', 'Each stage below is a real step in the pipeline, not an animation.'),
    el('div', { class: 'grid cols-2' },
      el('div', { class: 'card' },
        el('div', { class: 'card-head' }, headline),
        el('div', { class: 'card-body' }, list)),
      el('div', { class: 'stack' },
        card('How the audit works', el('div', { class: 'small' },
          el('p', {}, 'Extraction locates values in the page text and records the exact '
            + 'characters it matched. Every downstream finding keeps a reference to that '
            + 'span, which is why any result can be opened back to its source.'),
          el('p', {}, 'The comparison logic is deterministic — the same documents always '
            + 'produce the same audit. No language model participates in deciding whether '
            + 'two records disagree.'),
          el('p', { class: 'muted', style: 'margin-bottom:0' },
            'Where two documents disagree, CARETRACE reports both and marks the finding '
            + 'unresolved. It does not select a correct value.'))))))));

  // Walk the stage list visually while the request is in flight, then settle on
  // the real per-stage counts the server reports.
  let i = 0;
  const tick = setInterval(() => {
    if (i >= STAGES.length) return;
    const prev = STAGES[i - 1] && stageNodes.get(STAGES[i - 1][0]);
    if (prev) prev.node.className = 'stage done';
    stageNodes.get(STAGES[i][0]).node.className = 'stage active';
    i += 1;
  }, 90);

  try {
    const res = await API.post(`/api/cases/${cid}/process`);
    clearInterval(tick);
    for (const s of res.stages) {
      const entry = stageNodes.get(s.stage);
      if (!entry) continue;
      entry.node.className = 'stage done';
      const nums = Object.entries(s).filter(([k]) => k !== 'stage');
      entry.ct.textContent = nums.map(([k, v]) => `${v} ${k}`).join(' · ');
    }
    headline.replaceChildren(
      el('span', { class: 'chip s-verified' }, 'Complete'),
      el('span', { class: 'strong' }, 'Evidence audit complete'),
      el('div', { style: 'flex:1' }),
      el('button', { class: 'btn primary', onclick: () => Router.go('dashboard') },
        'View Evidence Audit \u2192'));
    State.clearCache();
    await State.refreshSummary();
    setTimeout(() => { if (State.route === 'processing') Router.go('dashboard'); }, 1100);
  } catch (err) {
    clearInterval(tick);
    headline.replaceChildren(
      el('span', { class: 'chip s-missing' }, 'Failed'),
      el('span', {}, err.message));
  }
});
