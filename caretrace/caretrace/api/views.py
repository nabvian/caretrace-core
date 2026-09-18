"""Read models for the API.

Every view assembled here hydrates provenance: a finding is never returned
without the document, page and verbatim source text it came from. The frontend
therefore cannot display a result that the user is unable to trace, because the
payload has nowhere to put one.

These functions are pure reads over the store. All audit logic lives in
caretrace.core.engine; nothing here decides anything.
"""
from __future__ import annotations

import json

from typing import Any, Optional

from ..core import models as M
from ..core.store import Store
from ..packs.medical import lexicon as LX

# --------------------------------------------------------------------------
# Provenance
# --------------------------------------------------------------------------


def _provenance(store: Store, source_id: Optional[str],
                srcs: Optional[dict] = None) -> Optional[dict]:
    """Resolve a source_id to {document, page, text} — the audit trail."""
    if not source_id:
        return None
    row = (srcs or {}).get(source_id) or store.source(source_id)
    if not row:
        return None
    return {
        "source_id": row["id"],
        "document_id": row["document_id"],
        "filename": row["filename"],
        "doc_type": row.get("doc_type"),
        "page": row["page_number"],
        "source_text": row["source_text"],
        "char_start": row.get("char_start"),
        "char_end": row.get("char_end"),
    }


class _Ctx:
    """Lookup tables for one case, built once per request."""

    def __init__(self, store: Store, case_id: str):
        self.store = store
        self.case_id = case_id
        self.sources = store.sources_map(case_id)
        self.documents = {d["id"]: d for d in store.documents(case_id)}
        self.facts = {f["id"]: f for f in store.rows("facts", case_id)}
        self.claims = {c["id"]: c for c in store.rows("claims", case_id)}
        self.medications = {m["id"]: m for m in store.rows("medications", case_id)}
        self.events = {e["id"]: e for e in store.rows("events", case_id)}

    def prov(self, source_id: Optional[str]) -> Optional[dict]:
        return _provenance(self.store, source_id, self.sources)

    def entity(self, kind: str, entity_id: str) -> Optional[dict]:
        return {
            "fact": self.facts, "claim": self.claims,
            "medication": self.medications, "event": self.events,
            "document": self.documents,
        }.get(kind, {}).get(entity_id)

    def describe(self, kind: str, entity_id: str) -> dict:
        """A uniform {id, label, detail, provenance} envelope for any entity."""
        row = self.entity(kind, entity_id)
        if row is None:
            return {"type": kind, "id": entity_id, "label": "(not found)",
                    "provenance": None}
        if kind == "fact":
            val = row["value_num"] if row["value_num"] is not None else row["value_text"]
            label = f"{val} {row['unit'] or ''}".strip()
            detail = LX.concept_label(row["concept"])
        elif kind == "claim":
            label, detail = row["claim_text"], "Clinical claim"
        elif kind == "medication":
            label = f"{row['drug_name']} {row['dose'] or ''}{row['unit'] or ''}".strip()
            detail = row["frequency"] or ""
        elif kind == "event":
            label = row["label"]
            detail = row["detail"] or row["event_type"].replace("_", " ").title()
        elif kind == "document":
            return {"type": "document", "id": entity_id,
                    "display_id": row["filename"], "label": row["filename"],
                    "detail": M.DocType.LABELS.get(row["doc_type"], row["doc_type"]),
                    "date": row["doc_date"], "provenance": None}
        else:
            label, detail = str(entity_id), ""
        return {
            "type": kind,
            "id": entity_id,
            "display_id": row.get("display_id"),
            "label": label,
            "detail": detail,
            "date": row.get("obs_date") or row.get("claim_date")
                    or row.get("record_date") or row.get("event_date"),
            "provenance": self.prov(row.get("source_id")),
        }


# --------------------------------------------------------------------------
# Views
# --------------------------------------------------------------------------


