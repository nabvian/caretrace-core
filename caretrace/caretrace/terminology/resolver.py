"""Terminology resolution: pack concept or drug name -> vocabulary codings.

The resolver owns three decisions:

*   WHICH provider is asked for a given subject. A medication goes to RxNorm, a
    laboratory analyte to LOINC, a diagnosis statement to ICD-11. Providers
    declare the kinds they can code; the resolver never asks a provider for a
    kind it does not claim.

*   WHAT is asked. For a fact, the pack's canonical concept label is queried
    rather than the document's surface form, because the surface form is often
    an abbreviation ("Hb") that no vocabulary lists, while the document's own
    wording is still preserved on the coding for provenance.

*   WHETHER to go out at all. Answers are cached by (provider, kind, phrase),
    including misses, so re-processing a case makes no network calls and an
    offline deployment still annotates phrases it has seen.

What the resolver deliberately does NOT do: influence the audit. It runs after
facts, claims and medications exist, writes only to `codings`, and its failure
mode is fewer annotations -- never a changed conflict, change or gap.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from ..core import models as M
from ..packs import medical as _packs_pkg  # noqa: F401  (namespace anchor)
from ..packs.medical import lexicon as LX
from .base import Coding as ProviderCoding
from .base import MatchKind, ProviderState
from .config import TerminologyConfig
from .providers.icd11 import Icd11Provider
from .providers.loinc import LoincProvider
from .providers.rxnorm import RxNormProvider
from .providers.snomed import SnomedProvider
from .transport import Transport

#: Vocabulary kinds a subject can be coded as.
KIND_OBSERVATION = "observation"
KIND_MEDICATION = "medication"
KIND_DIAGNOSIS = "diagnosis_statement"


def norm_query(text: str) -> str:
    """Cache key form: casefolded, whitespace-collapsed, punctuation-trimmed."""
    return re.sub(r"\s+", " ", (text or "").strip().lower()).strip(" .,:;")


@dataclass
class ResolutionReport:
    """What a resolution pass did. Surfaced in the processing-run stages."""

    attempted: int = 0
    coded: int = 0
    assertable: int = 0
    approximate: int = 0
    misses: int = 0
    cache_hits: int = 0
    provider_calls: int = 0
    skipped_unlicensed: dict = None      # provider_key -> count
    by_system: dict = None               # system -> count

    def __post_init__(self):
        if self.skipped_unlicensed is None:
            self.skipped_unlicensed = {}
        if self.by_system is None:
            self.by_system = {}

    def as_dict(self) -> dict:
        return {
            "attempted": self.attempted, "coded": self.coded,
            "assertable": self.assertable, "approximate": self.approximate,
            "misses": self.misses, "cache_hits": self.cache_hits,
            "provider_calls": self.provider_calls,
            "skipped_unlicensed": dict(self.skipped_unlicensed),
            "by_system": dict(self.by_system),
        }


class TerminologyResolver:
    def __init__(self, config: Optional[TerminologyConfig] = None,
                 providers: Optional[Sequence] = None,
                 transport: Optional[Transport] = None):
        cfg = config or TerminologyConfig.from_env()
        self.config = cfg
        tr = transport or Transport(timeout=cfg.timeout)
        if providers is not None:
            self.providers = list(providers)
        else:
            self.providers = [
                RxNormProvider(transport=tr, **_only(cfg.rxnorm, {"base"})),
                LoincProvider(transport=tr, **_only(cfg.loinc, {"username", "password"})),
                SnomedProvider(transport=tr, **_only(cfg.snomed,
                               {"endpoint", "branch", "api_key", "enabled"})),
                Icd11Provider(transport=tr, **_only(cfg.icd11,
                              {"client_id", "client_secret", "release"})),
            ]
        self._by_key = {p.key: p for p in self.providers}

    # ---------------------------------------------------------------- health
    def health(self) -> list[dict]:
        """Probe every provider, merged with its static identity.

        `ProviderHealth` describes a moment in time; which concept kinds a
        vocabulary codes and what its system URI is are properties of the
        adapter, not of the probe. The admin screen needs both, so they are
        joined here rather than duplicated into every provider's health call.
        """
        out = []
        for p in self.providers:
            d = p.health().as_dict()
            d["system"] = getattr(p, "system", None)
            d["system_uri"] = getattr(p, "system_uri", None)
            d["codes_kinds"] = list(getattr(p, "codes_kinds", ()))
            out.append(d)
        return out

    def providers_for(self, kind: str) -> list:
        return [p for p in self.providers
                if kind in getattr(p, "codes_kinds", ())]

    # --------------------------------------------------------------- resolve
    def resolve_case(self, store, case_id: str) -> ResolutionReport:
        """Annotate every fact, medication and claim in a case.

        Runs last in the pipeline and writes only to `codings`.
        """
        report = ResolutionReport()
        rows = []
        for f in store.rows("facts", case_id):
            phrase = self._fact_query(f)
            if phrase:
                rows.append((M.SubjectType.FACT, f["id"], phrase,
                             f.get("surface_form") or phrase, KIND_OBSERVATION))
        for m in store.rows("medications", case_id):
            name = (m.get("drug_name") or "").strip()
            if name:
                rows.append((M.SubjectType.MEDICATION, m["id"], name, name,
                             KIND_MEDICATION))
        for c in store.rows("claims", case_id):
            text = (c.get("claim_text") or "").strip()
            if text:
                rows.append((M.SubjectType.CLAIM, c["id"], text, text,
                             KIND_DIAGNOSIS))

        out: list[M.Coding] = []
        for subject_type, subject_id, query, surface, kind in rows:
            report.attempted += 1
            codings = self._lookup_cached(store, query, kind, report)
            if not codings:
                report.misses += 1
                continue
            for pc in codings:
                report.coded += 1
                if pc.assertable:
                    report.assertable += 1
                else:
                    report.approximate += 1
                report.by_system[pc.system] = report.by_system.get(pc.system, 0) + 1
                out.append(M.Coding(
                    case_id=case_id, subject_type=subject_type,
                    subject_id=subject_id, system=pc.system,
                    system_uri=pc.system_uri, code=pc.code, display=pc.display,
                    # The document's own wording, not the normalized query.
                    queried_text=surface, match_kind=pc.match_kind,
                    assertable=1 if pc.assertable else 0, score=pc.score,
                    version=pc.version, provider_key=_provider_of(pc, self.providers),
                    resolved_at=pc.resolved_at))
        if out:
            store.insert_many(out)
        for p in self.providers:
            if not getattr(p, "configured", True):
                report.skipped_unlicensed[p.key] = report.skipped_unlicensed.get(p.key, 0)
        return report

    def _fact_query(self, fact_row: dict) -> Optional[str]:
        """Query the pack's canonical label, not the document's abbreviation.

        A CBC prints "Hb"; no vocabulary lists that. The pack knows the phrase
        the concept is published under, and the surface form is still kept on
        the coding so provenance points at what the document actually said.
        """
        concept = fact_row.get("concept")
        if not concept:
            return None
        cd = LX.CONCEPTS.get(concept)
        if cd is not None:
            return cd.label
        # A qualitative finding has no ConceptDef; its label is the best query.
        return LX.concept_label(concept) or None

    def _lookup_cached(self, store, query: str, kind: str,
                       report: ResolutionReport) -> list[ProviderCoding]:
        key = norm_query(query)
        results: list[ProviderCoding] = []
        for provider in self.providers_for(kind):
            cached = store.q1(
                "SELECT * FROM terminology_cache WHERE provider_key=? AND kind=? "
                "AND query_norm=?", (provider.key, kind, key))
            if cached is not None:
                report.cache_hits += 1
                if not cached["miss"]:
                    results.extend(_codings_from_json(cached["payload"]))
                continue
            if not getattr(provider, "configured", True):
                # Unlicensed: record nothing, and do not cache a miss -- the
                # phrase was never searched, so a later licensed run must try.
                report.skipped_unlicensed[provider.key] = \
                    report.skipped_unlicensed.get(provider.key, 0) + 1
                continue
            report.provider_calls += 1
            found = list(provider.lookup(query, kind=kind, limit=3))
            store.insert(M.TerminologyCacheEntry(
                provider_key=provider.key, kind=kind, query_norm=key,
                payload=json.dumps([_coding_to_json(c) for c in found]),
                miss=0 if found else 1))
            store.commit()
            results.extend(found)
        return results


def _only(vals: dict, allowed: set) -> dict:
    return {k: v for k, v in (vals or {}).items() if k in allowed}


def _provider_of(coding: ProviderCoding, providers: Iterable) -> str:
    for p in providers:
        if p.system == coding.system:
            return p.key
    return "unknown"


def _coding_to_json(c: ProviderCoding) -> dict:
    return {"system": c.system, "system_uri": c.system_uri, "code": c.code,
            "display": c.display, "queried_text": c.queried_text,
            "match_kind": c.match_kind, "score": c.score,
            "version": c.version, "resolved_at": c.resolved_at}


def _codings_from_json(payload: str) -> list[ProviderCoding]:
    try:
        items = json.loads(payload)
    except ValueError:
        return []
    out = []
    for d in items:
        try:
            out.append(ProviderCoding(**d))
        except (TypeError, ValueError):
            continue
    return out
