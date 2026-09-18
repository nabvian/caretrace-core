"""SQLite persistence for CARETRACE. Pure stdlib, no ORM.

The store knows how to write and read domain records. It contains no audit
logic — all comparison/detection lives in core/engine.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import fields as dc_fields
from pathlib import Path
from typing import Any, Iterable, Optional

from . import models as M

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

# Columns that are stored as JSON text but live as lists/dicts on the dataclass.
_JSON_FIELDS = {
    "evidence_gaps": {"evidence_located", "evidence_not_located"},
    "conflicts": {"left_member_ids", "right_member_ids"},
    "processing_runs": {"stages"},
    "identity_links": {"candidates"},
}

_TABLE_FOR = {
    M.Case: "cases",
    M.Document: "documents",
    M.DocumentPage: "document_pages",
    M.RawExtraction: "raw_extractions",
    M.Source: "sources",
    M.Fact: "facts",
    M.Claim: "claims",
    M.Medication: "medications",
    M.Event: "events",
    M.DocumentReference: "document_references",
    M.Relationship: "relationships",
    M.Conflict: "conflicts",
    M.EvidenceGap: "evidence_gaps",
    M.Change: "changes",
    M.ProcessingRun: "processing_runs",
    M.Coding: "codings",
    M.TerminologyCacheEntry: "terminology_cache",
    M.Patient: "patients",
    M.IdentityAssertionRow: "identity_assertions",
    M.IdentityLink: "identity_links",
    M.Institution: "institutions",
    M.Clinician: "clinicians",
    M.DocumentParticipant: "document_participants",
    M.Encounter: "encounters",
    M.IngestJob: "ingest_jobs",
    M.IngestItem: "ingest_items",
}


class Store:
    def __init__(self, db_path: str | Path = ":memory:"):
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        if self.db_path != ":memory:":
            # WAL lets readers (a progress poll, the API) proceed while a bulk
            # ingestion holds a write transaction. Without it a 10,000-file
            # batch blocks every read for the duration of each chunk.
            # NORMAL synchronous is the right trade for a derived store: a
            # power-loss window costs the tail of one chunk, which the job's
            # PENDING items make recoverable by re-running.
            self.conn.execute("PRAGMA journal_mode = WAL")
            self.conn.execute("PRAGMA synchronous = NORMAL")
        self.init_schema()

    def init_schema(self) -> None:
        self.conn.executescript(SCHEMA_PATH.read_text())
        self._migrate()
        self.conn.commit()

    # --------------------------------------------------------------- migrations
    # schema.sql is written with CREATE TABLE IF NOT EXISTS, which means an
    # existing database keeps whatever shape it was first created with. Anything
    # that changes an EXISTING table therefore needs a migration here; a new
    # table needs none. Each migration must be idempotent and safe to run on a
    # database that never had the defect.

    def _migrate(self) -> None:
        for name, fn in (("codings_cascade", self._migrate_codings_cascade),):
            try:
                fn()
            except sqlite3.Error as e:  # pragma: no cover - defensive
                raise RuntimeError(f"migration {name} failed: {e}") from e

    def _table_sql(self, table: str) -> str:
        row = self.conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (table,)).fetchone()
        return (row["sql"] or "") if row else ""

    def _migrate_codings_cascade(self) -> None:
        """Give `codings.case_id` ON DELETE CASCADE.

        The table shipped without it, which made a case containing codings
        undeletable — the FK blocked the parent delete. Deletion is a stated
        requirement, so this rebuilds the table in place. SQLite cannot alter a
        constraint, hence copy/drop/rename.
        """
        sql = self._table_sql("codings")
        if not sql or "ON DELETE CASCADE" in sql:
            return
        self.conn.executescript("""
            PRAGMA foreign_keys = OFF;
            ALTER TABLE codings RENAME TO codings_pre_cascade;
        """)
        # Recreate from the current schema, then copy the rows across.
        self.conn.executescript(SCHEMA_PATH.read_text())
        cols = [r["name"] for r in
                self.conn.execute("PRAGMA table_info(codings_pre_cascade)")]
        keep = [c for c in cols
                if c in {r["name"] for r in
                         self.conn.execute("PRAGMA table_info(codings)")}]
        collist = ", ".join(keep)
        self.conn.execute(
            f"INSERT INTO codings ({collist}) SELECT {collist} "
            f"FROM codings_pre_cascade")
        self.conn.executescript("""
            DROP TABLE codings_pre_cascade;
            PRAGMA foreign_keys = ON;
        """)
        self.conn.commit()

    # ---------------------------------------------------------------- writes
    def insert(self, obj: Any) -> Any:
        table = _TABLE_FOR[type(obj)]
        row = {}
        for f in dc_fields(obj):
            val = getattr(obj, f.name)
            if f.name in _JSON_FIELDS.get(table, set()):
                val = json.dumps(val)
            elif isinstance(val, bool):
                val = int(val)
            row[f.name] = val
        cols = ", ".join(row)
        marks = ", ".join("?" for _ in row)
        self.conn.execute(
            f"INSERT INTO {table} ({cols}) VALUES ({marks})", list(row.values())
        )
        return obj

    def insert_many(self, objs: Iterable[Any]) -> list[Any]:
        out = [self.insert(o) for o in objs]
        self.commit()
        return out

    def update(self, table: str, row_id: str, **values: Any) -> None:
        if not values:
            return
        payload = {}
        for k, v in values.items():
            if k in _JSON_FIELDS.get(table, set()):
                v = json.dumps(v)
            elif isinstance(v, bool):
                v = int(v)
            payload[k] = v
        sets = ", ".join(f"{k} = ?" for k in payload)
        self.conn.execute(
            f"UPDATE {table} SET {sets} WHERE id = ?", [*payload.values(), row_id]
        )
        self.conn.commit()

    def commit(self) -> None:
        self.conn.commit()

    def delete_case(self, case_id: str) -> None:
        # ON DELETE CASCADE handles the dependents.
        self.conn.execute("DELETE FROM cases WHERE id = ?", (case_id,))
        self.conn.commit()

    def clear_derived(self, case_id: str) -> None:
        """Remove everything a processing run produces, keeping documents/pages.

        The registry itself (patients, institutions, clinicians) is NOT cleared:
        those rows span cases and outlive a run, and dropping them would make
        cross-case identity resolution impossible. The per-run *decisions* about
        them -- assertions, links, encounters -- are cleared, because they are
        derived from documents exactly like facts are.

        `codings` belongs here: a coding names the fact/medication/claim row it
        annotates, and those ids are regenerated on every run, so keeping old
        codings would both double the count and leave rows pointing at deleted
        subjects. `terminology_cache` is deliberately NOT cleared -- it is a
        durable memo of what providers answered for a phrase, not per-case
        state, and dropping it would force needless network calls.
        """
        for table in ("encounters", "identity_links", "identity_assertions",
                      "codings", "relationships", "conflicts", "evidence_gaps",
                      "changes", "document_references", "events", "medications",
                      "claims", "facts", "sources", "processing_runs"):
            self.conn.execute(f"DELETE FROM {table} WHERE case_id = ?", (case_id,))
        self.conn.execute(
            "UPDATE documents SET processing_status='PENDING', processing_note=NULL "
            "WHERE case_id = ?", (case_id,))
        self.conn.commit()

    # ----------------------------------------------------------------- reads
    def q(self, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
        cur = self.conn.execute(sql, tuple(params))
        rows = [dict(r) for r in cur.fetchall()]
        return rows

    def q1(self, sql: str, params: Iterable[Any] = ()) -> Optional[dict[str, Any]]:
        rows = self.q(sql, params)
        return rows[0] if rows else None

    def rows(self, table: str, case_id: str, order: str = "created_at") -> list[dict]:
        out = self.q(f"SELECT * FROM {table} WHERE case_id = ? ORDER BY {order}",
                     (case_id,))
        json_cols = _JSON_FIELDS.get(table, set())
        if json_cols:
            for r in out:
                for c in json_cols:
                    if isinstance(r.get(c), str):
                        r[c] = json.loads(r[c])
        return out

    def cases(self) -> list[dict]:
        """Case rows with the counts the case list needs, in one query.

        `processed` reflects a COMPLETE run, not merely the presence of
        derived rows -- consistent with the case summary.
        """
        return self.q("""
            SELECT c.*,
                   (SELECT COUNT(*) FROM documents d WHERE d.case_id = c.id)
                       AS document_count,
                   (SELECT COUNT(*) FROM conflicts x WHERE x.case_id = c.id)
                       AS conflict_count,
                   (SELECT COUNT(*) FROM evidence_gaps g WHERE g.case_id = c.id)
                       AS gap_count,
                   EXISTS(SELECT 1 FROM processing_runs r
                          WHERE r.case_id = c.id AND r.status = 'COMPLETE')
                       AS processed
            FROM cases c ORDER BY c.created_at DESC""")

    def case(self, case_id: str) -> Optional[dict]:
        return self.q1("SELECT * FROM cases WHERE id = ? OR case_ref = ?",
                       (case_id, case_id))

    def documents(self, case_id: str) -> list[dict]:
        return self.q(
            "SELECT * FROM documents WHERE case_id = ? ORDER BY ordinal, filename",
            (case_id,))

    def pages(self, document_id: str) -> list[dict]:
        return self.q(
            "SELECT * FROM document_pages WHERE document_id = ? ORDER BY page_number",
            (document_id,))

    def source(self, source_id: str) -> Optional[dict]:
        return self.q1(
            """SELECT s.*, d.filename, d.doc_type, d.id AS doc_id, p.text AS page_text
                 FROM sources s
                 JOIN documents d ON d.id = s.document_id
                 JOIN document_pages p ON p.id = s.page_id
                WHERE s.id = ?""", (source_id,))

    def sources_map(self, case_id: str) -> dict[str, dict]:
        rows = self.q(
            """SELECT s.*, d.filename, d.doc_type, p.text AS page_text
                 FROM sources s
                 JOIN documents d ON d.id = s.document_id
                 JOIN document_pages p ON p.id = s.page_id
                WHERE s.case_id = ?""", (case_id,))
        return {r["id"]: r for r in rows}

    def latest_run(self, case_id: str) -> Optional[dict]:
        row = self.q1(
            "SELECT * FROM processing_runs WHERE case_id = ? "
            "ORDER BY started_at DESC LIMIT 1", (case_id,))
        if row and isinstance(row.get("stages"), str):
            row["stages"] = json.loads(row["stages"])
        return row

    def finish_run(self, run_id: str, stages: list[dict],
                   status: str = "COMPLETE") -> None:
        self.conn.execute(
            "UPDATE processing_runs SET stages = ?, status = ?, finished_at = ? "
            "WHERE id = ?",
            (json.dumps(stages), status, M.now_iso(), run_id))
        self.conn.commit()

    def count(self, table: str, case_id: str) -> int:
        row = self.q1(f"SELECT COUNT(*) AS n FROM {table} WHERE case_id = ?",
                      (case_id,))
        return int(row["n"]) if row else 0