def case_summary(store: Store, case_id: str) -> dict:
    """Dashboard metrics. Every number is COUNTED from stored rows."""
    case = store.case(case_id)
    if not case:
        return {}
    docs = store.documents(case_id)
    facts = store.rows("facts", case_id)
    traceable = sum(1 for f in facts if f["source_id"] in store.sources_map(case_id))
    run = store.latest_run(case_id)
    return {
        "case": case,
        "metrics": {
            # A case counts as audited only when a run actually completed.
            # Presence of derived rows is not sufficient: a run that failed
            # part-way could leave some behind.
            "processed": bool(run and run.get("status") == "COMPLETE"),
            "documents": len(docs),
            "pages": sum(d["page_count"] for d in docs),
            "facts": len(facts),
            "claims": store.count("claims", case_id),
            "medications": store.count("medications", case_id),
            "changes": store.count("changes", case_id),
            "conflicts": store.count("conflicts", case_id),
            "evidence_gaps": store.count("evidence_gaps", case_id),
            "relationships": store.count("relationships", case_id),
            "unresolved": len(store.q(
                "SELECT id FROM conflicts WHERE case_id = ? AND status = ?",
                (case_id, M.Status.UNRESOLVED))),
            "source_traceability": round(traceable / len(facts), 4) if facts else 1.0,
            "documents_incomplete": sum(
                1 for d in docs if d["processing_status"] == "EXTRACTION_INCOMPLETE"),
            # Advisory annotation coverage. Reported alongside the audit
            # metrics but deliberately not one of them: no audit result
            # changes when this number is zero.
            "codings": store.count("codings", case_id),
            # Registry metrics. `identity_review` counts documents the registry
            # declined to attach to any patient -- a queue for a reviewer, and
            # the reason it is surfaced as a badge rather than buried: a
            # document nobody looks at is evidence nobody used.
            "patients": store.q1(
                "SELECT COUNT(DISTINCT patient_id) AS n FROM identity_links "
                "WHERE case_id = ? AND patient_id IS NOT NULL",
                (case_id,))["n"],
            "identity_review": store.q1(
                "SELECT COUNT(*) AS n FROM identity_links "
                "WHERE case_id = ? AND status = ?",
                (case_id, "NEEDS_REVIEW"))["n"],
        },
        "last_run": run,
    }


def documents(store: Store, case_id: str) -> list[dict]:
    out = []
    for d in store.documents(case_id):
        out.append({
            **d,
            "doc_type_label": M.DocType.LABELS.get(d["doc_type"], d["doc_type"]),
            "fact_count": len(store.q(
                "SELECT f.id FROM facts f JOIN sources s ON f.source_id = s.id "
                "WHERE s.document_id = ?", (d["id"],))),
        })
    return out


def document_detail(store: Store, document_id: str) -> dict:
    doc = store.q1("SELECT * FROM documents WHERE id = ?", (document_id,))
    if not doc:
        return {}
    pages = store.pages(document_id)
    facts = store.q(
        "SELECT f.*, s.page_number, s.source_text FROM facts f "
        "JOIN sources s ON f.source_id = s.id WHERE s.document_id = ? "
        "ORDER BY s.page_number, f.display_id", (document_id,))
    for f in facts:
        f["concept_label"] = LX.concept_label(f["concept"])
    return {
        "document": {**doc,
                     "doc_type_label": M.DocType.LABELS.get(doc["doc_type"],
                                                            doc["doc_type"])},
        "pages": pages,
        "facts": facts,
    }


def facts(store: Store, case_id: str) -> list[dict]:
    ctx = _Ctx(store, case_id)
    out = []
    for f in store.rows("facts", case_id, order="display_id"):
        out.append({**f,
                    "concept_label": LX.concept_label(f["concept"]),
                    "provenance": ctx.prov(f["source_id"])})
    return out


def claims(store: Store, case_id: str) -> list[dict]:
    ctx = _Ctx(store, case_id)
    out = []
    for c in store.rows("claims", case_id, order="display_id"):
        supporting = store.q(
            "SELECT * FROM relationships WHERE case_id = ? AND from_id = ? "
            "AND rel_type IN (?, ?)",
            (case_id, c["id"], M.RelType.SUPPORTS, M.RelType.CONTRADICTS))
        out.append({
            **c,
            "provenance": ctx.prov(c["source_id"]),
            "evidence": [
                {"rel_type": r["rel_type"], "detail": r["detail"],
                 **ctx.describe(r["to_type"], r["to_id"])}
                for r in supporting
            ],
        })
    return out


def changes(store: Store, case_id: str) -> list[dict]:
    ctx = _Ctx(store, case_id)
    out = []
    for c in store.rows("changes", case_id, order="display_id"):
        out.append({
            **c,
            "from_provenance": ctx.prov(
                (ctx.facts.get(c["from_fact_id"]) or {}).get("source_id")),
            "to_provenance": ctx.prov(
                (ctx.facts.get(c["to_fact_id"]) or {}).get("source_id")),
        })
    return out


