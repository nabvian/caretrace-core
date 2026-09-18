"""Bulk ingestion: the properties the benchmark's prose asserts.

Every claim tested here was, until this module existed, only a sentence in
bulk_benchmark.md: that a corrupt file becomes a recorded failure rather than a
dead batch, that an interrupted run resumes without duplicating rows, that
byte-identical resubmissions are recognised, and that an unsupported extension
is a stated reason rather than a silent skip. A benchmark measures speed; it
does not defend behaviour.
"""
from __future__ import annotations

import pytest

from caretrace.core import bulk as B
from caretrace.core import models as M
from caretrace.core.store import Store
from caretrace.demo.synth_corpus import generate


@pytest.fixture
def case():
    store = Store()
    c = store.insert(M.Case(case_ref="CT-BULK-001",
                            subject_label="synthetic cohort"))
    store.commit()
    return store, c.id


@pytest.fixture
def corpus(tmp_path):
    d = tmp_path / "corpus"
    generate(d, count=120, patients=12)
    return d


# --------------------------------------------------------------------------- #
# Discovery
# --------------------------------------------------------------------------- #

def test_discover_admits_unsupported_extensions(tmp_path):
    """An unsupported file must reach the parser to be *recorded* as failed.

    Silently dropping it at discovery was the original behaviour and it
    contradicted the module's own docstring: the count of files found no longer
    matched the count of files accounted for.
    """
    (tmp_path / "a.txt").write_text("Hemoglobin: 9.2 g/dL")
    (tmp_path / "b.xyz").write_text("something unparseable")
    found = {p.name for p in B.discover(tmp_path)}
    assert found == {"a.txt", "b.xyz"}


def test_discover_excludes_filesystem_noise(tmp_path):
    (tmp_path / "real.txt").write_text("Hb 9.2")
    (tmp_path / ".DS_Store").write_bytes(b"\x00\x01")
    (tmp_path / "Thumbs.db").write_bytes(b"\x00")
    assert {p.name for p in B.discover(tmp_path)} == {"real.txt"}


# --------------------------------------------------------------------------- #
# Accounting: every discovered file reaches a terminal state
# --------------------------------------------------------------------------- #

def test_every_file_accounted_for(case, corpus):
    store, case_id = case
    job = B.plan_job(store, case_id, corpus)
    res = B.run_job(store, job.id)
    assert res["ingested"] + res["duplicate"] + res["failed"] == job.total
    assert job.total == len(B.discover(corpus))


def test_corrupt_file_is_recorded_not_fatal(case, tmp_path):
    """A file claiming to be a PDF and failing to parse must not end the batch."""
    store, case_id = case
    d = tmp_path / "mixed"
    d.mkdir()
    (d / "good.txt").write_text("Hemoglobin: 9.2 g/dL\nPatient: A Patient")
    (d / "broken.pdf").write_bytes(b"%PDF-1.4 truncated garbage")
    job = B.plan_job(store, case_id, d)
    res = B.run_job(store, job.id)

    assert res["ingested"] == 1
    assert res["failed"] == 1
    fails = B.failed_items(store, job.id)
    assert len(fails) == 1
    assert fails[0]["path"].endswith("broken.pdf")
    # The parser's own reason, not a generic message we invented.
    assert fails[0]["error"]


def test_duplicate_resubmission_is_flagged(case, tmp_path):
    store, case_id = case
    d = tmp_path / "dupes"
    d.mkdir()
    body = "Hemoglobin: 10.4 g/dL\nPatient: A Patient\nMRN: 55512"
    (d / "first.txt").write_text(body)
    (d / "second.txt").write_text(body)          # byte-identical
    job = B.plan_job(store, case_id, d)
    res = B.run_job(store, job.id)
    assert (res["ingested"], res["duplicate"]) == (1, 1)


# --------------------------------------------------------------------------- #
# Resumability
# --------------------------------------------------------------------------- #

