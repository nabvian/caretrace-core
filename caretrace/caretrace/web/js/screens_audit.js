/* The audit screens: dashboard, conflicts, gaps, changes, timeline,
   facts/claims and documents. */

/* ---------- Dashboard ---------- */

Router.register('dashboard', (root) => requireCase(root, async (root) => {
  const m = State.summary.metrics;
  const [conflicts, gaps] = await Promise.all([State.view('conflicts'), State.view('gaps')]);
  const trace = Math.round((m.source_traceability || 0) * 100);

  const metrics = el('div', { class: 'grid cols-4' },
    metric(m.documents, 'Documents analysed',
      { onClick: () => Router.go('documents'),
        note: m.documents_incomplete ? `${m.documents_incomplete} extraction-incomplete` : `${m.pages} pages` }),
    metric(m.facts, 'Facts extracted', { onClick: () => Router.go('facts') }),
    metric(m.claims, 'Claims identified', { onClick: () => Router.go('facts', { tab: 'claims' }) }),
    metric(m.changes, 'Documented changes', { tone: 'warn', onClick: () => Router.go('changes') }),
    metric(m.conflicts, 'Conflicts', { tone: 'alert', onClick: () => Router.go('conflicts') }),
    metric(m.evidence_gaps, 'Evidence gaps', { tone: 'miss', onClick: () => Router.go('gaps') }),
    metric(m.unresolved, 'Unresolved items',
      { tone: m.unresolved ? 'alert' : 'ok', note: 'No automatic resolution' }),
    metric(`${trace}%`, 'Source traceability',
      { tone: trace === 100 ? 'ok' : 'warn',
        note: `${m.facts + m.claims + m.medications} items, each with a source` }));

  const priority = el('div', { class: 'stack' });
  const top = [
    ...conflicts.map(c => ({ kind: 'conflict', o: c })),
    ...gaps.map(g => ({ kind: 'gap', o: g })),
  ].slice(0, 5);

  if (!top.length) {
    priority.append(empty('No conflicts or gaps detected',
      'CARETRACE found no conflicting documented values and no absent supporting '
      + 'evidence among the currently processed records. This describes the records '
      + 'supplied, not their clinical accuracy.'));
  } else {
    for (const { kind, o } of top) {
      priority.append(el('div', {
        class: 'tl-entry ' + (kind === 'conflict' ? 'conflict' : 'missing'),
        style: 'cursor:pointer',
        onclick: () => Router.go(kind === 'conflict' ? 'conflicts' : 'gaps', { focus: o.id }),
      },
        el('span', { class: 'kind' }, o.display_id),
        el('div', { class: 'body' },
          el('div', { class: 'ttl' },
            kind === 'conflict'
              ? `${o.concept_label}: ${o.left_summary} vs ${o.right_summary}`
              : o.title),
          el('div', { class: 'small muted' },
            kind === 'conflict' ? titleCase(o.conflict_type) : titleCase(o.gap_type))),
        chip(kind === 'conflict' ? 'UNRESOLVED' : 'MISSING')));
    }
  }

  root.replaceChildren(Shell.wrap(el('div', { class: 'content' },
    pageHead('Evidence Audit',
      `${State.summary.case.case_ref} \u00B7 ${State.summary.case.subject_label || 'unnamed subject'}`,
      [el('a', { class: 'btn', href: '#/processing' }, 'Re-run audit'),
       el('a', { class: 'btn primary', href: '#/brief' }, 'Evidence Brief')]),
    metrics,
    el('div', { class: 'grid cols-2', style: 'margin-top:14px;align-items:start' },
      el('div', { class: 'card' },
        el('div', { class: 'card-head' },
          el('h3', {}, 'Items requiring review'),
          el('div', { style: 'flex:1' }),
          el('span', { class: 'small muted' }, `${conflicts.length + gaps.length} total`)),
        el('div', { class: 'card-body' }, priority)),
      el('div', { class: 'stack' },
        card('What this audit asserts', el('div', { class: 'small' },
          el('p', {}, el('span', { class: 'strong' }, 'Conflicts '),
            'mean two documents state different things about the same concept in the '
            + 'same episode. CARETRACE reports both and marks the finding unresolved; '
            + 'it does not select a correct value.'),
          el('p', {}, el('span', { class: 'strong' }, 'Evidence gaps '),
            'mean supporting evidence was not located in the uploaded records. That is '
            + 'a statement about the records, not about whether a claim is true.'),
          el('p', { style: 'margin-bottom:0' }, el('span', { class: 'strong' }, 'Changes '),
            'are differences between dated records. They are reported in neutral terms; '
            + 'no clinical direction is attributed to them.'))),
        card('Run detail', el('dl', { class: 'kv' },
          el('dt', {}, 'Engine'), el('dd', { class: 'mono' }, State.summary.last_run?.engine_version || '—'),
          el('dt', {}, 'Completed'), el('dd', { class: 'small' },
            (State.summary.last_run?.finished_at || '').slice(0, 19).replace('T', ' ') || '—'),
          el('dt', {}, 'Relationships'), el('dd', {}, m.relationships),
          el('dt', {}, 'Pages'), el('dd', {}, m.pages),
          el('dt', {}, 'Data'), el('dd', {},
            State.summary.case.is_synthetic ? 'Synthetic demonstration corpus' : 'Uploaded documents'))))))));
}));

