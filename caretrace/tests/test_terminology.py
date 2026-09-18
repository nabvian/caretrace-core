"""Terminology layer.

The property this file exists to defend: an audit result must be identical
whether every vocabulary provider is licensed and answering, or none of them
are. Terminology is advisory annotation, so the tests below use a scripted
transport rather than a live service -- a suite that needs the network to pass
cannot tell a broken adapter from a bad day at the far end.
"""
from __future__ import annotations

import json

import pytest

from caretrace.core import models as M
from caretrace.core import pipeline as P
from caretrace.core.store import Store
from caretrace.terminology.base import (Coding, HttpError, LicenceRequirement,
                                        MatchKind, ProviderState)
from caretrace.terminology.config import SECRET_FIELDS, TerminologyConfig
from caretrace.terminology.providers.icd11 import Icd11Provider
from caretrace.terminology.providers.loinc import LoincProvider
from caretrace.terminology.providers.rxnorm import RxNormProvider
from caretrace.terminology.providers.snomed import SnomedProvider
from caretrace.terminology.resolver import (KIND_MEDICATION, KIND_OBSERVATION,
                                            TerminologyResolver, norm_query)


class FakeTransport:
    """Serves scripted JSON by URL substring, and records what was asked."""

    def __init__(self, routes: dict, fail: set | None = None):
        self.routes = routes
        self.fail = fail or set()
        self.calls: list[str] = []

    def get_json(self, url, *, params=None, headers=None):
        full = url + ("?" + "&".join(f"{k}={v}" for k, v in (params or {}).items()))
        self.calls.append(full)
        for frag in self.fail:
            if frag in full:
                raise HttpError(f"scripted failure for {frag}", status=503)
        for frag, payload in self.routes.items():
            if frag in full:
                return payload, 4.2
        return {}, 1.0

    def post_form(self, url, form, headers=None):
        self.calls.append(url)
        for frag, payload in self.routes.items():
            if frag in url:
                return payload, 3.0
        raise HttpError("no scripted token route")


RXNAV_ROUTES = {
    "rxcui.json?name=ferrous sulfate": {"idGroup": {"rxnormId": ["24947"]}},
    "rxcui/24947/properties.json": {"properties": {"name": "ferrous sulfate"}},
    "rxcui.json?name=Vitamin C": {"idGroup": {"rxnormId": ["1151"]}},
    "rxcui/1151/properties.json": {"properties": {"name": "ascorbic acid"}},
    "approximateTerm.json": {"approximateGroup": {"candidate": [
        {"rxcui": "24947", "score": "11.99", "name": "Ferrous sulphate"}]}},
    "version.json": {"version": "test-release"},
}


# --------------------------------------------------------------- match kinds
def test_an_approximate_match_is_never_assertable():
    """A fuzzy hit is a suggestion for a reviewer, not an identity claim."""
    c = Coding(system="RxNorm", system_uri="u", code="24947",
               display="ferrous sulfate", queried_text="ferous sulphate",
               match_kind=MatchKind.APPROXIMATE, score=11.99)
    assert c.assertable is False
    assert MatchKind.APPROXIMATE not in MatchKind.ASSERTABLE


def test_exact_and_synonym_matches_are_assertable():
    for kind in (MatchKind.EXACT, MatchKind.SYNONYM):
        c = Coding(system="LOINC", system_uri="u", code="718-7",
                   display="Hemoglobin [Mass/volume] in Blood",
                   queried_text="Hemoglobin", match_kind=kind)
        assert c.assertable is True


def test_an_unknown_match_kind_is_rejected():
    with pytest.raises(ValueError):
        Coding(system="X", system_uri="u", code="1", display="d",
               queried_text="t", match_kind="PROBABLY")


# ------------------------------------------------------------------- RxNorm
def test_rxnorm_exact_name_yields_an_assertable_coding():
    p = RxNormProvider(transport=FakeTransport(RXNAV_ROUTES))
    (c,) = p.lookup("ferrous sulfate", kind=KIND_MEDICATION)
    assert (c.code, c.match_kind, c.assertable) == ("24947", MatchKind.EXACT, True)