def series(store: Store, case_id: str) -> dict[str, list[dict]]:
    """Numeric observation series per concept, for the change chart."""
    ctx = _Ctx(store, case_id)
    by_concept: dict[str, dict[str, dict]] = {}
    for f in store.rows("facts", case_id):
        if f["value_num"] is None or not f["obs_date"]:
            continue
        # One point per (concept, date); a restated value collapses onto itself
        # but a CONFLICTING value on the same date is kept as its own point.
        key = f"{f['obs_date']}|{f['value_num']}"
        by_concept.setdefault(f["concept"], {}).setdefault(key, {
            "date": f["obs_date"], "value": f["value_num"],
            "unit": f["unit"], "fact_id": f["id"],
            "display_id": f["display_id"],
            "provenance": ctx.prov(f["source_id"]),
            "restated_in": [],
        })
        entry = by_concept[f["concept"]][key]
        if entry["fact_id"] != f["id"]:
            entry["restated_in"].append(ctx.prov(f["source_id"]))
    out = {}
    for concept, points in by_concept.items():
        pts = sorted(points.values(), key=lambda p: (p["date"], p["value"]))
        if len(pts) < 2:
            continue
        cd = LX.CONCEPTS.get(concept)
        out[concept] = {
            "concept": concept,
            "label": LX.concept_label(concept),
            "unit": pts[0]["unit"] or (cd.canonical_unit if cd else None),
            # Materiality is a documentation threshold, not a clinical reference
            # range: it is what the engine used to decide agreement.
            "material_abs": cd.material_abs if cd else None,
            "material_rel": cd.material_rel if cd else None,
            "points": pts,
        }
    return out


def conflicts(store: Store, case_id: str) -> list[dict]:
    """Conflicts with BOTH sides fully sourced. Never a resolution."""
    ctx = _Ctx(store, case_id)
    out = []
    for c in store.rows("conflicts", case_id, order="display_id"):
        left = ctx.describe(c["left_type"], c["left_id"])
        right = ctx.describe(c["right_type"], c["right_id"])
        out.append({
            **c,
            "left": left,
            "right": right,
            "left_members": [ctx.describe(c["left_type"], i)
                             for i in c["left_member_ids"]],
            "right_members": [ctx.describe(c["right_type"], i)
                              for i in c["right_member_ids"]],
        })
    return out


def evidence_gaps(store: Store, case_id: str) -> list[dict]:
    ctx = _Ctx(store, case_id)
    out = []
    for g in store.rows("evidence_gaps", case_id, order="display_id"):
        subject = (ctx.describe(g["subject_type"], g["subject_id"])
                   if g["subject_id"] else None)
        # A gap has no source of its own — it is the ABSENCE of a source. Its
        # provenance is that of the claim or record that raised the question.
        out.append({**g, "subject": subject,
                    "provenance": (subject or {}).get("provenance")})
    return out


def medications(store: Store, case_id: str) -> list[dict]:
    ctx = _Ctx(store, case_id)
    return [{**m, "provenance": ctx.prov(m["source_id"])}
            for m in store.rows("medications", case_id, order="display_id")]