/* ---------- Conflicts ---------- */

function conflictCard(c) {
  const sideNode = (label, summary, members) => el('div', { class: 'side' },
    el('div', { class: 'who' }, label),
    el('div', { class: 'val' }, summary),
    el('div', { class: 'srcs' },
      ...members.map(m => prov(m.provenance,
        { label: `${m.provenance?.filename} \u00B7 p${m.provenance?.page}` }))));

  return el('div', { class: 'finding alert', id: `f-${c.id}` },
    el('div', { class: 'finding-head' },
      el('span', { class: 'id' }, c.display_id),
      el('span', { class: 'title' }, c.concept_label || titleCase(c.concept)),
      el('span', { class: 'tag' }, titleCase(c.conflict_type)),
      el('div', { style: 'flex:1' }),
      chip('UNRESOLVED')),
    el('div', { class: 'finding-body' },
      el('div', { class: 'versus' },
        sideNode('Source A', c.left_summary, c.left_members),
        el('div', { class: 'mid' }, 'VS'),
        sideNode('Source B', c.right_summary, c.right_members)),
      c.delta ? el('div', { class: 'small muted', style: 'margin-top:9px' },
        `Difference: ${c.delta}`) : null,
      el('div', { class: 'basis' },
        el('span', { class: 'lab' }, 'Basis for this finding'),
        c.basis)));
}

