"""API tests.

The contract these pin down is the product promise expressed as HTTP: every
finding a route returns must arrive with the document, page and source text it
came from, and no route may return a resolution to a conflict.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from caretrace.api import app as A
from caretrace.core.store import Store


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("api")
    A.DATA_DIR = tmp
    A.UPLOAD_DIR = tmp / "uploads"
    A._store = Store(tmp / "caretrace.db")
    return TestClient(A.app)


@pytest.fixture(scope="module")
def case_id(client):
    r = client.post("/api/demo")
    assert r.status_code == 201
    cid = r.json()["case"]["id"]
    assert client.post(f"/api/cases/{cid}/process").status_code == 200
    return cid


def test_health_and_meta_carry_the_disclaimer(client):
    assert "research/prototype" in client.get("/api/health").json()["disclaimer"]
    meta = client.get("/api/meta").json()
    assert "not" in meta["disclaimer"].lower()
    assert len(meta["concepts"]) >= 12


def test_demo_case_is_flagged_synthetic(client, case_id):
    case = client.get(f"/api/cases/{case_id}").json()["case"]
    assert case["is_synthetic"] in (1, True)
    assert "synthetic" in case["subject_label"].lower()


def test_pipeline_stages_are_reported(client, case_id):
    stages = client.post(f"/api/cases/{case_id}/process").json()["stages"]
    names = [s["stage"] for s in stages]
    for expected in ("INGEST", "CLASSIFY", "EXTRACT", "NORMALIZE", "CREATE_FACTS",
                     "DETECT_CHANGES", "DETECT_CONFLICTS", "DETECT_GAPS",
                     "GENERATE_AUDIT"):
        assert expected in names


def test_every_fact_arrives_with_provenance(client, case_id):
    for f in client.get(f"/api/cases/{case_id}/facts").json():
        p = f["provenance"]
        assert p and p["filename"] and p["page"] >= 1 and p["source_text"].strip()


def test_conflicts_expose_both_sides_and_no_resolution(client, case_id):
    conflicts = client.get(f"/api/cases/{case_id}/conflicts").json()
    assert conflicts
    for c in conflicts:
        assert c["status"] == "UNRESOLVED"
        assert c["left"]["label"] and c["right"]["label"]
        assert "resolution" not in c
        for side in ("left_members", "right_members"):
            for m in c[side]:
                assert m["provenance"] or m["type"] == "document"


def test_conflict_members_cite_distinct_documents(client, case_id):
    hb = [c for c in client.get(f"/api/cases/{case_id}/conflicts").json()
          if c["concept"] == "hemoglobin"]
    assert len(hb) == 1
    files = {m["provenance"]["filename"]
             for m in hb[0]["left_members"] + hb[0]["right_members"]
             if m.get("provenance")}
    assert len(files) >= 2


def test_evidence_gaps_do_not_assert_falsehood(client, case_id):
    for g in client.get(f"/api/cases/{case_id}/evidence-gaps").json():
        blob = f"{g['title']} {g['basis']} {g['status']}".lower()
        for banned in ("false", "incorrect", "wrong", "disproven", "untrue"):
            assert banned not in blob


def test_timeline_entries_link_to_a_source(client, case_id):
    days = client.get(f"/api/cases/{case_id}/timeline").json()
    assert days
    for day in days:
        for e in day["entries"]:
            assert e["provenance"]["filename"]
    dates = [d["date"] for d in days]
    assert dates == sorted(dates)


def test_graph_edges_reference_existing_nodes(client, case_id):
    g = client.get(f"/api/cases/{case_id}/graph").json()
    ids = {n["id"] for n in g["nodes"]}
    assert g["nodes"] and g["edges"]
    for e in g["edges"]:
        assert e["source"] in ids and e["target"] in ids
    assert any(e["rel_type"] == "CONTRADICTS" for e in g["edges"])


def test_source_endpoint_returns_page_text(client, case_id):
    f = client.get(f"/api/cases/{case_id}/facts").json()[0]
    s = client.get(f"/api/sources/{f['provenance']['source_id']}").json()
    assert s["source"]["source_text"] in s["page_text"]
    assert s["document"]["filename"] == s["source"]["filename"]


def test_brief_metrics_match_the_endpoints(client, case_id):
    brief = client.get(f"/api/cases/{case_id}/brief").json()
    m = brief["metrics"]
    assert m["conflicts"] == len(client.get(f"/api/cases/{case_id}/conflicts").json())
    assert m["evidence_gaps"] == len(
        client.get(f"/api/cases/{case_id}/evidence-gaps").json())
    assert m["facts"] == len(client.get(f"/api/cases/{case_id}/facts").json())
    assert brief["source_index"]
    assert "not been clinically validated" in brief["disclaimer"]


def test_unknown_ids_return_404(client):
    assert client.get("/api/cases/nope").status_code == 404
    assert client.get("/api/sources/nope").status_code == 404
    assert client.get("/api/documents/nope").status_code == 404


def test_unsupported_upload_is_rejected_with_a_reason(client, case_id):
    r = client.post(f"/api/cases/{case_id}/documents",
                    files={"files": ("notes.exe", b"binary", "application/octet-stream")})
    assert r.json()["rejected"][0]["reason"]
    assert r.json()["accepted"] == []


def test_processing_an_empty_case_is_a_client_error(client):
    cid = client.post("/api/cases", json={"case_ref": "EMPTY-1"}).json()["id"]
    assert client.post(f"/api/cases/{cid}/process").status_code == 400


def test_uploaded_document_is_audited_like_the_demo(client, tmp_path):
    """An uploaded file must travel the same path as the demo corpus."""
    cid = client.post("/api/cases", json={"case_ref": "UP-1"}).json()["id"]
    from caretrace.demo.render_pdfs import render_all
    out = tmp_path / "pdfs"
    paths = render_all(out)
    files = [("files", (p.name, p.read_bytes(), "application/pdf"))
             for p in paths if p.name in ("07_CBC_Jun.pdf",
                                          "08_Discharge_Summary_Jun.pdf")]
    r = client.post(f"/api/cases/{cid}/documents", files=files)
    assert len(r.json()["accepted"]) == 2
    client.post(f"/api/cases/{cid}/process")
    conflicts = client.get(f"/api/cases/{cid}/conflicts").json()
    assert any(c["concept"] == "hemoglobin" for c in conflicts), \
        "the Hb disagreement must be found from uploads alone"


def test_case_deletion_removes_everything(client):
    cid = client.post("/api/cases", json={"case_ref": "DEL-1"}).json()["id"]
    assert client.delete(f"/api/cases/{cid}").status_code == 204
    assert client.get(f"/api/cases/{cid}").status_code == 404


# ---------------------------------------------------------------- terminology
def test_provider_status_endpoint_explains_why_each_is_unusable(client):
    r = client.get("/api/terminology/providers")
    assert r.status_code == 200
    body = r.json()
    keys = {p["key"] for p in body["providers"]}
    assert {"rxnorm", "loinc", "snomed", "icd11"} <= keys
    for p in body["providers"]:
        assert p["state"] in ("ACTIVE", "UNLICENSED", "UNREACHABLE",
                              "DISABLED", "UNKNOWN")
        # Every non-active provider must say what it needs, so a user can act.
        if p["state"] == "UNLICENSED":
            assert p["licence"]["obtain_url"]
            assert p["licence"]["credential_fields"]
        assert p["detail"]
    # The screen must state that audit results do not depend on it.
    assert "audit results do not depend" in body["note"]


def test_the_config_endpoint_never_returns_a_secret(client, monkeypatch):
    monkeypatch.setenv("CARETRACE_LOINC_USERNAME", "alice")
    monkeypatch.setenv("CARETRACE_LOINC_PASSWORD", "hunter2")
    monkeypatch.setenv("CARETRACE_ICD_CLIENT_SECRET", "s3cret")
    body = client.get("/api/terminology/config").text
    assert "hunter2" not in body and "s3cret" not in body
    assert "<set>" in body
    # Variable names ARE returned: the screen must tell a user what to set.
    assert "CARETRACE_LOINC_PASSWORD" in body


def test_codings_endpoint_labels_annotations_as_advisory(client):
    cid = client.post("/api/demo").json()["case"]["id"]
    client.post(f"/api/cases/{cid}/process")
    body = client.get(f"/api/cases/{cid}/codings").json()
    assert "advisory" in body["note"]
    assert "No audit result depends on them" in body["note"]
    for c in body["codings"]:
        assert c["subject_type"] in ("fact", "medication", "claim")
        assert c["subject_display_id"] and c["queried_text"]
        # An approximate coding must never be flagged assertable.
        if c["match_kind"] == "APPROXIMATE":
            assert c["assertable"] == 0


# ------------------------------------------------- terminology admin routes ---

def test_providers_route_reports_kinds_and_uri(client):
    body = client.get("/api/terminology/providers").json()
    assert body["providers"]
    for p in body["providers"]:
        assert p["codes_kinds"], f"{p['key']} declares no codeable kinds"
        assert p["system_uri"]
    # The note must keep saying the audit does not depend on this screen.
    assert "audit results do not depend" in body["note"]


def test_config_route_masks_secret_fields(client, monkeypatch):
    monkeypatch.setenv("CARETRACE_LOINC_PASSWORD", "do-not-leak")
    body = client.get("/api/terminology/config").json()
    assert "do-not-leak" not in json.dumps(body)


def test_summary_reports_coding_count_separately_from_audit(client):
    """Codings are advisory: counted, but never mixed into audit metrics.

    Resolves the demo case rather than taking the module-scoped `case_id`:
    POST /api/demo resets by design, so any earlier test that reloads the demo
    invalidates that fixture's id. `reset=false` returns whichever demo case is
    currently live.
    """
    cid = client.post("/api/demo?reset=false").json()["case"]["id"]
    client.post(f"/api/cases/{cid}/process")
    m = client.get(f"/api/cases/{cid}").json()["metrics"]
    assert "codings" in m
    assert m["codings"] >= 0
    # The audit metrics stand on their own.
    assert m["conflicts"] > 0 and m["evidence_gaps"] > 0


def test_patients_endpoint_reports_the_review_queue_alongside_the_resolved(client):
    """A registry view that showed only successful links would hide exactly
    what a reviewer is there to see.

    Resolves the live demo case rather than taking the module-scoped fixture:
    POST /api/demo resets by design, so an earlier test that reloads the demo
    invalidates that id.
    """
    cid = client.post("/api/demo?reset=false").json()["case"]["id"]
    client.post(f"/api/cases/{cid}/process")
    r = client.get(f"/api/cases/{cid}/patients")
    assert r.status_code == 200
    body = r.json()
    for key in ("summary", "patients", "review_queue", "care_team"):
        assert key in body, f"missing {key}: {sorted(body)}"
    assert body["summary"]["patients"] >= 1
    # Every queued document must carry a reason a human can act on.
    for row in body["review_queue"]:
        assert row["basis"], row
        assert row["rationale"] and len(row["rationale"]) > 20, row
        assert isinstance(row["candidates"], list), row


def test_summary_counts_the_review_queue_so_the_nav_can_surface_it(client):
    cid = client.post("/api/demo?reset=false").json()["case"]["id"]
    client.post(f"/api/cases/{cid}/process")
    m = client.get(f"/api/cases/{cid}").json()["metrics"]
    for key in ("patients", "identity_review"):
        assert key in m, f"missing {key}: {sorted(m)}"
    q = client.get(f"/api/cases/{cid}/patients").json()
    assert m["identity_review"] == len(q["review_queue"])
    assert m["patients"] == q["summary"]["patients"]
