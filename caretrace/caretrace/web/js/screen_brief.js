/* Final evidence brief — the print/export view.

   The brief restates findings; it never introduces one. Everything here comes
   from the same endpoints the interactive screens use. */

Router.register('brief', (root) => requireCase(root, async (root) => {
  const b = await State.view('brief');
  const m = b.metrics;

  const metricBlock = (v, l) => el('div', { class: 'm' },
    el('div', { class: 'v' }, v), el('div', { class: 'l' }, l));

  const unresolved = b.key_unresolved.length
    ? b.key_unresolved.map((k, i) => el('div', { class: 'brief-item' },
        el('span', { class: 'n' }, String(i + 1).padStart(2, '0')),
        el('div', { style: 'flex:1' },
          el('div', { class: 'strong' }, k.title),
          el('div', { class: 'small muted' }, k.detail),
          el('div', { class: 'row wrap', style: 'gap:6px;margin-top:5px' },
            ...(k.provenance || []).map(p => prov(p)))),
        chip(k.status)))
    : [el('div', { class: 'small muted' },
        'No unresolved conflicts or evidence gaps were identified in the processed records.')];

  const conflictRows = b.conflicts.map(c => el('div', { class: 'brief-item' },
    el('span', { class: 'n' }, c.display_id.split('-')[1]),
    el('div', { style: 'flex:1' },
      el('div', { class: 'strong' }, `${c.concept_label} \u2014 ${c.left_summary} vs ${c.right_summary}`),
      el('div', { class: 'small muted' }, c.basis),
      el('div', { class: 'row wrap', style: 'gap:6px;margin-top:5px' },
        ...[...c.left_members, ...c.right_members]
          .filter(x => x.provenance).map(x => prov(x.provenance)))),
    chip('UNRESOLVED')));

  const gapRows = b.evidence_gaps.map(g => el('div', { class: 'brief-item' },
    el('span', { class: 'n' }, g.display_id.split('-')[1]),
    el('div', { style: 'flex:1' },
      el('div', { class: 'strong' }, g.title),
      el('div', { class: 'small muted' }, g.basis),
      g.evidence_not_located?.length
        ? el('div', { class: 'small', style: 'margin-top:4px' },
            el('span', { class: 'tiny upper muted' }, 'Not located: '),
            g.evidence_not_located.join(', '))
        : null,
      g.provenance ? el('div', { style: 'margin-top:5px' }, prov(g.provenance)) : null),
    chip('MISSING')));

  const changeTable = el('table', { class: 'table' },
    el('thead', {}, el('tr', {},
      el('th', {}, 'Concept'), el('th', {}, 'Date 1'), el('th', {}, 'Value 1'),
      el('th', {}, 'Date 2'), el('th', {}, 'Value 2'), el('th', {}, 'Delta'),
      el('th', {}, 'Sources'))),
    el('tbody', {}, ...b.changes.map(ch => el('tr', {},
      el('td', { class: 'strong' }, ch.concept_label),
      el('td', { class: 'nowrap small' }, fmtDate(ch.from_date)),
      el('td', { class: 'num' }, `${fmtNum(ch.from_value)} ${ch.unit || ''}`),
      el('td', { class: 'nowrap small' }, fmtDate(ch.to_date)),
      el('td', { class: 'num' }, `${fmtNum(ch.to_value)} ${ch.unit || ''}`),
      el('td', { class: 'num' }, `${ch.delta > 0 ? '+' : ''}${fmtNum(ch.delta)}`),
      el('td', {}, el('div', { class: 'row wrap', style: 'gap:4px' },
        prov(ch.from_provenance, { label: `p${ch.from_provenance?.page}` }),
        prov(ch.to_provenance, { label: `p${ch.to_provenance?.page}` })))))));

  const sourceTable = el('table', { class: 'table' },
    el('thead', {}, el('tr', {},
      el('th', {}, '#'), el('th', {}, 'Document'), el('th', {}, 'Type'),
      el('th', {}, 'Date'), el('th', {}, 'Pages'), el('th', {}, 'Facts'),
      el('th', {}, 'Status'))),
    el('tbody', {}, ...b.source_index.map((s, i) => el('tr', {},
      el('td', { class: 'mono tiny muted' }, String(i + 1).padStart(2, '0')),
      el('td', { class: 'mono small strong' }, s.filename),
      el('td', { class: 'small' }, s.doc_type_label),
      el('td', { class: 'nowrap small' }, fmtDate(s.doc_date)),
      el('td', { class: 'num' }, s.page_count),
      el('td', { class: 'num' }, s.fact_count),
      el('td', {}, s.processing_status === 'EXTRACTION_INCOMPLETE'
        ? chip('MISSING', 'Incomplete') : chip('VERIFIED', 'Processed'))))));

  const section = (title, ...body) => el('section', {}, el('h2', {}, title), ...body);

  root.replaceChildren(Shell.wrap(el('div', { class: 'content' },
    el('div', { class: 'row no-print', style: 'margin-bottom:16px' },
      el('div', { style: 'flex:1' }),
      el('button', { class: 'btn', onclick: () => downloadJSON(b) }, 'Export JSON'),
      el('button', { class: 'btn primary', onclick: () => window.print() }, 'Print / Export PDF')),

    el('div', { class: 'brief' },
      el('div', { class: 'brief-head' },
        el('div', { class: 't' }, 'CARETRACE Evidence Brief'),
        el('h1', {}, b.case.case_ref),
        el('div', { class: 'row', style: 'gap:12px;margin-top:7px' },
          el('span', { class: 'small muted' }, b.case.subject_label || 'Unnamed subject'),
          b.case.is_synthetic ? el('span', { class: 'chip s-documented plain' }, 'Synthetic data') : null,
          el('span', { class: 'small muted' },
            `Audited ${(b.last_run?.finished_at || '').slice(0, 10)} \u00B7 engine ${b.last_run?.engine_version || '—'}`))),

      section('Scope', el('div', { class: 'disclaimer-bar' },
        el('span', { class: 'ico' }, '\u26A0'), el('span', {}, b.disclaimer))),

      section('Audit metrics', el('div', { class: 'brief-metrics' },
        metricBlock(m.documents, 'Documents reviewed'),
        metricBlock(m.facts, 'Facts extracted'),
        metricBlock(m.claims, 'Claims'),
        metricBlock(m.medications, 'Medication records'),
        metricBlock(m.changes, 'Documented changes'),
        metricBlock(m.conflicts, 'Conflicts'),
        metricBlock(m.evidence_gaps, 'Evidence gaps'),
        metricBlock(`${Math.round((m.source_traceability || 0) * 100)}%`, 'Source traceability'))),

      section('Key unresolved items', ...unresolved),

      section(`Conflicts (${b.conflicts.length})`,
        b.conflicts.length ? el('div', {}, ...conflictRows)
          : el('div', { class: 'small muted' },
              'No conflicting documented values were detected among the processed records.')),

      section(`Evidence gaps (${b.evidence_gaps.length})`,
        b.evidence_gaps.length ? el('div', {}, ...gapRows)
          : el('div', { class: 'small muted' },
              'No absent supporting evidence was identified.')),

      section(`Documented changes (${b.changes.length})`,
        b.changes.length ? changeTable
          : el('div', { class: 'small muted' }, 'No value differences between dated records.')),

      section('Source index', sourceTable),

      el('div', { class: 'small muted', style: 'border-top:1px solid var(--ink-200);padding-top:12px' },
        'Every finding in this brief is derived from the documents listed in the source '
        + 'index. CARETRACE reports what those documents state; it does not resolve '
        + 'disagreements between them, and it makes no clinical determination.')))));
}));

function downloadJSON(brief) {
  const blob = new Blob([JSON.stringify(brief, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = el('a', { href: url, download: `caretrace_brief_${brief.case.case_ref}.json` });
  document.body.append(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
  toast('Evidence brief exported');
}
