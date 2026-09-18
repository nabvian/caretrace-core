"""The immutable raw-text layer.

Contract: for every ingested document CARETRACE retains the complete parser
output verbatim, with the method and tool that produced it, and no later stage
may alter it. Every provenance claim in the product resolves to this layer, so
if it can drift the product's central promise is unenforceable.
"""
from __future__ import annotations

import json
import pathlib

import pytest
from fastapi.testclient import TestClient

from caretrace.api import app as A
from caretrace.core import models as M
from caretrace.core.store import Store


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("raw")
    A.DATA_DIR = tmp
    A.UPLOAD_DIR = tmp / "uploads"
    A._store = Store(tmp / "caretrace.db")
    return TestClient(A.app)


@pytest.fixture(scope="module")
def case_id(client):
    return client.post("/api/demo").json()["case"]["id"]


def _raws(case_id):
    return A._store.q(
        "SELECT r.*, d.filename, d.ordinal FROM raw_extractions r "
        "JOIN documents d ON d.id = r.document_id "
        "WHERE d.case_id = ? ORDER BY d.ordinal", (case_id,))


def test_every_document_has_exactly_one_raw_extraction(client, case_id):
    docs = client.get(f"/api/cases/{case_id}/documents").json()
    raws = _raws(case_id)
    assert len(raws) == len(docs) > 0
    assert len({r["document_id"] for r in raws}) == len(raws)


def test_method_and_tool_are_recorded_not_inferred(client, case_id):
    for r in _raws(case_id):
        assert r["method"] in {M.ExtractionMethod.PDF_TEXT_LAYER,
                               M.ExtractionMethod.PLAIN_TEXT,
                               M.ExtractionMethod.OCR,
                               M.ExtractionMethod.NONE}
        if r["method"] == M.ExtractionMethod.PDF_TEXT_LAYER:
            assert r["tool_name"] == "pypdf" and r["tool_version"]


def test_page_offsets_resolve_back_to_page_text_exactly(client, case_id):
    for r in _raws(case_id):
        offsets = json.loads(r["page_offsets"])
        pages = A._store.q(
            "SELECT text FROM document_pages WHERE document_id = ? "
            "ORDER BY page_number", (r["document_id"],))
        assert len(offsets) == len(pages)
        for (start, end), page in zip(offsets, pages):
            assert r["text"][start:end] == page["text"]


def test_checksum_matches_the_retained_text(client, case_id):
    import hashlib
    for r in _raws(case_id):
        assert hashlib.sha256(
            r["text"].encode("utf-8")).hexdigest() == r["text_sha256"]
        assert r["char_count"] == len(r["text"])


def test_sidecar_txt_is_written_and_identical(client, case_id):
    for r in _raws(case_id):
        assert r["sidecar_path"], "raw text must be retained as .txt on disk"
        assert pathlib.Path(
            r["sidecar_path"]).read_text(encoding="utf-8") == r["text"]


def test_processing_does_not_mutate_the_raw_layer(client, case_id):
    before = {r["document_id"]: (r["text_sha256"], r["id"])
              for r in _raws(case_id)}
    client.post(f"/api/cases/{case_id}/process")
    client.post(f"/api/cases/{case_id}/process")     # twice: reruns must not edit
    after = {r["document_id"]: (r["text_sha256"], r["id"])
             for r in _raws(case_id)}
    assert before == after


def test_route_serves_verbatim_text_with_provenance(client, case_id):
    doc = client.get(f"/api/cases/{case_id}/documents").json()[0]
    j = client.get(f"/api/documents/{doc['id']}/text").json()
    assert j["immutable"] is True
    assert j["method"] and j["char_count"] == len(j["text"])
    row = A._store.q1("SELECT * FROM raw_extractions WHERE document_id = ?",
                      (doc["id"],))
    assert j["text"] == row["text"]        # served, not re-parsed
    dl = client.get(f"/api/documents/{doc['id']}/text?download=true")
    assert dl.text == row["text"]
    assert ".txt" in dl.headers["content-disposition"]


def test_missing_text_layer_is_reported_not_faked(client, tmp_path):
    """An image with no OCR backend must not look like a clean extraction."""
    cid = client.post("/api/cases",
                      json={"title": "img", "patient_label": "P"}).json()["id"]
    png = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
    client.post(f"/api/cases/{cid}/documents",
                files=[("files", ("scan.png", png, "image/png"))])
    r = _raws(cid)[0]
    assert r["has_text_layer"] == 0
    assert r["method"] == M.ExtractionMethod.OCR
    assert r["text"].strip() == ""          # empty, never invented
    assert "invented" in (r["note"] or "").lower() or "No text layer" in (r["note"] or "")