def test_rxnorm_reports_a_publisher_synonym_as_synonym_not_exact():
    """'Vitamin C' resolves to a code whose preferred term is ascorbic acid.

    That is a synonym match: still assertable, but the distinction is kept so a
    reviewer can see the wording differed from the publisher's own term.
    """
    p = RxNormProvider(transport=FakeTransport(RXNAV_ROUTES))
    (c,) = p.lookup("Vitamin C", kind=KIND_MEDICATION)
    assert c.display == "ascorbic acid"
    assert c.match_kind == MatchKind.SYNONYM and c.assertable is True


def test_rxnorm_misspelling_falls_back_to_a_non_assertable_candidate():
    p = RxNormProvider(transport=FakeTransport(RXNAV_ROUTES))
    (c,) = p.lookup("ferous sulphate", kind=KIND_MEDICATION)
    assert c.code == "24947"
    assert c.match_kind == MatchKind.APPROXIMATE and c.assertable is False
    assert c.score == pytest.approx(11.99)


def test_a_provider_returns_nothing_rather_than_raising_when_the_service_fails():
    """A terminology outage degrades annotation; it must never raise."""
    p = RxNormProvider(transport=FakeTransport(RXNAV_ROUTES, fail={"rxnav"}))
    assert list(p.lookup("ferrous sulfate", kind=KIND_MEDICATION)) == []
    assert p.health().state == ProviderState.UNREACHABLE


def test_a_provider_is_not_asked_for_a_kind_it_does_not_code():
    p = RxNormProvider(transport=FakeTransport(RXNAV_ROUTES))
    assert list(p.lookup("Hemoglobin", kind=KIND_OBSERVATION)) == []


# ------------------------------------------------- licence-gated providers
@pytest.mark.parametrize("provider", [LoincProvider(), SnomedProvider(),
                                      Icd11Provider()])
def test_an_unlicensed_provider_reports_unlicensed_and_codes_nothing(provider):
    """Distinguishable from 'searched and found nothing'.

    A reviewer must be able to tell "this phrase has no LOINC code" from "we
    are not licensed to look it up", so the state is UNLICENSED rather than a
    silent empty result.
    """
    h = provider.health()
    assert h.state == ProviderState.UNLICENSED
    assert h.licence.required is True
    assert h.licence.obtain_url and h.licence.credential_fields
    assert list(provider.lookup("hemoglobin")) == []


def test_snomed_stays_off_even_when_the_endpoint_is_reachable():
    """Reachability is not permission.

    The public SNOMED browser answers without credentials; using it as a
    backdoor would put an unlicensed user in breach, so the provider is off
    until a licence is affirmed in configuration.
    """
    routes = {"codesystems": {"items": [{"latestVersion": {"version": "20260101"}}]},
              "concepts": {"items": [{"conceptId": "38082009",
                                      "pt": {"term": "Hemoglobin"},
                                      "fsn": {"term": "Hemoglobin (substance)"}}]}}
    off = SnomedProvider(transport=FakeTransport(routes), enabled=False)
    assert off.health().state == ProviderState.UNLICENSED
    assert list(off.lookup("Hemoglobin")) == []

    on = SnomedProvider(transport=FakeTransport(routes), enabled=True)
    assert on.health().state == ProviderState.ACTIVE
    (c,) = on.lookup("Hemoglobin", kind=KIND_OBSERVATION, limit=1)
    assert (c.code, c.match_kind) == ("38082009", MatchKind.EXACT)


