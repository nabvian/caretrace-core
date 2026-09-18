"""LOINC via the Regenstrief FHIR terminology server.

LOINC content is free but its terminology server requires a (free) LOINC
account, so this provider ships complete and inactive: without credentials it
reports UNLICENSED and returns nothing. It does not fall back to guessing a
code, because a wrong LOINC code is worse than an absent one -- it would make
two different measurements look like the same observation.
"""
from __future__ import annotations

from typing import Sequence

from ..base import (Coding, HttpError, LicenceRequirement, MatchKind,
                    ProviderHealth, ProviderState, now_iso)
from ..transport import Transport, basic_auth

BASE = "https://fhir.loinc.org"
SYSTEM = "LOINC"
SYSTEM_URI = "http://loinc.org"


class LoincProvider:
    key = "loinc"
    label = "LOINC (Regenstrief FHIR server)"
    system = SYSTEM
    system_uri = SYSTEM_URI
    licence = LicenceRequirement(
        required=True,
        licence_name="LOINC account (free registration)",
        obtain_url="https://loinc.org/downloads/",
        credential_fields=("username", "password"),
        note="LOINC content is free of charge but the terminology server "
             "requires a registered LOINC account. Supply yours to activate "
             "laboratory-observation coding.",
    )
    codes_kinds = ("observation",)

    def __init__(self, username: str | None = None, password: str | None = None,
                 transport: Transport | None = None, base: str = BASE):
        self.username = username or None
        self.password = password or None
        self.transport = transport or Transport()
        self.base = base.rstrip("/")

    @property
    def configured(self) -> bool:
        return bool(self.username and self.password)

    def _auth(self) -> dict:
        return {"Authorization": basic_auth(self.username or "", self.password or "")}

    def health(self) -> ProviderHealth:
        present = tuple(f for f in ("username", "password") if getattr(self, f))
        missing = tuple(f for f in ("username", "password") if not getattr(self, f))
        h = ProviderHealth(key=self.key, label=self.label,
                           state=ProviderState.UNKNOWN, licence=self.licence,
                           checked_at=now_iso(), credentials_present=present,
                           credentials_missing=missing)
        if not self.configured:
            h.state = ProviderState.UNLICENSED
            h.detail = ("No LOINC credentials configured. Laboratory codings "
                        "are not produced; audit results are unaffected.")
            return h
        try:
            data, ms = self.transport.get_json(
                f"{self.base}/CodeSystem",
                params={"url": SYSTEM_URI}, headers=self._auth())
            h.state = ProviderState.ACTIVE
            h.latency_ms = round(ms, 1)
            h.version = _first_version(data)
            h.detail = "Answering."
        except HttpError as e:
            if e.status in (401, 403):
                h.state = ProviderState.UNLICENSED
                h.detail = f"Server rejected the supplied credentials ({e.status})."
            else:
                h.state = ProviderState.UNREACHABLE
                h.detail = str(e)
        return h

    def lookup(self, text: str, *, kind: str = "any",
               limit: int = 3) -> Sequence[Coding]:
        phrase = (text or "").strip()
        if not phrase or not self.configured:
            return []
        if kind not in ("any", "observation"):
            return []
        try:
            data, _ = self.transport.get_json(
                f"{self.base}/ValueSet/$expand",
                params={"url": f"{SYSTEM_URI}/vs", "filter": phrase,
                        "count": max(1, limit)},
                headers=self._auth())
        except HttpError:
            return []
        return _codings_from_expansion(data, phrase, limit)

    def lookup_code(self, code: str) -> Coding | None:
        """Resolve a code the document itself printed, to confirm and label it."""
        if not self.configured or not code:
            return None
        try:
            data, _ = self.transport.get_json(
                f"{self.base}/CodeSystem/$lookup",
                params={"system": SYSTEM_URI, "code": code},
                headers=self._auth())
        except HttpError:
            return None
        display = _param(data, "display")
        if not display:
            return None
        return Coding(system=SYSTEM, system_uri=SYSTEM_URI, code=code,
                      display=display, queried_text=code,
                      match_kind=MatchKind.EXACT, version=_param(data, "version"),
                      resolved_at=now_iso())


def _codings_from_expansion(data, phrase: str, limit: int) -> list[Coding]:
    exp = (data or {}).get("expansion") or {}
    version = None
    for p in exp.get("parameter") or []:
        if p.get("name") == "version":
            version = p.get("valueUri") or p.get("valueString")
    out = []
    for item in (exp.get("contains") or [])[:limit]:
        display = item.get("display") or ""
        code = item.get("code")
        if not code:
            continue
        # The server filters by substring, so a returned row is only an exact
        # match when its display equals the queried phrase.
        kind = (MatchKind.EXACT if display.strip().lower() == phrase.lower()
                else MatchKind.APPROXIMATE)
        out.append(Coding(system=SYSTEM, system_uri=SYSTEM_URI, code=str(code),
                          display=display, queried_text=phrase, match_kind=kind,
                          version=version, resolved_at=now_iso()))
    return out


def _first_version(bundle) -> str | None:
    for entry in ((bundle or {}).get("entry") or []):
        v = (entry.get("resource") or {}).get("version")
        if v:
            return v
    return None


def _param(data, name: str) -> str | None:
    for p in ((data or {}).get("parameter") or []):
        if p.get("name") == name:
            return p.get("valueString") or p.get("valueCode") or p.get("valueUri")
    return None