def test_interrupted_run_resumes_without_duplicating(case, corpus):
    """Terminal status and document rows commit together, so a partial run
    leaves no half-ingested file and the remainder is exactly what is left.

    The resume granularity is the chunk, not the file: progress is reported and
    committed once per chunk, so a job must be planned with a chunk smaller
    than the corpus for an interruption to land mid-run at all. Planning with
    the default 200-file chunk over a 120-file corpus gives exactly one chunk
    and nothing to resume.
    """
    store, case_id = case
    job = B.plan_job(store, case_id, corpus, chunk_size=25)

    class Stop(Exception):
        pass

    def bail(p):
        # The callback payload carries running counts, not a total; sum them.
        if p["ingested"] + p["duplicate"] + p["failed"] >= 50:
            raise Stop

    with pytest.raises(Stop):
        B.run_job(store, job.id, progress=bail)

    part = B.job_progress(store, job.id)
    assert 0 < part["processed"] < job.total
    assert part["pending"] == job.total - part["processed"]

    assert _doc_count(store, case_id) == part["ingested"]

    res = B.run_job(store, job.id)          # resume
    final = B.job_progress(store, job.id)
    assert final["processed"] == job.total
    assert final["pending"] == 0
    # The resumed run touched only the remainder.
    assert (res["ingested"] + res["duplicate"] + res["failed"]
            == job.total - part["processed"])
    # No file processed twice: documents never exceed the ingested tally.
    assert _doc_count(store, case_id) == final["ingested"]


def test_progress_is_readable_mid_run(case, corpus):
    """Progress polls must not be blocked by the batch's write transaction."""
    store, case_id = case
    job = B.plan_job(store, case_id, corpus)
    seen = []

    def poll(p):
        seen.append(B.job_progress(store, job.id)["processed"])

    B.run_job(store, job.id, progress=poll)
    assert seen and seen == sorted(seen)
    assert seen[-1] == job.total


def _doc_count(store: Store, case_id: str) -> int:
    row = store.conn.execute(
        "SELECT COUNT(*) FROM documents WHERE case_id = ?", (case_id,)
    ).fetchone()
    return row[0]


# --------------------------------------------------------------------------- #
# HTTP surface
# --------------------------------------------------------------------------- #

@pytest.fixture
def client(tmp_path):
    from fastapi.testclient import TestClient
    from caretrace.api import app as A
    A.DATA_DIR = tmp_path
    A.UPLOAD_DIR = tmp_path / "uploads"
    A._store = Store(tmp_path / "caretrace.db")
    return TestClient(A.app)


@pytest.fixture
def api_case(client):
    r = client.post("/api/cases", json={"case_ref": "CT-BULK-API",
                                        "subject_label": "synthetic cohort"})
    assert r.status_code == 201, r.text
    # POST /api/cases returns the case row itself, not a {"case": ...} wrapper.
    return r.json()["id"]


def test_bulk_endpoint_reports_failures_with_the_job(client, api_case, tmp_path):
    """A batch that silently dropped files is the failure mode to avoid, so the
    failure list arrives with the job rather than behind a second call."""
    d = tmp_path / "api_corpus"
    d.mkdir()
    (d / "ok.txt").write_text("Hemoglobin: 9.2 g/dL\nPatient: A Patient")
    (d / "bad.pdf").write_bytes(b"%PDF-1.4 not really")

    r = client.post(f"/api/cases/{api_case}/ingest/bulk",
                    params={"source": str(d), "wait": True})
    assert r.status_code == 202, r.text
    job = r.json()["job"]
    assert job["total"] == 2
    assert job["processed"] == 2
    assert job["pending"] == 0

    got = client.get(f"/api/ingest/jobs/{job['job_id']}").json()
    assert got["failed"] == 1
    assert len(got["failures"]) == 1
    assert got["failures"][0]["path"].endswith("bad.pdf")

    listed = client.get(f"/api/cases/{api_case}/ingest/jobs").json()["jobs"]
    assert [j["id"] for j in listed] == [job["job_id"]]


def test_missing_source_is_rejected_not_recorded(client, api_case):
    r = client.post(f"/api/cases/{api_case}/ingest/bulk",
                    params={"source": "/nonexistent/path", "wait": True})
    assert r.status_code == 400
    assert client.get(f"/api/cases/{api_case}/ingest/jobs").json()["jobs"] == []


def test_unknown_job_is_404(client):
    assert client.get("/api/ingest/jobs/not-a-job").status_code == 404
