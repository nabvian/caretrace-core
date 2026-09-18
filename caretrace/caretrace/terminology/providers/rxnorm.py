"""RxNorm via the NLM RxNav API.

RxNorm is public-domain and RxNav needs no credentials, so this provider is
active out of the box. It is the reference implementation of the contract: an
exact-name lookup first, and only on failure an approximate search whose
results are returned as non-assertable candidates.
"""
from __future__ import annotations

from typing import Sequence

from ..base import (Coding, HttpError, LicenceRequirement, MatchKind,
                    ProviderHealth, ProviderState, now_iso)
from ..transport import Transport

BASE = "https://rxnav.nlm.nih.gov/REST"
SYSTEM = "RxNorm"
SYSTEM_URI = "http://www.nlm.nih.gov/research/umls/rxnorm"


class RxNormProvider:
    key = "rxnorm"
    label = "RxNorm (NLM RxNav)"
    system = SYSTEM
    system_uri = SYSTEM_URI
    licence = LicenceRequirement(
        required=False,
        note="RxNorm is public domain and RxNav requires no credentials.",
    )
    #: Which pack concept kinds this provider can code.
    codes_kinds = ("medication",)

    def __init__(self, transport: Transport | None = None, base: str = BASE):
        self.transport = transport or Transport()
        self.base = base.rstrip("/")

    # -- health -------------------------------------------------------------
    def health(self) -> ProviderHealth:
        h = ProviderHealth(key=self.key, label=self.label, state=ProviderState.UNKNOWN,
                           licence=self.licence, checked_at=now_iso())
        try:
            data, ms = self.transport.get_json(f"{self.base}/version.json")
            h.state = ProviderState.ACTIVE
            h.latency_ms = round(ms, 1)
            if isinstance(data, dict):
                h.version = data.get("version")
            h.detail = "Answering."
        except HttpError as e:
            h.state = ProviderState.UNREACHABLE
            h.detail = str(e)
        return h

    # -- lookup -------------------------------------------------------------
    def lookup(self, text: str, *, kind: str = "any",
               limit: int = 3) -> Sequence[Coding]:
        phrase = (text or "").strip()
        if not phrase:
            return []
        if kind not in ("any", "medication"):
            return []
        exact = self._exact(phrase)
        if exact:
            return exact[:limit]
        return self._approximate(phrase, limit)

    def _exact(self, phrase: str) -> list[Coding]:
        try:
            data, _ = self.transport.get_json(f"{self.base}/rxcui.json",
                                              params={"name": phrase})
        except HttpError:
            return []
        ids = ((data or {}).get("idGroup") or {}).get("rxnormId") or []
        out = []
        for rxcui in ids:
            display = self._preferred_name(rxcui) or phrase
            # RxNav's name lookup is case-insensitive, so a hit whose preferred
            # term differs only in case is still the publisher's own term.
            kind_ = (MatchKind.EXACT if display.lower() == phrase.lower()
                     else MatchKind.SYNONYM)
            out.append(Coding(system=SYSTEM, system_uri=SYSTEM_URI, code=str(rxcui),
                              display=display, queried_text=phrase,
                              match_kind=kind_, resolved_at=now_iso()))
        return out

    def _approximate(self, phrase: str, limit: int) -> list[Coding]:
        try:
            data, _ = self.transport.get_json(
                f"{self.base}/approximateTerm.json",
                params={"term": phrase, "maxEntries": max(1, limit)})
        except HttpError:
            return []
        cands = ((data or {}).get("approximateGroup") or {}).get("candidate") or []
        out, seen = [], set()
        for c in cands:
            rxcui = c.get("rxcui")
            if not rxcui or rxcui in seen:
                continue
            seen.add(rxcui)
            # The candidate's own `name` is the matched atom, which may be a
            # source-specific string rather than RxNorm's preferred term.
            display = c.get("name") or self._preferred_name(rxcui) or phrase
            score = c.get("score")
            out.append(Coding(
                system=SYSTEM, system_uri=SYSTEM_URI, code=str(rxcui),
                display=display, queried_text=phrase,
                match_kind=MatchKind.APPROXIMATE,
                score=float(score) if score not in (None, "") else None,
                resolved_at=now_iso()))
            if len(out) >= limit:
                break
        return out

    def _preferred_name(self, rxcui: str) -> str | None:
        try:
            data, _ = self.transport.get_json(f"{self.base}/rxcui/{rxcui}/properties.json")
        except HttpError:
            return None
        return ((data or {}).get("properties") or {}).get("name")