def test_a_licensed_loinc_lookup_marks_a_substring_hit_approximate():
    """The server filters by substring, so only an equal display is exact."""
    routes = {"$expand": {"expansion": {
        "parameter": [{"name": "version", "valueString": "2.77"}],
        "contains": [
            {"code": "718-7", "display": "Hemoglobin [Mass/volume] in Blood"},
            {"code": "30313-1", "display": "Hemoglobin"}]}}}
    p = LoincProvider(username="u", password="p",
                      transport=FakeTransport(routes))
    got = p.lookup("Hemoglobin", kind=KIND_OBSERVATION, limit=2)
    kinds = {c.code: (c.match_kind, c.assertable) for c in got}
    assert kinds["718-7"] == (MatchKind.APPROXIMATE, False)
    assert kinds["30313-1"] == (MatchKind.EXACT, True)
    assert all(c.version == "2.77" for c in got)


def test_rejected_credentials_report_unlicensed_not_unreachable():
    """A 401 is a licence problem, and saying 'unreachable' would misdirect."""
    p = LoincProvider(username="u", password="bad",
                      transport=FakeTransport({}, fail={"CodeSystem"}))
    # The scripted failure carries 503; a real rejection carries 401/403.
    assert p.health().state == ProviderState.UNREACHABLE

    class Rejecting(FakeTransport):
        def get_json(self, url, *, params=None, headers=None):
            raise HttpError("HTTP 401 from fhir.loinc.org", status=401)

    p2 = LoincProvider(username="u", password="bad", transport=Rejecting({}))
    h = p2.health()
    assert h.state == ProviderState.UNLICENSED and "credentials" in h.detail


def test_icd11_obtains_and_reuses_a_bearer_token():
    routes = {"connect/token": {"access_token": "tok", "expires_in": 3600},
              "release/11/2024-01/mms": {"releaseId": "2024-01"}}
    ft = FakeTransport(routes)
    p = Icd11Provider(client_id="i", client_secret="s", transport=ft)
    assert p.health().state == ProviderState.ACTIVE
    p.health()
    # One token request only: the second probe reuses the cached token.
    assert sum(1 for c in ft.calls if "connect/token" in c) == 1


def test_icd11_strips_markup_from_a_returned_title():
    routes = {"connect/token": {"access_token": "tok", "expires_in": 3600},
              "search": {"destinationEntities": [
                  {"theCode": "3A00.0", "title": "<em>Iron</em> deficiency anaemia",
                   "score": "0.87", "matchingPVs": []}]}}
    p = Icd11Provider(client_id="i", client_secret="s",
                      transport=FakeTransport(routes))
    (c,) = p.lookup("iron deficiency anaemia", kind="diagnosis_statement")
    assert c.display == "Iron deficiency anaemia"
    assert c.match_kind == MatchKind.APPROXIMATE


# ------------------------------------------------------------- configuration
def test_configuration_never_echoes_a_secret():
    cfg = TerminologyConfig.from_env({
        "CARETRACE_LOINC_USERNAME": "alice",
        "CARETRACE_LOINC_PASSWORD": "hunter2",
        "CARETRACE_ICD_CLIENT_SECRET": "s3cret",
        "CARETRACE_SNOMED_API_KEY": "k3y",
    })
    blob = json.dumps(cfg.redacted())
    for secret in ("hunter2", "s3cret", "k3y"):
        assert secret not in blob
    assert "alice" in blob            # a username is not a secret
    assert cfg.redacted()["loinc"]["password"] == "<set>"
    assert SECRET_FIELDS == {"password", "api_key", "client_secret"}


def test_snomed_licence_flag_is_read_as_a_boolean():
    on = TerminologyConfig.from_env({"CARETRACE_SNOMED_LICENCE_CONFIRMED": "1"})
    off = TerminologyConfig.from_env({"CARETRACE_SNOMED_LICENCE_CONFIRMED": "0"})
    assert on.snomed.get("enabled") is True
    assert off.snomed.get("enabled") is False


# ------------------------------------------------------------------ resolver
def test_query_normalization_is_case_and_punctuation_insensitive():
    assert norm_query("  Ferrous  Sulphate. ") == "ferrous sulphate"
    assert norm_query("Hb:") == "hb"


