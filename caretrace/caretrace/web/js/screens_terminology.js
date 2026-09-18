/* Terminology screens: the case's vocabulary codings, and the provider admin.

   Both screens carry the same message in different words: a coding is an
   external vocabulary's opinion about a phrase, not part of what a document
   said, and no audit result depends on one. The admin screen exists so a
   reviewer can tell "this phrase has no published code" apart from "we are not
   licensed to look it up" — a distinction that silently disappears if
   unlicensed providers are simply skipped. */

/* Provider states are shown in the application's own status vocabulary rather
   than a private palette, so a chip means the same thing on this screen as it
   does on the conflicts screen: MISSING is something absent that could be
   present, CONFLICT is something wrong that needs attention. */
const STATE_CHIP = {
  ACTIVE: 'VERIFIED', UNLICENSED: 'MISSING', UNREACHABLE: 'CONFLICT',
  DISABLED: 'DOCUMENTED', UNKNOWN: 'DOCUMENTED',
};

/* ---------------------------------------------------------- case codings ---- */

Router.register('codings', (root) => requireCase(root, async (root) => {
  const [data, health] = await Promise.all([
    State.view('codings'),
    API.get('/api/terminology/providers').catch(() => null),
  ]);
  const rows = data.codings || [];

  const bySystem = el('div', { class: 'row wrap', style: 'gap:8px' },
    ...(data.by_system || []).map(b => el('div', { class: 'stat-inline' },
      el('span', { class: 'strong' }, b.system),
      el('span', { class: 'muted small' },
        `${b.total} coded \u00B7 ${b.assertable} assertable`
        + (b.approximate ? ` \u00B7 ${b.approximate} approximate` : '')))));

  // Providers that produced nothing are named explicitly: an empty column is
  // otherwise indistinguishable from a vocabulary that had no match.
  const inactive = (health?.providers || []).filter(p => p.state !== 'ACTIVE');

  const table = rows.length ? el('table', { class: 'table' },
    el('thead', {}, el('tr', {},
      el('th', {}, 'Annotates'), el('th', {}, 'Document wording'),
      el('th', {}, 'Vocabulary'), el('th', {}, 'Code'),
      el('th', {}, 'Published term'), el('th', {}, 'Match'),
      el('th', {}, 'Source'))),
    el('tbody', {}, ...rows.map(c => el('tr', {
      class: c.provenance ? 'clickable' : '',
      onclick: c.provenance ? () => Drawer.openSource(c.provenance) : null,
    },
      el('td', {},
        el('span', { class: 'mono small strong' }, c.subject_display_id || '\u2014'),
        el('div', { class: 'tiny muted' }, titleCase(c.subject_type))),
      el('td', { class: 'small' }, c.queried_text),
      el('td', {}, el('span', { class: 'tag' }, c.system)),
      el('td', { class: 'mono small' }, c.code),
      el('td', { class: 'small' }, c.display || '\u2014'),
      el('td', {},
        c.assertable
          ? chip('VERIFIED', titleCase(c.match_kind))
          : chip('UNRESOLVED', 'Approximate'),
        c.score != null
          ? el('div', { class: 'tiny muted' }, `score ${fmtNum(c.score)}`) : null),
      el('td', { class: 'tiny muted' },
        c.provenance ? c.provenance.filename : '\u2014')))))
    : empty('No codings recorded',
        'No vocabulary provider returned a code for this case. Annotation '
        + 'coverage depends on which providers are licensed and reachable.');

  root.replaceChildren(Shell.wrap(el('div', { class: 'content' },
    pageHead('Vocabulary codings',
      'Advisory links from documented wording to published vocabulary concepts.',
      el('a', { class: 'btn sm', href: '#/terminology' }, 'Provider settings')),

    // Stated before the data, not after it.
    el('div', { class: 'disclaimer-bar', style: 'margin-bottom:16px' },
      el('span', { class: 'ico' }, '\u24D8'),
      el('span', {}, data.note)),

    (data.by_system || []).length
      ? card('Coverage by vocabulary', el('div', { class: 'stack' },
          bySystem,
          inactive.length
            ? el('div', { class: 'small muted' },
                'Not contributing: '
                + inactive.map(p => `${p.label} (${p.state.toLowerCase()})`).join(', ')
                + '. An absent vocabulary means codes were not looked up \u2014 '
                + 'not that none exist.')
            : null))
      : null,

    card(`${rows.length} coding${rows.length === 1 ? '' : 's'}`, table))));
}));

/* ------------------------------------------------------- provider admin ---- */

