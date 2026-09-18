/* Patient registry: who the documents were resolved to, and what was refused.

   The review queue is given equal weight to the resolved patients, not tucked
   into a corner. A registry screen that showed only successful links would
   present a tidier picture than the records support — and the documents it
   could not place are precisely the ones a reviewer has to act on.

   Nothing on this screen offers a "merge" button. Deciding that two records
   are the same person is a clinical judgement with consequences that outlast
   the session, and the MVP's honest position is to show the evidence and the
   candidates rather than to imply one click settles it. */

const BASIS_TEXT = {
  MRN_EXACT: 'Matched on the institution-issued record number',
  NAME_DOB_SEX: 'Matched on name, date of birth and sex',
  NAME_DOB: 'Matched on name and date of birth',
  NEW_PATIENT: 'First document for this patient',
  MRN_CONFLICT: 'Record number matches a patient with a different name',
  AMBIGUOUS: 'Matches more than one patient equally well',
  INSUFFICIENT_IDENTITY: 'Identity stated is too weak to match on',
  NO_IDENTITY_STATED: 'No patient identity stated in the document text',
  NO_READABLE_TEXT: 'No text could be extracted from the document',
  NO_MATCH: 'First record for this patient — the registry entry was created '
          + 'from this document',
};

/* The basis on a LINKED row says how the document reached the patient, and
 * "created the patient" is a different answer from "matched an existing one".
 * Collapsing both into a demographic-match label made the founding document
 * read as though it had matched a record that did not yet exist. */
const BASIS_LABEL = {
  MRN_EXACT: 'MRN',
  NAME_DOB_SEX: 'Demographics',
  NAME_DOB: 'Demographics',
  NO_MATCH: 'First record',
};

/* A refusal is not a failure of the same kind as a contradiction, so the two
   are not chipped alike: an MRN collision is a genuine disagreement between
   documents (CONFLICT), whereas an unreadable page or a weak identity is
   simply absent information (MISSING). */
const BASIS_CHIP = {
  MRN_CONFLICT: 'CONFLICT',
  AMBIGUOUS: 'UNRESOLVED',
};

function identityLine(a) {
  const parts = [];
  if (a.name) parts.push(a.name);
  if (a.dob) parts.push(`DOB ${a.dob}`);
  if (a.sex) parts.push(a.sex);
  if (a.mrn) parts.push(`MRN ${a.mrn}`);
  return parts.length ? parts.join('  \u00B7  ') : 'No identity fields stated';
}