def build_case(store: Store) -> tuple[str, str]:
    """A case with one document, one page and one source to hang facts on."""
    case = store.insert(M.Case(case_ref="T-1", subject_label="Test (synthetic)",
                               is_synthetic=True))
    doc = store.insert(M.Document(case_id=case.id, filename="t.pdf",
                                  ordinal=1, doc_type=M.DocType.LAB_REPORT))
    page = store.insert(M.DocumentPage(document_id=doc.id, page_number=1,
                                       text="Hb: 9.2 g/dL"))
    src = store.insert(M.Source(case_id=case.id, document_id=doc.id,
                                page_id=page.id, page_number=1,
                                source_text="Hb: 9.2 g/dL"))
    store.commit()
    return case.id, src.id


def test_the_resolver_queries_the_pack_label_not_the_documents_abbreviation():
    """A CBC prints 'Hb'; no vocabulary lists that.

    The pack knows the published label, so that is what gets queried -- while
    the coding still records the document's own wording for provenance.
    """
    store = Store()
    cid, src_id = build_case(store)
    store.insert(M.Fact(case_id=cid, display_id="F-001", concept="hemoglobin",
                        surface_form="Hb", source_id=src_id,
                        evidence_type=M.EvidenceType.OBSERVATION,
                        value_num=9.2, unit="g/dL", obs_date="2026-01-18"))
    store.commit()

    routes = {"$expand": {"expansion": {"contains": [
        {"code": "718-7", "display": "Hemoglobin"}]}}}
    ft = FakeTransport(routes)
    res = TerminologyResolver(
        config=TerminologyConfig.from_env({}),
        providers=[LoincProvider(username="u", password="p", transport=ft)])
    report = res.resolve_case(store, cid)

    assert report.coded == 1
    assert any("filter=Hemoglobin" in c for c in ft.calls), ft.calls
    (row,) = store.rows("codings", cid)
    assert row["queried_text"] == "Hb"        # provenance keeps the wording
    assert row["code"] == "718-7"


def test_a_repeated_phrase_costs_one_provider_call():
    store = Store()
    cid, src_id = build_case(store)
    for i in range(3):
        store.insert(M.Medication(case_id=cid, display_id=f"M-00{i+1}",
                                  drug_name="ferrous sulfate",
                                  drug_norm="ferrous sulfate", source_id=src_id))
    store.commit()
    ft = FakeTransport(RXNAV_ROUTES)
    res = TerminologyResolver(config=TerminologyConfig.from_env({}),
                             providers=[RxNormProvider(transport=ft)])
    report = res.resolve_case(store, cid)
    assert report.coded == 3            # every medication is annotated
    assert report.provider_calls == 1   # but the phrase was looked up once
    assert report.cache_hits == 2


def test_a_miss_is_cached_but_an_unlicensed_lookup_is_not():
    """The distinction matters for a later licensed run.

    A searched-and-absent phrase should not be re-queried. A phrase that was
    never searched because no licence was held MUST be retried once one is.
    """
    store = Store()
    cid, src_id = build_case(store)
    store.insert(M.Medication(case_id=cid, display_id="M-001",
                              drug_name="zzznotadrug",
                              drug_norm="zzznotadrug", source_id=src_id))
    store.commit()

    res = TerminologyResolver(
        config=TerminologyConfig.from_env({}),
        providers=[RxNormProvider(transport=FakeTransport({})),
                   LoincProvider()])          # unlicensed
    res.resolve_case(store, cid)
    cached = store.q("SELECT provider_key, miss FROM terminology_cache")
    assert cached == [{"provider_key": "rxnorm", "miss": 1}]

    # Now licensed: the phrase LOINC never saw is looked up.
    routes = {"$expand": {"expansion": {"contains": []}}}
    ft = FakeTransport(routes)
    res2 = TerminologyResolver(
        config=TerminologyConfig.from_env({}),
        providers=[LoincProvider(username="u", password="p", transport=ft)])
    res2.resolve_case(store, cid)
    # Medications are not a LOINC kind, so nothing was queried -- but no stale
    # "unlicensed" cache row blocked it either.
    assert not any(r["provider_key"] == "loinc" and r["miss"] == 0
                   for r in store.q("SELECT provider_key, miss FROM terminology_cache"))