def timeline(store: Store, case_id: str) -> list[dict]:
    """Chronological evidence, each entry linked to its source."""
    ctx = _Ctx(store, case_id)
    conflict_fact_ids: dict[str, list[str]] = {}
    for c in store.rows("conflicts", case_id):
        for fid in list(c["left_member_ids"]) + list(c["right_member_ids"]):
            conflict_fact_ids.setdefault(fid, []).append(c["display_id"])

    entries: list[dict] = []
    for f in store.rows("facts", case_id):
        if not f["obs_date"]:
            continue
        entries.append({
            "date": f["obs_date"], "date_precision": f["date_precision"],
            "kind": "observation", "entity_type": "fact", "entity_id": f["id"],
            "display_id": f["display_id"],
            "title": LX.concept_label(f["concept"]),
            "detail": f"{f['value_num'] if f['value_num'] is not None else f['value_text']} {f['unit'] or ''}".strip(),
            "status": (M.Status.CONFLICT if f["id"] in conflict_fact_ids
                       else M.Status.DOCUMENTED),
            "conflict_ids": conflict_fact_ids.get(f["id"], []),
            "provenance": ctx.prov(f["source_id"]),
        })
    for m in store.rows("medications", case_id):
        if not m["record_date"]:
            continue
        entries.append({
            "date": m["record_date"], "date_precision": "day",
            "kind": "medication", "entity_type": "medication", "entity_id": m["id"],
            "display_id": m["display_id"], "title": m["drug_name"],
            "detail": " ".join(x for x in [
                f"{m['dose']:g}{m['unit']}" if m["dose"] else "",
                m["frequency"] or "", m["route"] or "", f"({m['status'].lower()})"
            ] if x),
            "status": M.Status.DOCUMENTED, "conflict_ids": [],
            "provenance": ctx.prov(m["source_id"]),
        })
    for c in store.rows("claims", case_id):
        if not c["claim_date"]:
            continue
        entries.append({
            "date": c["claim_date"], "date_precision": c["date_precision"],
            "kind": "claim", "entity_type": "claim", "entity_id": c["id"],
            "display_id": c["display_id"], "title": c["claim_text"],
            "detail": c["evidence_status"].replace("_", " ").title(),
            "status": (M.Status.MISSING
                       if c["evidence_status"] == M.ClaimEvidenceStatus.NO_LOCATED_EVIDENCE
                       else M.Status.DOCUMENTED),
            "conflict_ids": [],
            "provenance": ctx.prov(c["source_id"]),
        })
    for e in store.rows("events", case_id):
        if not e["event_date"]:
            continue
        entries.append({
            "date": e["event_date"], "date_precision": "day", "kind": "event",
            "entity_type": "event", "entity_id": e["id"],
            "display_id": e["display_id"], "title": e["label"],
            "detail": e["detail"] or e["event_type"].replace("_", " ").title(),
            "status": M.Status.DOCUMENTED, "conflict_ids": [],
            "provenance": ctx.prov(e["source_id"]),
        })

    entries.sort(key=lambda x: (x["date"], x["display_id"] or ""))
    # Group into days for the UI
    days: list[dict] = []
    for e in entries:
        if not days or days[-1]["date"] != e["date"]:
            days.append({"date": e["date"], "entries": []})
        days[-1]["entries"].append(e)
    return days


def graph(store: Store, case_id: str) -> dict:
    """Nodes and edges for the evidence graph."""
    ctx = _Ctx(store, case_id)
    nodes: list[dict] = []
    seen: set[str] = set()

    def add(kind: str, entity_id: str) -> None:
        if entity_id in seen:
            return
        seen.add(entity_id)
        desc = ctx.describe(kind, entity_id)
        nodes.append({
            "id": entity_id, "type": kind,
            "display_id": desc.get("display_id"),
            "label": desc.get("label"), "detail": desc.get("detail"),
            "date": desc.get("date"), "provenance": desc.get("provenance"),
        })

    for d in store.documents(case_id):
        add("document", d["id"])
    for f in ctx.facts:
        add("fact", f)
    for c in ctx.claims:
        add("claim", c)
    for m in ctx.medications:
        add("medication", m)
    for e in ctx.events:
        add("event", e)

    edges: list[dict] = []
    # Containment: document -> extracted item, derived from the sources table.
    for kind, table in (("fact", "facts"), ("claim", "claims"),
                        ("medication", "medications"), ("event", "events")):
        for row in store.rows(table, case_id):
            src = ctx.sources.get(row["source_id"])
            if src:
                edges.append({
                    "id": f"contains:{row['id']}",
                    "source": src["document_id"], "target": row["id"],
                    "rel_type": "CONTAINS",
                    "detail": f"page {src['page_number']}",
                    "status": M.Status.DOCUMENTED,
                })
    for r in store.rows("relationships", case_id):
        # MISSING_SUPPORT points at a concept that has no record precisely
        # because it is absent. Materialise it as an explicit node rather than
        # dropping the edge: representing missing evidence visibly is a core
        # promise, and a silently pruned edge would hide it.
        if r["to_type"] == "concept" and r["to_id"] not in seen:
            keys = [k for k in r["to_id"].split(",") if k]
            seen.add(r["to_id"])
            nodes.append({
                "id": r["to_id"], "type": "absent_evidence",
                "display_id": None,
                "label": ", ".join(LX.concept_label(k) for k in keys) or r["to_id"],
                "detail": "Not located in the uploaded records",
                "date": None, "provenance": None,
            })
        if r["from_id"] not in seen or r["to_id"] not in seen:
            continue
        edges.append({
            "id": r["id"], "source": r["from_id"], "target": r["to_id"],
            "rel_type": r["rel_type"], "detail": r["detail"],
            "status": r["status"],
        })
    return {"nodes": nodes, "edges": edges}