Router.register('conflicts', (root) => requireCase(root, async (root) => {
  const conflicts = await State.view('conflicts');
  const body = conflicts.length
    ? el('div', { class: 'stack' }, ...conflicts.map(conflictCard))
    : el('div', { class: 'card' }, empty('No conflicts detected',
        'CARETRACE found no conflicting documented values among the currently '
        + 'processed records. This is a statement about the uploaded documents, not '
        + 'a confirmation that they are correct.', '\u2713'));

  root.replaceChildren(Shell.wrap(el('div', { class: 'content' },
    pageHead('Conflicts',
      `${conflicts.length} unresolved contradiction${conflicts.length === 1 ? '' : 's'} between source documents`),
    el('div', { class: 'disclaimer-bar', style: 'margin-bottom:14px' },
      el('span', { class: 'ico' }, '\u26A0'),
      el('span', {}, 'Every conflict below lists both sources and every record that '
        + 'restates each value. CARETRACE does not determine which document is correct.')),
    body)));

  const focus = Router.parse().params.focus;
  if (focus) $(`#f-${focus}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
}));

/* ---------- Evidence gaps ---------- */

function gapCard(g) {
  const list = (title, items, cls) => el('div', { class: `evidence-list ${cls}` },
    el('div', { class: 'hd' }, title),
    items.length
      ? el('ul', {}, ...items.map(x => el('li', {}, x)))
      : el('div', { class: 'none' }, 'None'));

  return el('div', { class: 'finding miss', id: `f-${g.id}` },
    el('div', { class: 'finding-head' },
      el('span', { class: 'id' }, g.display_id),
      el('span', { class: 'title' }, g.title),
      el('span', { class: 'tag' }, titleCase(g.gap_type)),
      el('div', { style: 'flex:1' }),
      chip('MISSING', 'Evidence not located')),
    el('div', { class: 'finding-body' },
      g.subject ? el('div', { class: 'row', style: 'margin-bottom:10px;gap:8px' },
        el('span', { class: 'tiny upper muted' }, `${g.subject.type}`),
        el('span', { class: 'mono small' }, g.subject.display_id || ''),
        g.provenance ? prov(g.provenance) : null) : null,
      el('div', { class: 'evidence-cols' },
        list('Evidence located', g.evidence_located, 'found'),
        list('Evidence not located', g.evidence_not_located, 'absent')),
      el('div', { class: 'basis' },
        el('span', { class: 'lab' }, 'Basis for this finding'),
        g.basis)));
}

Router.register('gaps', (root) => requireCase(root, async (root) => {
  const gaps = await State.view('gaps');
  const body = gaps.length
    ? el('div', { class: 'stack' }, ...gaps.map(gapCard))
    : el('div', { class: 'card' }, empty('No evidence gaps detected',
        'Every claim, medication and document reference in the processed records had '
        + 'corresponding evidence located.', '\u2713'));

  root.replaceChildren(Shell.wrap(el('div', { class: 'content' },
    pageHead('Evidence Gaps',
      `${gaps.length} item${gaps.length === 1 ? '' : 's'} where supporting evidence was not located`),
    el('div', { class: 'disclaimer-bar', style: 'margin-bottom:14px' },
      el('span', { class: 'ico' }, '\u26A0'),
      el('span', {}, '"Evidence not located" means the uploaded records do not contain '
        + 'the supporting item. It does not mean a claim is false or that a test was '
        + 'never performed.')),
    body)));

  const focus = Router.parse().params.focus;
  if (focus) $(`#f-${focus}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
}));

/* ---------- Changes ---------- */

function sparkline(series, conflictDates) {
  const pts = series.points;
  if (pts.length < 2) return null;
  const W = 640, H = 190, PAD = { t: 16, r: 20, b: 30, l: 46 };
  const iw = W - PAD.l - PAD.r, ih = H - PAD.t - PAD.b;
  const xs = pts.map(p => Date.parse(p.date));
  const ys = pts.map(p => p.value);
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  let y0 = Math.min(...ys), y1 = Math.max(...ys);
  const padY = (y1 - y0) * 0.18 || Math.abs(y1 * 0.1) || 1;
  y0 -= padY; y1 += padY;
  const sx = v => PAD.l + (x1 === x0 ? iw / 2 : ((v - x0) / (x1 - x0)) * iw);
  const sy = v => PAD.t + ih - ((v - y0) / (y1 - y0)) * ih;

  const NS = 'http://www.w3.org/2000/svg';
  const mk = (t, a = {}) => {
    const n = document.createElementNS(NS, t);
    for (const [k, v] of Object.entries(a)) if (v !== null) n.setAttribute(k, v);
    return n;
  };
  const svg = mk('svg', { class: 'chart-svg', viewBox: `0 0 ${W} ${H}`,
                          preserveAspectRatio: 'xMidYMid meet', role: 'img',
                          'aria-label': `${series.label} over time` });

  for (let i = 0; i <= 3; i++) {
    const y = PAD.t + (ih / 3) * i;
    svg.append(mk('line', { class: 'grid-line', x1: PAD.l, x2: W - PAD.r, y1: y, y2: y }));
    const t = mk('text', { class: 'axis-text', x: PAD.l - 7, y: y + 3.5, 'text-anchor': 'end' });
    t.textContent = fmtNum(parseFloat((y1 - (y1 - y0) * (i / 3)).toFixed(2)));
    svg.append(t);
  }
  svg.append(mk('line', { class: 'axis-line', x1: PAD.l, x2: W - PAD.r,
                          y1: PAD.t + ih, y2: PAD.t + ih }));

  const d = pts.map((p, i) => `${i ? 'L' : 'M'}${sx(Date.parse(p.date))},${sy(p.value)}`).join(' ');
  svg.append(mk('path', { class: 'series-line', d }));

  pts.forEach((p) => {
    const cx = sx(Date.parse(p.date)), cy = sy(p.value);
    const isConflict = conflictDates.has(p.date);
    const c = mk('circle', { class: 'pt' + (isConflict ? ' conflict' : ''),
                             cx, cy, r: 4.5 });
    c.addEventListener('click', () => Drawer.openSource(p.provenance));
    const title = mk('title');
    title.textContent = `${fmtDate(p.date)} — ${fmtNum(p.value)} ${p.unit || ''}\n`
      + `${p.provenance.filename} p${p.provenance.page}`;
    c.append(title);
    svg.append(c);

    const lbl = mk('text', { class: 'pt-label', x: cx, y: cy - 11, 'text-anchor': 'middle' });
    lbl.textContent = fmtNum(p.value);
    svg.append(lbl);

    const dt = mk('text', { class: 'axis-text', x: cx, y: PAD.t + ih + 16, 'text-anchor': 'middle' });
    dt.textContent = fmtDateShort(p.date);
    svg.append(dt);
  });
  return svg;
}

Router.register('changes', (root) => requireCase(root, async (root) => {
  const [changes, series, conflicts] = await Promise.all([
    State.view('changes'), State.view('series'), State.view('conflicts')]);

  const conflictDatesByConcept = {};
  for (const c of conflicts) {
    const set = conflictDatesByConcept[c.concept] || (conflictDatesByConcept[c.concept] = new Set());
    for (const m of [...c.left_members, ...c.right_members]) if (m.date) set.add(m.date);
  }

  const rows = changes.map(ch => el('tr', {},
    el('td', { class: 'mono tiny muted' }, ch.display_id),
    el('td', { class: 'strong' }, ch.concept_label),
    el('td', { class: 'nowrap' }, fmtDate(ch.from_date)),
    el('td', { class: 'num' }, `${fmtNum(ch.from_value)} ${ch.unit || ''}`),
    el('td', {}, prov(ch.from_provenance)),
    el('td', { class: 'nowrap' }, fmtDate(ch.to_date)),
    el('td', { class: 'num' }, `${fmtNum(ch.to_value)} ${ch.unit || ''}`),
    el('td', {}, prov(ch.to_provenance)),
    el('td', { class: 'num' },
      el('span', { class: 'tag' },
        `${ch.delta > 0 ? '+' : ''}${fmtNum(ch.delta)}`))));

  const table = el('table', { class: 'table' },
    el('thead', {}, el('tr', {},
      el('th', {}, 'ID'), el('th', {}, 'Concept'),
      el('th', {}, 'Date 1'), el('th', {}, 'Value 1'), el('th', {}, 'Source'),
      el('th', {}, 'Date 2'), el('th', {}, 'Value 2'), el('th', {}, 'Source'),
      el('th', {}, 'Delta'))),
    el('tbody', {}, rows));

  const charts = Object.values(series)
    .filter(s => s.points.length >= 2)
    .map(s => {
      const chart = sparkline(s, conflictDatesByConcept[s.concept] || new Set());
      return el('div', { class: 'card' },
        el('div', { class: 'card-head' },
          el('h3', {}, s.label),
          el('span', { class: 'tag mono' }, s.unit || ''),
          el('div', { style: 'flex:1' }),
          el('span', { class: 'tiny muted' },
            `documentation threshold ${s.material_abs} ${s.unit || ''} or ${Math.round(s.material_rel * 100)}%`)),
        el('div', { class: 'card-body' }, chart || empty('Single record', 'No change to plot.')));
    });

  root.replaceChildren(Shell.wrap(el('div', { class: 'content' },
    pageHead('Documented changes',
      `${changes.length} value difference${changes.length === 1 ? '' : 's'} between dated records`),
    el('div', { class: 'disclaimer-bar', style: 'margin-bottom:14px' },
      el('span', { class: 'ico' }, '\u26A0'),
      el('span', {}, 'These are differences between documents over time. Values recorded '
        + 'within the same episode are reported as conflicts instead. No clinical '
        + 'interpretation is attached to any direction of change.')),
    changes.length
      ? el('div', { class: 'card' }, el('div', { class: 'card-body tight' }, table))
      : el('div', { class: 'card' }, empty('No documented changes',
          'No concept was recorded with differing values on separate dates.')),
    charts.length ? el('h2', { style: 'margin:22px 0 12px' }, 'Numeric observations over time') : null,
    el('div', { class: 'grid cols-2' }, ...charts))));
}));

/* ---------- Timeline ---------- */

Router.register('timeline', (root) => requireCase(root, async (root) => {
  const days = await State.view('timeline');
  const KIND_ORDER = { document: 0, observation: 1, medication: 2, claim: 3, event: 4 };

  const nodes = days.map(day => {
    const entries = [...day.entries].sort(
      (a, b) => (KIND_ORDER[a.kind] ?? 9) - (KIND_ORDER[b.kind] ?? 9));
    const hasConflict = entries.some(e => e.conflict_ids?.length);
    const [y, m, d] = day.date.split('-');
    return el('div', { class: 'tl-day' + (hasConflict ? ' has-conflict' : '') },
      el('div', { class: 'tl-date' },
        `${d} ${MONTHS[Number(m) - 1]}`, el('span', { class: 'yr' }, y)),
      el('div', { class: 'tl-entries' },
        ...entries.map(e => el('div', {
          class: 'tl-entry' + (e.conflict_ids?.length ? ' conflict'
                 : e.status === 'MISSING' ? ' missing' : ''),
        },
          el('span', { class: 'kind' }, e.kind),
          el('div', { class: 'body' },
            el('div', { class: 'ttl' }, e.title),
            e.detail ? el('div', { class: 'det' }, e.detail) : null,
            el('div', { class: 'row', style: 'margin-top:5px;gap:6px' },
              prov(e.provenance),
              ...(e.conflict_ids || []).map(cid => el('button', {
                class: 'chip s-conflict', style: 'cursor:pointer;border:1px solid var(--alert-300)',
                onclick: () => Router.go('conflicts', { focus: cid }),
              }, 'Conflict')))))))); 
  });

  root.replaceChildren(Shell.wrap(el('div', { class: 'content' },
    pageHead('Evidence timeline',
      `${days.length} dated point${days.length === 1 ? '' : 's'} across the record set. `
      + 'Every entry links to the document and page it came from.'),
    days.length
      ? el('div', { class: 'timeline' }, ...nodes)
      : el('div', { class: 'card' }, empty('Nothing dated', 'No document carried a usable date.')))));
}));

/* ---------- Facts & claims ---------- */

Router.register('facts', (root) => requireCase(root, async (root) => {
  const params = Router.parse().params;
  const tab = params.tab || 'facts';
  const [facts, claims, meds] = await Promise.all([
    State.view('facts'), State.view('claims'), State.view('medications')]);

  const tabBtn = (id, label, n) => el('button', {
    class: 'btn' + (tab === id ? ' primary' : ''),
    onclick: () => Router.go('facts', { tab: id }),
  }, `${label} (${n})`);

  let body;
  if (tab === 'claims') {
    body = el('div', { class: 'card' }, el('div', { class: 'card-body tight' },
      el('table', { class: 'table' },
        el('thead', {}, el('tr', {},
          el('th', {}, 'ID'), el('th', {}, 'Claim'), el('th', {}, 'Type'),
          el('th', {}, 'Date'), el('th', {}, 'Evidence status'), el('th', {}, 'Source'))),
        el('tbody', {}, ...claims.map(c => el('tr', {},
          el('td', { class: 'mono tiny muted' }, c.display_id),
          el('td', {}, c.claim_text),
          el('td', {}, el('span', { class: 'tag' }, titleCase(c.claim_type))),
          el('td', { class: 'nowrap small' }, fmtDate(c.claim_date, c.date_precision)),
          el('td', {}, chip(
            c.evidence_status === 'SUPPORTING_EVIDENCE' ? 'VERIFIED'
              : c.evidence_status === 'CONTRADICTING_EVIDENCE' ? 'CONFLICT'
              : c.evidence_status === 'NO_LOCATED_EVIDENCE' ? 'MISSING' : 'DOCUMENTED',
            titleCase(c.evidence_status))),
          el('td', {}, prov(c.provenance))))))));
  } else if (tab === 'medications') {
    body = el('div', { class: 'card' }, el('div', { class: 'card-body tight' },
      el('table', { class: 'table' },
        el('thead', {}, el('tr', {},
          el('th', {}, 'ID'), el('th', {}, 'Drug'), el('th', {}, 'Dose'),
          el('th', {}, 'Frequency'), el('th', {}, 'Route'), el('th', {}, 'Status'),
          el('th', {}, 'Recorded'), el('th', {}, 'Source'))),
        el('tbody', {}, ...meds.map(m => el('tr', {},
          el('td', { class: 'mono tiny muted' }, m.display_id),
          el('td', { class: 'strong' }, m.drug_name),
          el('td', { class: 'num' }, m.dose ? `${fmtNum(m.dose)} ${m.unit || ''}` : '—'),
          el('td', {}, m.frequency || '—'),
          el('td', {}, m.route || '—'),
          el('td', {}, chip(m.status === 'ACTIVE' ? 'DOCUMENTED'
            : m.status === 'STOPPED' ? 'CHANGED' : 'MISSING', titleCase(m.status))),
          el('td', { class: 'nowrap small' }, fmtDate(m.record_date)),
          el('td', {}, prov(m.provenance))))))));
  } else {
    body = el('div', { class: 'card' }, el('div', { class: 'card-body tight' },
      el('table', { class: 'table' },
        el('thead', {}, el('tr', {},
          el('th', {}, 'ID'), el('th', {}, 'Concept'), el('th', {}, 'As written'),
          el('th', {}, 'Value'), el('th', {}, 'Date'), el('th', {}, 'Confidence'),
          el('th', {}, 'Source'))),
        el('tbody', {}, ...facts.map(f => el('tr', {},
          el('td', { class: 'mono tiny muted' }, f.display_id),
          el('td', { class: 'strong' }, f.concept_label),
          el('td', { class: 'small muted' }, f.surface_form),
          el('td', { class: 'num' },
            f.value_num !== null ? `${fmtNum(f.value_num)} ${f.unit || ''}` : (f.value_text || '—')),
          el('td', { class: 'nowrap small' }, fmtDate(f.obs_date, f.date_precision)),
          el('td', { class: 'num small muted' }, f.confidence?.toFixed(2) ?? '—'),
          el('td', {}, prov(f.provenance))))))));
  }

  root.replaceChildren(Shell.wrap(el('div', { class: 'content' },
    pageHead('Extracted evidence',
      'Every row records where in the source text it was found. '
      + 'Extraction confidence is a parsing measure, not a statement about medical truth.'),
    el('div', { class: 'row no-print', style: 'margin-bottom:14px' },
      tabBtn('facts', 'Facts', facts.length),
      tabBtn('claims', 'Claims', claims.length),
      tabBtn('medications', 'Medications', meds.length)),
    body)));
}));

/* ---------- Documents ---------- */

Router.register('documents', (root) => requireCase(root, async (root) => {
  const docs = await State.view('documents');

  const rows = docs.map(d => {
    const incomplete = d.processing_status === 'EXTRACTION_INCOMPLETE';
    return el('tr', { class: 'clickable', onclick: () => showDoc(d.id) },
      el('td', { class: 'strong mono small' }, d.filename),
      el('td', {}, el('span', { class: 'tag' }, d.doc_type_label)),
      el('td', { class: 'num' }, d.page_count),
      el('td', { class: 'nowrap small' }, fmtDate(d.doc_date)),
      el('td', { class: 'num' }, d.fact_count),
      el('td', {},
        incomplete ? chip('MISSING', 'Extraction incomplete') : chip('VERIFIED', 'Processed'),
        d.processing_note ? el('div', { class: 'tiny muted', style: 'margin-top:3px' },
          d.processing_note) : null),
      el('td', { class: 'num small muted' }, `${(d.byte_size / 1024).toFixed(0)} KB`));
  });

  async function showDoc(id) {
    Drawer.ensure();
    Drawer.open(el('div', { class: 'drawer-body' },
      el('div', { class: 'row' }, el('span', { class: 'spinner' }), 'Loading…')));
    const data = await API.get(`/api/documents/${id}`);
    const d = data.document;
    // Extraction provenance: how the text was obtained, and by which tool.
    // Recorded at ingestion, never inferred here.
    let raw = null;
    try { raw = await API.get(`/api/documents/${id}/text`); } catch (e) { raw = null; }
    Drawer.open(el('div', { style: 'display:flex;flex-direction:column;height:100%' },
      el('div', { class: 'drawer-head' },
        el('div', {},
          el('h2', {}, d.filename),
          el('div', { class: 'small muted' },
            `${titleCase(d.doc_type)} \u00B7 ${d.page_count} page(s) \u00B7 ${fmtDate(d.doc_date)}`)),
        el('div', { style: 'flex:1' }),
        el('button', { class: 'btn ghost', onclick: () => Drawer.close() }, '\u2715')),
      el('div', { class: 'drawer-body' },
        d.processing_note ? el('div', { class: 'disclaimer-bar', style: 'margin-bottom:14px' },
          el('span', { class: 'ico' }, '\u26A0'),
          el('span', {}, d.processing_note)) : null,
        raw ? el('div', { class: 'card', style: 'margin-bottom:14px' },
          el('div', { class: 'card-body' },
            el('dl', { class: 'kv' },
              el('dt', {}, 'Extraction method'),
              el('dd', {}, el('span', { class: 'mono' }, raw.method)),
              el('dt', {}, 'Tool'),
              el('dd', {}, raw.tool && raw.tool.name
                ? `${raw.tool.name} ${raw.tool.version || ''}`.trim() : '—'),
              el('dt', {}, 'Text layer'),
              el('dd', {}, raw.has_text_layer ? 'Present' : 'Not present'),
              el('dt', {}, 'Raw text retained'),
              el('dd', {}, `${raw.char_count.toLocaleString()} characters, verbatim`),
              el('dt', {}, 'Raw text checksum'),
              el('dd', { class: 'mono' }, (raw.text_sha256 || '').slice(0, 16))))) : null,
        el('div', { class: 'small muted', style: 'margin-bottom:6px' },
          `${data.facts.length} fact(s) extracted from this document`),
        ...data.pages.map(p => el('div', { style: 'margin-bottom:16px' },
          el('h4', { style: 'margin-bottom:6px' }, `Page ${p.page_number}`),
          el('div', { class: 'page-render' },
            p.text || '(no extractable text — this page carries no text layer)')))),
      el('div', { class: 'drawer-foot no-print' },
        el('a', { class: 'btn', href: `/api/documents/${id}/file`, target: '_blank' },
          'Open original file'),
        el('a', { class: 'btn', href: `/api/documents/${id}/text?download=true` },
          'Download raw text'),
        el('button', { class: 'btn ghost', onclick: () => Drawer.close() }, 'Close'))));
  }

  root.replaceChildren(Shell.wrap(el('div', { class: 'content' },
    pageHead('Documents', `${docs.length} document(s) in this case`,
      [el('a', { class: 'btn', href: '#/upload' }, 'Add documents')]),
    el('div', { class: 'card' }, el('div', { class: 'card-body tight' },
      el('table', { class: 'table' },
        el('thead', {}, el('tr', {},
          el('th', {}, 'File'), el('th', {}, 'Type'), el('th', {}, 'Pages'),
          el('th', {}, 'Date'), el('th', {}, 'Facts'), el('th', {}, 'Status'),
          el('th', {}, 'Size'))),
        el('tbody', {}, ...rows)))))));
}));