# ------------------------------------------------- the invariance the layer owes
AUDIT_KEYS = ("documents", "facts", "claims", "medications", "changes",
              "conflicts", "evidence_gaps", "relationships", "unresolved")


@pytest.fixture(scope="module")
def demo_pdfs(tmp_path_factory):
    from caretrace.demo.render_pdfs import render_all
    out = tmp_path_factory.mktemp("pdfs")
    render_all(out)
    return out


def audit(pdf_dir, **kw):
    from pathlib import Path
    store = Store()
    case = store.insert(M.Case(case_ref="CT-DEMO-001",
                               subject_label="Arjun Mehta (synthetic)",
                               is_synthetic=True))
    store.commit()
    for i, p in enumerate(sorted(Path(pdf_dir).glob("*.pdf")), start=1):
        P.ingest_document(store, case.id, p, i)
    store.commit()
    return store, case.id, P.process_case(store, case.id, **kw)


def test_the_audit_is_identical_with_and_without_terminology(demo_pdfs):
    """The core promise of this layer.

    Every audit count is computed before resolution runs, so a case audited
    with no provider at all must produce exactly the audit of a case with every
    provider answering. If this test ever fails, terminology has leaked into
    the evidence engine.
    """
    _, _, without = audit(demo_pdfs, resolve_terminology=False)

    routes = dict(RXNAV_ROUTES)
    routes["$expand"] = {"expansion": {"contains": [
        {"code": "718-7", "display": "Hemoglobin"}]}}
    providers = [RxNormProvider(transport=FakeTransport(routes)),
                 LoincProvider(username="u", password="p",
                               transport=FakeTransport(routes))]
    res = TerminologyResolver(config=TerminologyConfig.from_env({}),
                              providers=providers)
    store, cid, with_ = audit(demo_pdfs, resolver=res)

    assert {k: without.counts[k] for k in AUDIT_KEYS} == \
           {k: with_.counts[k] for k in AUDIT_KEYS}
    # And resolution did happen, so the equality above is not vacuous.
    assert with_.counts["codings"] > 0
    assert store.count("codings", cid) == with_.counts["codings"]


def test_a_total_terminology_failure_does_not_fail_the_run(demo_pdfs):
    """An annotation outage is reported in the stage log, not raised."""

    class Exploding:
        key, label, system, system_uri = "boom", "Boom", "Boom", "u"
        codes_kinds = ("medication", "observation", "diagnosis_statement")
        configured = True
        licence = LicenceRequirement(required=False)

        def health(self):
            raise RuntimeError("provider is on fire")

        def lookup(self, text, *, kind="any", limit=3):
            raise RuntimeError("provider is on fire")

    res = TerminologyResolver(config=TerminologyConfig.from_env({}),
                              providers=[Exploding()])
    _, _, result = audit(demo_pdfs, resolver=res)
    assert result.run.status == "COMPLETE"
    assert result.counts["conflicts"] > 0          # audit still complete
    assert result.counts["codings"] == 0
    (stage,) = [s for s in result.stages if s["stage"] == "RESOLVE_TERMINOLOGY"]
    assert "error" in stage


def test_reprocessing_does_not_accumulate_codings(demo_pdfs):
    """Codings are derived state, keyed to fact ids that a re-run regenerates.

    Without clearing them, a second run doubles the count and leaves rows
    pointing at deleted subjects.
    """
    res = TerminologyResolver(
        config=TerminologyConfig.from_env({}),
        providers=[RxNormProvider(transport=FakeTransport(RXNAV_ROUTES))])
    store, cid, first = audit(demo_pdfs, resolver=res)
    n_first = store.count("codings", cid)
    for _ in range(2):
        P.process_case(store, cid, resolver=res)
    assert store.count("codings", cid) == n_first
    orphans = store.q(
        "SELECT COUNT(*) n FROM codings WHERE subject_type='medication' "
        "AND subject_id NOT IN (SELECT id FROM medications)")[0]["n"]
    assert orphans == 0