def brief(store: Store, case_id: str) -> dict:
    """The final evidence brief — an assembly of the other views, not new logic."""
    summary = case_summary(store, case_id)
    cfs = conflicts(store, case_id)
    gaps = evidence_gaps(store, case_id)
    chs = changes(store, case_id)

    key_items = []
    for c in cfs:
        if c["status"] != M.Status.UNRESOLVED:
            continue
        key_items.append({
            "kind": "conflict", "display_id": c["display_id"],
            "title": f"{c['concept_label']} — documented values disagree",
            "detail": f"{c['left_summary']} vs {c['right_summary']}",
            "status": c["status"],
        })
    for g in gaps:
        key_items.append({
            "kind": "evidence_gap", "display_id": g["display_id"],
            "title": g["title"], "detail": g["basis"], "status": g["status"],
        })

    source_index = []
    for d in documents(store, case_id):
        source_index.append({
            "filename": d["filename"], "doc_type_label": d["doc_type_label"],
            "doc_date": d["doc_date"], "pages": d["page_count"],
            "facts": d["fact_count"], "status": d["processing_status"],
            "note": d.get("processing_note"),
        })

    return {
        **summary,
        "key_unresolved": key_items,
        "conflicts": cfs,
        "evidence_gaps": gaps,
        "changes": chs,
        "source_index": source_index,
        "disclaimer": (
            "CARETRACE is a research/prototype evidence-auditing system. It "
            "does not provide medical diagnosis or treatment recommendations "
            "and has not been clinically validated. All findings describe what "
            "the supplied documents state, not the condition of any person."),
    }


def codings(store: Store, case_id: str) -> dict:
    """Vocabulary codings for a case, with what each one annotates.

    Presented separately from facts and claims, and labelled advisory, so the
    UI cannot imply that a code is part of what a document stated. Assertable
    and approximate codings are counted apart: an approximate match is a
    suggestion for a reviewer, never an identity claim.
    """
    ctx = _Ctx(store, case_id)
    subj_label = {}
    for f in store.rows("facts", case_id):
        subj_label[f["id"]] = (f.get("display_id"),
                               LX.concept_label(f["concept"]), f.get("source_id"))
    for m in store.rows("medications", case_id):
        subj_label[m["id"]] = (m.get("display_id"), m.get("drug_name"),
                               m.get("source_id"))
    for c in store.rows("claims", case_id):
        subj_label[c["id"]] = (c.get("display_id"), c.get("claim_text"),
                               c.get("source_id"))
    rows = []
    for r in store.rows("codings", case_id):
        disp, label, source_id = subj_label.get(r["subject_id"], (None, None, None))
        rows.append({**r,
                     "subject_display_id": disp,
                     "subject_label": label,
                     "provenance": ctx.prov(source_id) if source_id else None})
    rows.sort(key=lambda r: (r["subject_type"], r["subject_display_id"] or "",
                             r["system"]))
    by_system: dict[str, dict] = {}
    for r in rows:
        b = by_system.setdefault(r["system"], {"system": r["system"], "total": 0,
                                               "assertable": 0, "approximate": 0})
        b["total"] += 1
        if r["assertable"]:
            b["assertable"] += 1
        else:
            b["approximate"] += 1
    return {
        "codings": rows,
        "by_system": sorted(by_system.values(), key=lambda b: -b["total"]),
        "note": ("Codings are advisory vocabulary annotations. They record that "
                 "a phrase in a document plausibly denotes a published concept. "
                 "No audit result depends on them."),
    }


