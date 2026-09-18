"""Multi-file upload contract.

The defect these pin down: two different files submitted in ONE batch under the
same filename used to resolve to a single path on disk, so the second silently
overwrote the first while both database rows survived. The source viewer would
then show the wrong document -- a provenance failure, which is the one class of
bug this product cannot tolerate.
"""
from __future__ import annotations

import pathlib

import pytest
from fastapi.testclient import TestClient

from caretrace.api import app as A
from caretrace.core.store import Store

PDFS = sorted((pathlib.Path(__file__).resolve().parents[1]
               / "caretrace" / "demo" / "pdfs").glob("*.pdf"))


@pytest.fixture()
def client(tmp_path):
    A.DATA_DIR = tmp_path
    A.UPLOAD_DIR = tmp_path / "uploads"
    A._store = Store(tmp_path / "caretrace.db")
    return TestClient(A.app)


@pytest.fixture()
def case_id(client):
    return client.post("/api/cases",
                       json={"title": "Upload", "patient_label": "P"}
                       ).json()["id"]


def _pdf(name, data):
    return ("files", (name, data, "application/pdf"))


def _uniq(i):
    """A genuinely distinct but still-valid PDF."""
    return PDFS[i % len(PDFS)].read_bytes() + b"\n%% uniq-%d\n" % i


def test_demo_pdfs_exist():
    assert len(PDFS) >= 12


def test_same_name_different_content_keeps_both_documents(client, case_id):
    a, b = PDFS[0].read_bytes(), PDFS[6].read_bytes()
    r = client.post(f"/api/cases/{case_id}/documents",
                    files=[_pdf("report.pdf", a), _pdf("report.pdf", b)])
    assert r.status_code == 201
    docs = client.get(f"/api/cases/{case_id}/documents").json()
    assert len(docs) == 2
    # Distinct content must land on distinct paths, or one overwrites the other.
    assert len({d["stored_path"] for d in docs}) == 2
    assert len({d["sha256"] for d in docs}) == 2
    # The operator's filename is preserved for display on both rows.
    assert [d["filename"] for d in docs] == ["report.pdf", "report.pdf"]
    # Each row's bytes on disk are its OWN bytes.
    sizes = {pathlib.Path(d["stored_path"]).stat().st_size for d in docs}
    assert sizes == {len(a), len(b)}


def test_identical_content_is_reported_as_duplicate_not_ingested_twice(
        client, case_id):
    a = PDFS[0].read_bytes()
    r = client.post(f"/api/cases/{case_id}/documents",
                    files=[_pdf("x.pdf", a), _pdf("y.pdf", a)]).json()
    assert r["accepted"] == ["x.pdf"]
    assert [d["filename"] for d in r["duplicates"]] == ["y.pdf"]
    assert r["duplicates"][0]["duplicate_of"] == "x.pdf"
    assert len(client.get(f"/api/cases/{case_id}/documents").json()) == 1


def test_duplicate_detection_spans_separate_batches(client, case_id):
    a = PDFS[1].read_bytes()
    client.post(f"/api/cases/{case_id}/documents", files=[_pdf("first.pdf", a)])
    r = client.post(f"/api/cases/{case_id}/documents",
                    files=[_pdf("again.pdf", a)]).json()
    assert r["accepted"] == []
    assert r["duplicates"][0]["duplicate_of"] == "first.pdf"


def test_one_bad_file_does_not_fail_the_batch(client, case_id):
    r = client.post(f"/api/cases/{case_id}/documents", files=[
        _pdf("good.pdf", PDFS[0].read_bytes()),
        ("files", ("bad.exe", b"MZ\x00", "application/octet-stream")),
        _pdf("empty.pdf", b""),
    ]).json()
    assert r["accepted"] == ["good.pdf"]
    reasons = {x["filename"]: x["reason"] for x in r["rejected"]}
    assert "Unsupported file type" in reasons["bad.exe"]
    assert "empty" in reasons["empty.pdf"].lower()


def test_large_batch_is_fully_ingested_with_contiguous_ordinals(
        client, case_id):
    n = 200
    files = [_pdf(f"rep_{i:03d}.pdf", _uniq(i)) for i in range(n)]
    r = client.post(f"/api/cases/{case_id}/documents", files=files).json()
    assert len(r["accepted"]) == n
    assert r["duplicates"] == [] and r["rejected"] == []
    docs = client.get(f"/api/cases/{case_id}/documents").json()
    assert len(docs) == n
    assert len({d["stored_path"] for d in docs}) == n
    assert sorted(d["ordinal"] for d in docs) == list(range(1, n + 1))
    # No partially-written staging files may survive a successful batch.
    assert not list((A.UPLOAD_DIR / case_id).glob(".incoming-*"))


def test_batch_upload_then_process_yields_findings(client, case_id):
    """The end-to-end promise: uploads alone (no demo shortcut) produce audit."""
    files = [_pdf(p.name, p.read_bytes()) for p in PDFS]
    client.post(f"/api/cases/{case_id}/documents", files=files)
    assert client.post(f"/api/cases/{case_id}/process").status_code == 200
    m = client.get(f"/api/cases/{case_id}").json()["metrics"]
    assert m["facts"] > 0 and m["conflicts"] > 0