def test_the_cache_survives_reprocessing_so_reruns_need_no_network(demo_pdfs):
    """The memo is durable; only per-case rows are rebuilt."""
    ft = FakeTransport(RXNAV_ROUTES)
    res = TerminologyResolver(config=TerminologyConfig.from_env({}),
                              providers=[RxNormProvider(transport=ft)])
    store, cid, _ = audit(demo_pdfs, resolver=res)
    calls_after_first = len(ft.calls)
    assert calls_after_first > 0
    result = P.process_case(store, cid, resolver=res)
    assert len(ft.calls) == calls_after_first          # nothing new was asked
    (stage,) = [s for s in result.stages if s["stage"] == "RESOLVE_TERMINOLOGY"]
    assert stage["provider_calls"] == 0 and stage["cache_hits"] > 0


def test_offline_mode_forbids_every_outbound_call(monkeypatch):
    """A deployment can bar egress entirely; resolution then serves cache only."""
    from caretrace.terminology import transport as T
    monkeypatch.setenv(T.OFFLINE_ENV, "1")
    assert T.offline() is True
    p = RxNormProvider(transport=T.Transport())
    assert list(p.lookup("ferrous sulfate", kind=KIND_MEDICATION)) == []
    h = p.health()
    assert h.state == ProviderState.UNREACHABLE and "offline" in h.detail


# ------------------------------------------------------------------- deletion
def test_deleting_a_case_deletes_its_codings(demo_pdfs):
    """The deletion guarantee covers annotations too.

    `codings` originally shipped without ON DELETE CASCADE, which made any
    audited case undeletable — the foreign key blocked the parent row. Since
    deletion is a stated requirement, this pins the cascade.
    """
    res = TerminologyResolver(
        config=TerminologyConfig.from_env({}),
        providers=[RxNormProvider(transport=FakeTransport(RXNAV_ROUTES))])
    store, cid, _ = audit(demo_pdfs, resolver=res)
    assert store.count("codings", cid) > 0
    store.delete_case(cid)
    store.commit()
    assert store.q("SELECT COUNT(*) n FROM codings")[0]["n"] == 0
    assert store.q("SELECT COUNT(*) n FROM facts")[0]["n"] == 0


def test_the_cascade_migration_repairs_an_existing_database(tmp_path):
    """An old database must be upgraded in place, not left broken.

    schema.sql uses CREATE TABLE IF NOT EXISTS, so a database created before
    the fix keeps the un-cascaded table forever unless a migration runs.
    """
    import sqlite3

    from caretrace.core.store import Store as S
    db = tmp_path / "old.db"
    s = S(db)
    # Reproduce the pre-fix shape, with a row in it.
    s.conn.executescript("""
        PRAGMA foreign_keys = OFF;
        DROP TABLE codings;
        CREATE TABLE codings (
            id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL REFERENCES cases(id),
            subject_type TEXT NOT NULL, subject_id TEXT NOT NULL,
            system TEXT NOT NULL, system_uri TEXT, code TEXT NOT NULL,
            display TEXT, queried_text TEXT NOT NULL, match_kind TEXT NOT NULL,
            assertable INTEGER NOT NULL DEFAULT 0, score REAL, version TEXT,
            provider_key TEXT NOT NULL, resolved_at TEXT, created_at TEXT NOT NULL
        );
    """)
    case = s.insert(M.Case(case_ref="OLD", subject_label="x", is_synthetic=True))
    s.conn.execute(
        "INSERT INTO codings (id, case_id, subject_type, subject_id, system, "
        "code, queried_text, match_kind, assertable, provider_key, created_at) "
        "VALUES ('c1', ?, 'medication', 'm1', 'RxNorm', '24947', 'iron', "
        "'EXACT', 1, 'rxnorm', '2026-01-01')", (case.id,))
    s.conn.commit()
    assert "ON DELETE CASCADE" not in s._table_sql("codings")
    s.conn.close()

    # Reopening runs the migration.
    s2 = S(db)
    assert "ON DELETE CASCADE" in s2._table_sql("codings")
    assert s2.q("SELECT code FROM codings") == [{"code": "24947"}]  # row kept
    assert not s2.q("SELECT 1 FROM sqlite_master WHERE name='codings_pre_cascade'")
    s2.delete_case(case.id)            # the defect the migration exists to fix
    s2.commit()
    assert s2.q("SELECT COUNT(*) n FROM codings")[0]["n"] == 0