Router.register('registry', (root) => requireCase(root, async (root) => {
  const data = await State.view('patients');
  const s = data.summary || {};

  const stats = el('div', { class: 'grid cols-4' },
    metric(s.patients, 'Patients'),
    metric(s.linked_documents, 'Documents linked'),
    // Tone only when there is something to act on: a warn chip on a zero
    // would train the reviewer to ignore the colour.
    metric(s.needs_review, 'Awaiting review',
           s.needs_review ? { tone: 'miss' } : {}),
    metric(s.clinicians, 'Clinicians documented',
           { note: `${s.institutions} institutions` }));

  /* ------------------------------------------------------------ patients ---- */

  const patientCards = (data.patients || []).map(p => {
    const pt = p.patient;
    const ev = p.evidence_totals || {};
    return el('div', { class: 'card' },
      el('div', { class: 'row', style: 'padding:14px 16px 0' },
        el('div', {},
          el('div', { class: 'row', style: 'gap:8px' },
            el('h3', {}, pt.display_name || '\u2014'),
            pt.is_synthetic ? el('span', { class: 'tag' }, 'SYNTHETIC') : null),
          el('div', { class: 'small muted' }, identityLine({
            dob: pt.dob, sex: pt.sex, mrn: pt.mrn }))),
        el('div', { style: 'flex:1' }),
        el('span', { class: 'mono small strong' }, pt.patient_ref)),

      el('div', { class: 'row wrap', style: 'gap:8px;padding:10px 16px' },
        el('div', { class: 'stat-inline' },
          el('span', { class: 'strong' }, p.documents.length),
          el('span', { class: 'muted small' }, 'documents')),
        el('div', { class: 'stat-inline' },
          el('span', { class: 'strong' }, ev.facts || 0),
          el('span', { class: 'muted small' }, 'facts')),
        el('div', { class: 'stat-inline' },
          el('span', { class: 'strong' }, ev.claims || 0),
          el('span', { class: 'muted small' }, 'claims')),
        el('div', { class: 'stat-inline' },
          el('span', { class: 'strong' }, ev.medications || 0),
          el('span', { class: 'muted small' }, 'medications')),
        el('div', { class: 'stat-inline' },
          el('span', { class: 'strong' }, (p.encounters || []).length),
          el('span', { class: 'muted small' }, 'encounters'))),

      el('table', { class: 'table' },
        el('thead', {}, el('tr', {},
          el('th', {}, 'Document'), el('th', {}, 'Date'),
          el('th', {}, 'Identity as documented'), el('th', {}, 'Basis'))),
        el('tbody', {}, ...p.documents.map(d => el('tr', {},
          el('td', {},
            el('span', { class: 'small strong' }, d.filename),
            el('div', { class: 'tiny muted' }, titleCase(d.doc_type || ''))),
          el('td', { class: 'small mono' }, d.doc_date || '\u2014'),
          el('td', { class: 'small' }, identityLine(d.asserted || {})),
          el('td', {},
            chip('VERIFIED', BASIS_LABEL[d.basis]
                 || titleCase((d.basis || '').replace(/_/g, ' '))),
            el('div', { class: 'tiny muted' },
              BASIS_TEXT[d.basis] || d.basis)))))));
  });

  /* -------------------------------------------------------- review queue ---- */

  const review = (data.review_queue || []);
  const reviewBody = review.length
    ? el('div', { class: 'stack' }, ...review.map(r => el('div', { class: 'card' },
        el('div', { class: 'row', style: 'padding:14px 16px 0' },
          el('span', { class: 'strong' }, r.filename),
          el('div', { style: 'flex:1' }),
          chip(BASIS_CHIP[r.basis] || 'MISSING',
               titleCase((r.basis || '').replace(/_/g, ' ')))),
        el('div', { class: 'small muted', style: 'padding:4px 16px 0' },
          identityLine(r.asserted || {})),
        el('p', { class: 'small', style: 'padding:8px 16px 0;margin:0' },
          r.rationale),
        (r.candidates || []).length
          ? el('div', { style: 'padding:10px 16px 0' },
              el('div', { class: 'tiny muted strong' }, 'CANDIDATES CONSIDERED'),
              el('table', { class: 'table' },
                el('thead', {}, el('tr', {},
                  el('th', {}, 'Patient'), el('th', {}, 'Identity'),
                  el('th', {}, 'Why it was considered'))),
                el('tbody', {}, ...r.candidates.map(c => el('tr', {},
                  el('td', { class: 'mono small' }, c.patient_ref),
                  el('td', { class: 'small' }, c.display_name || '\u2014'),
                  el('td', { class: 'small muted' }, c.why || '\u2014'))))))
          : null,
        el('div', { class: 'note small', style: 'margin:10px 16px 16px' },
          'This document is retained and its contents are extracted, but its '
          + 'rows are not compared against any patient\u2019s record. '
          + 'Resolution is a reviewer\u2019s decision.'))))
    : empty('Every document was resolved',
        'Each document in this case stated identity that matched exactly one '
        + 'patient. No document is awaiting review.');

  /* ------------------------------------------------------------ care team --- */

  const team = (data.care_team || []);
  const teamTable = team.length ? el('table', { class: 'table' },
    el('thead', {}, el('tr', {},
      el('th', {}, 'Clinician'), el('th', {}, 'Documented roles'),
      el('th', {}, 'Institution'), el('th', {}, 'Documents'))),
    el('tbody', {}, ...team.map(t => el('tr', {},
      el('td', { class: 'small strong' }, t.display_name),
      /* One person, all the roles the documents give them. A clinician who
       * both orders tests and writes notes is one clinician. */
      el('td', {}, ...String(t.roles || '').split(',').filter(Boolean)
        .map(r => el('span', { class: 'tag', style: 'margin-right:4px' },
                     titleCase(r.replace(/_/g, ' '))))),
      el('td', { class: 'small' }, t.institution
        || el('span', { class: 'muted' }, 'Not stated')),
      el('td', { class: 'mono small' }, t.documents)))))
    : empty('No clinicians identified',
        'No document in this case names an ordering, performing, authoring or '
        + 'referring clinician in a recognised header field.');

  root.replaceChildren(Shell.wrap(el('div', { class: 'content' },
    pageHead('Patient registry',
      'Which patient each document was resolved to, on what basis, and which '
      + 'documents could not be placed.'),
    stats,

    el('div', { class: 'note' },
      el('span', { class: 'strong' }, 'How resolution works. '),
      'A document is attached to a patient only on an institution-issued '
      + 'record number, or on a full demographic match. Anything weaker or '
      + 'ambiguous is queued for review rather than merged \u2014 an incorrect '
      + 'merge produces a record that looks internally consistent and is '
      + 'wrong, which no later check can detect.'),

    card('Resolved patients', patientCards.length
      ? el('div', { class: 'stack' }, ...patientCards)
      : empty('No patients resolved',
          'No document in this case stated identity strong enough to create a '
          + 'patient record.')),

    card(`Awaiting review${review.length ? ` (${review.length})` : ''}`,
         reviewBody),

    card('Documented care team', teamTable),

    el('div', { class: 'note small' },
      'Institution and clinician attribution is derived from letterheads and '
      + 'header fields, and is a convenience for the reviewer. No audit result '
      + 'depends on it; the document remains the provenance anchor for every '
      + 'fact.'))));
}));