def patients(store: Store, case_id: str) -> dict:
    """The registry as it applies to one case, plus the review queue.

    Two things are deliberately reported side by side: the patients the case
    resolved to, and the documents it refused to attach to any of them. A
    registry screen that showed only successful links would hide exactly the
    information a reviewer needs -- an unresolved document is a finding, not an
    omission.
    """
    docs = {d["id"]: d for d in store.documents(case_id)}
    links = store.q(
        "SELECT l.*, a.raw_name, a.raw_dob, a.raw_sex, a.raw_mrn "
        "FROM identity_links l "
        "JOIN identity_assertions a ON a.id = l.assertion_id "
        "WHERE l.case_id = ?", (case_id,))

    # Counts of evidence rows per patient, so the UI can show what each link
    # actually brought in rather than just how many documents attached.
    ev_by_doc: dict[str, dict] = {}
    src_doc = {s["id"]: s["document_id"]
               for s in store.rows("sources", case_id, order="id")}
    for table, key in (("facts", "facts"), ("claims", "claims"),
                       ("medications", "medications")):
        for r in store.rows(table, case_id):
            did = src_doc.get(r.get("source_id"))
            if did:
                ev_by_doc.setdefault(did, {}).setdefault(key, 0)
                ev_by_doc[did][key] += 1

    by_patient: dict[str, dict] = {}
    review: list[dict] = []
    for lk in links:
        doc = docs.get(lk["document_id"], {})
        entry = {
            "document_id": lk["document_id"],
            "filename": doc.get("filename"),
            "doc_type": doc.get("doc_type"),
            "doc_date": doc.get("doc_date"),
            "status": lk["status"],
            "basis": lk["basis"],
            "rationale": lk["rationale"],
            "asserted": {"name": lk["raw_name"], "dob": lk["raw_dob"],
                         "sex": lk["raw_sex"], "mrn": lk["raw_mrn"]},
            "evidence": ev_by_doc.get(lk["document_id"], {}),
        }
        if lk["patient_id"]:
            by_patient.setdefault(lk["patient_id"], []).append(entry)
        else:
            # This query is raw SQL, so the JSON column has not been decoded
            # for us the way store.rows() would.
            # Raw SQL, so the JSON column is undecoded; and "no candidates"
            # is stored as JSON null, which decodes to None rather than [].
            cand = lk["candidates"]
            if isinstance(cand, str):
                cand = json.loads(cand)
            entry["candidates"] = cand or []
            review.append(entry)

    out = []
    for pid, entries in by_patient.items():
        p = store.q1("SELECT * FROM patients WHERE id = ?", (pid,))
        if not p:
            continue
        enc = store.q(
            "SELECT e.id, e.occurred_on, i.display_name AS institution, "
            "COUNT(ed.document_id) AS documents "
            "FROM encounters e "
            "LEFT JOIN institutions i ON i.id = e.institution_id "
            "LEFT JOIN encounter_documents ed ON ed.encounter_id = e.id "
            "WHERE e.case_id = ? AND e.patient_id = ? "
            "GROUP BY e.id ORDER BY e.occurred_on", (case_id, pid))
        totals = {"facts": 0, "claims": 0, "medications": 0}
        for e in entries:
            for k in totals:
                totals[k] += e["evidence"].get(k, 0)
        out.append({
            "patient": {k: p[k] for k in
                        ("id", "patient_ref", "display_name", "dob", "sex",
                         "mrn", "is_synthetic")},
            "documents": sorted(entries, key=lambda e: e["doc_date"] or ""),
            "encounters": enc,
            "evidence_totals": totals,
        })
    out.sort(key=lambda r: r["patient"]["patient_ref"])

    return {
        "patients": out,
        "review_queue": sorted(review, key=lambda e: e["filename"] or ""),
        "summary": {
            "patients": len(out),
            "linked_documents": sum(len(p["documents"]) for p in out),
            "needs_review": len(review),
            "institutions": store.q1(
                "SELECT COUNT(*) AS n FROM institutions")["n"],
            # Per case: a global count would include clinicians from every
            # other case ever processed.
            "clinicians": store.q1(
                "SELECT COUNT(DISTINCT p.clinician_id) AS n "
                "FROM document_participants p JOIN documents d "
                "ON d.id = p.document_id WHERE d.case_id = ?",
                (case_id,))["n"],
        },
        # One clinician is one row, with their documented roles collected into
        # a list. Grouping by role as well split the same person across the
        # laboratory that ran their order and the clinic where they wrote the
        # note, and made the care team look larger than it is.
        "care_team": store.q(
            "SELECT c.display_name, i.display_name AS institution, "
            "GROUP_CONCAT(DISTINCT p.role) AS roles, "
            "COUNT(DISTINCT p.document_id) AS documents "
            "FROM document_participants p "
            "JOIN clinicians c ON c.id = p.clinician_id "
            "LEFT JOIN institutions i ON i.id = c.institution_id "
            "JOIN documents d ON d.id = p.document_id "
            "WHERE d.case_id = ? "
            "GROUP BY c.id ORDER BY documents DESC, c.display_name",
            (case_id,)),
    }