# --------------------------------------------------------- health payload ----
# Regression: the admin screen rendered "Codes --" for every provider because
# health() reported only probe state, omitting which concept kinds an adapter
# codes and its system URI. Those are static properties of the adapter, and the
# screen has no other source for them.

def test_health_carries_static_provider_identity(monkeypatch):
    # Offline: the assertions are about static adapter identity, which must
    # hold whether or not a network is reachable.
    monkeypatch.setenv("CARETRACE_TERMINOLOGY_OFFLINE", "1")
    from caretrace.terminology.resolver import TerminologyResolver

    rows = TerminologyResolver().health()
    assert rows, "no providers registered"
    for r in rows:
        assert r["system"], f"{r['key']} reports no system"
        assert r["system_uri"], f"{r['key']} reports no system URI"
        assert r["codes_kinds"], f"{r['key']} declares no codeable kinds"

    by_key = {r["key"]: r for r in rows}
    assert by_key["rxnorm"]["codes_kinds"] == ["medication"]
    assert by_key["loinc"]["codes_kinds"] == ["observation"]


def test_health_never_exposes_a_credential_value(monkeypatch):
    """A probe may report which fields are set, never what they contain."""
    monkeypatch.setenv("CARETRACE_TERMINOLOGY_OFFLINE", "1")
    monkeypatch.setenv("CARETRACE_LOINC_USERNAME", "some-user")
    monkeypatch.setenv("CARETRACE_LOINC_PASSWORD", "s3cret-value")
    from caretrace.terminology.resolver import TerminologyResolver

    blob = json.dumps(TerminologyResolver().health())
    assert "s3cret-value" not in blob
    assert "some-user" not in blob


# ------------------------------------------------------------ stage ordering ---
# The audit's independence from terminology is enforced by ORDER: the resolver
# runs after GENERATE_AUDIT. If a future edit moves it earlier, an audit result
# could begin to depend on a network service. That would be a product-level
# regression, so it is asserted rather than left to convention.

def test_terminology_resolves_after_the_audit_is_generated():
    from caretrace.core import pipeline as P

    assert P.STAGES.index("RESOLVE_TERMINOLOGY") > P.STAGES.index("GENERATE_AUDIT")
    assert P.STAGES[-1] == "RESOLVE_TERMINOLOGY", \
        "terminology must remain the last stage"


def test_a_run_reports_exactly_the_declared_stages(tmp_path):
    from caretrace.core import pipeline as P
    from caretrace.core.store import Store
    from caretrace.demo import render_pdfs

    store = Store(tmp_path / "t.db")
    case = store.insert(M.Case(case_ref="STAGE-1", subject_label="synthetic",
                               is_synthetic=True))
    store.commit()
    pdf_dir = tmp_path / "pdfs"
    render_pdfs.render_all(pdf_dir)
    for i, path in enumerate(sorted(pdf_dir.glob("*.pdf")), start=1):
        P.ingest_document(store, case.id, path, i)
    store.commit()

    ran = [s["stage"] for s in P.process_case(store, case.id).stages]
    assert ran == list(P.STAGES), "run does not match the declared pipeline"