Router.register('terminology', async (root) => {
  // Deliberately NOT behind requireCase: provider configuration is a property
  // of the deployment, and a user must be able to inspect it before any case
  // exists.
  root.replaceChildren(Shell.wrap(el('div', { class: 'content' },
    el('div', { class: 'row' }, el('span', { class: 'spinner' }), 'Probing providers\u2026'))));

  let health, cfg;
  try {
    [health, cfg] = await Promise.all([
      API.get('/api/terminology/providers'),
      API.get('/api/terminology/config'),
    ]);
  } catch (err) {
    root.replaceChildren(Shell.wrap(el('div', { class: 'content' },
      pageHead('Terminology'),
      empty('Provider status unavailable', String(err.message), '\u26A0'))));
    return;
  }

  const cards = health.providers.map((p) => {
    const conf = (cfg.configured || {})[p.key] || {};
    const vars = (cfg.env_vars || {})[p.key] || {};
    const missing = p.credentials_missing || [];

    /* A field the licence requires is reported MISSING when absent; an
       optional endpoint override is not missing when unset, it is simply
       defaulted. Conflating the two made a working provider look broken. */
    const required = new Set(p.licence?.credential_fields || []);
    const rows = [];
    for (const [field, envName] of Object.entries(vars)) {
      const set = conf[field] !== undefined && conf[field] !== null;
      rows.push(
        el('dt', {}, titleCase(field) + (required.has(field) ? '' : ' (optional)')),
        el('dd', {},
          el('span', { class: 'mono tiny' }, envName),
          el('span', { style: 'margin-left:8px' },
            set ? chip('VERIFIED', String(conf[field]))
                : required.has(field) ? chip('MISSING', 'not set')
                                      : chip('DOCUMENTED', 'default'))));
    }

    return el('div', { class: 'card' },
      el('div', { class: 'card-head' },
        el('div', {},
          el('h3', { style: 'margin:0' }, p.label),
          el('div', { class: 'tiny muted mono' }, p.system_uri || p.system)),
        el('div', { style: 'flex:1' }),
        chip(STATE_CHIP[p.state] || 'DOCUMENTED', titleCase(p.state))),
      el('div', { class: 'card-body' },
        el('div', { class: 'stack' },
          el('p', { class: 'small' }, p.detail),

          el('dl', { class: 'kv' },
            el('dt', {}, 'Codes'),
            el('dd', {}, (p.codes_kinds || []).length
              ? (p.codes_kinds).map(k => titleCase(k.replace(/_/g, ' '))).join(', ')
              : el('span', { class: 'muted' }, 'nothing')),
            el('dt', {}, 'Release'),
            el('dd', {}, p.version
              ? el('span', { class: 'mono small' }, p.version)
              : el('span', { class: 'muted small' }, 'not reported')),
            ...(p.latency_ms != null
              ? [el('dt', {}, 'Probe'),
                 el('dd', { class: 'small' }, `${fmtNum(p.latency_ms)} ms`)]
              : []),
            ...rows),

          // A licence-gated vocabulary states its terms and where to get one,
          // so the path from "unlicensed" to "active" is visible in the UI.
          p.licence?.required
            ? el('div', { class: 'note' },
                el('div', { class: 'strong small' }, 'Licence required'),
                el('p', { class: 'small', style: 'margin:4px 0' },
                  p.licence.note || ''),
                p.licence.obtain_url
                  ? el('a', { class: 'small', href: p.licence.obtain_url,
                              target: '_blank', rel: 'noopener noreferrer' },
                      p.licence.obtain_url)
                  : null,
                missing.length
                  ? el('div', { class: 'tiny muted', style: 'margin-top:6px' },
                      'Awaiting: ' + missing.join(', '))
                  : null)
            : null)));
  });

  root.replaceChildren(Shell.wrap(el('div', { class: 'content' },
    pageHead('Terminology providers',
      'Vocabulary services CARETRACE can consult, and what each one needs.'),

    el('div', { class: 'disclaimer-bar', style: 'margin-bottom:16px' },
      el('span', { class: 'ico' }, '\u24D8'),
      el('span', {}, health.note)),

    card('Status', el('div', { class: 'stack' },
      el('div', { class: 'row wrap', style: 'gap:8px' },
        ...health.providers.map(p =>
          chip(STATE_CHIP[p.state] || 'DOCUMENTED',
               `${p.label}: ${titleCase(p.state)}`))),
      el('p', { class: 'small muted', style: 'margin:0' },
        health.active.length
          ? `${health.active.length} of ${health.providers.length} providers active. `
            + 'Codings are written only for vocabularies that are both licensed '
            + 'and answering.'
          : 'No provider is active. Codings will be empty; the audit is '
            + 'unaffected.'))),

    el('div', { class: 'grid-2' }, ...cards),

    card('Bring your own licence', el('div', { class: 'stack' },
      el('p', { class: 'small' },
        'CARETRACE ships no vocabulary content. LOINC, SNOMED CT and ICD-11 '
        + 'each carry their own licence terms, so the deployment supplies '
        + 'credentials and CARETRACE consults the publisher\u2019s own service. '
        + 'Until then those providers report as unlicensed rather than '
        + 'silently returning nothing.'),
      el('p', { class: 'small' },
        'Credentials are read from the environment at startup and are never '
        + 'returned by the API \u2014 this screen shows only whether each field '
        + 'is set.'),
      el('p', { class: 'small muted' },
        'The variable names for each provider are listed on its card above.'))))));
});
