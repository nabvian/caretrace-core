"""SNOMED CT via a Snowstorm terminology server.

SNOMED CT requires an affiliate licence in most territories, so this provider
ships inactive. The endpoint is configurable because affiliates commonly run
their own Snowstorm instance against their national edition -- hardcoding the
public browser would be wrong for exactly the users who are licensed.
"""
from __future__ import annotations

from typing import Sequence

from ..base import (Coding, HttpError, LicenceRequirement, MatchKind,
                    ProviderHealth, ProviderState, now_iso)
from ..transport import Transport

BASE = "https://browser.ihtsdotools.org/snowstorm/snomed-ct"
SYSTEM = "SNOMED CT"
SYSTEM_URI = "http://snomed.info/sct"


class SnomedProvider:
    key = "snomed"
    label = "SNOMED CT (Snowstorm)"
    system = SYSTEM
    system_uri = SYSTEM_URI
    licence = LicenceRequirement(
        required=True,
        licence_name="SNOMED CT Affiliate Licence",
        obtain_url="https://www.snomed.org/get-snomed",
        credential_fields=("endpoint", "branch", "api_key"),
        note="SNOMED CT requires an affiliate licence in most territories, "
             "which is free at point of use in member countries. Point this "
             "at your own Snowstorm endpoint and edition branch.",
    )
    codes_kinds = ("finding", "observation")

    def __init__(self, endpoint: str | None = None, branch: str = "MAIN",
                 api_key: str | None = None, enabled: bool = False,
                 transport: Transport | None = None):
        self.endpoint = (endpoint or BASE).rstrip("/")
        self.branch = branch or "MAIN"
        self.api_key = api_key or None
        #: SNOMED is off unless the user affirms a licence. Reachability is not
        #: permission: the public browser answers without credentials, and
        #: using it as a backdoor would put the user in breach.
        self.enabled = bool(enabled)
        self.transport = transport or Transport()

    @property
    def configured(self) -> bool:
        return self.enabled and bool(self.endpoint)

    def _headers(self) -> dict:
        return {"X-API-Key": self.api_key} if self.api_key else {}

    def health(self) -> ProviderHealth:
        present = tuple(f for f in ("endpoint", "branch", "api_key")
                        if getattr(self, f))
        h = ProviderHealth(key=self.key, label=self.label,
                           state=ProviderState.UNKNOWN, licence=self.licence,
                           checked_at=now_iso(), credentials_present=present,
                           credentials_missing=() if self.enabled else ("licence_confirmed",))
        if not self.enabled:
            h.state = ProviderState.UNLICENSED
            h.detail = ("SNOMED CT coding is off until an affiliate licence is "
                        "confirmed in configuration. Audit results are unaffected.")
            return h
        try:
            data, ms = self.transport.get_json(
                f"{self.endpoint}/codesystems", headers=self._headers())
            h.state = ProviderState.ACTIVE
            h.latency_ms = round(ms, 1)
            h.version = _edition_version(data)
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
        if kind not in ("any",) + self.codes_kinds:
            return []
        try:
            data, _ = self.transport.get_json(
                f"{self.endpoint}/{self.branch}/concepts",
                params={"term": phrase, "activeFilter": "true",
                        "limit": max(1, limit)},
                headers=self._headers())
        except HttpError:
            return []
        out = []
        for item in ((data or {}).get("items") or [])[:limit]:
            code = item.get("conceptId")
            display = ((item.get("fsn") or {}).get("term")
                       or (item.get("pt") or {}).get("term") or "")
            if not code:
                continue
            pt = (item.get("pt") or {}).get("term") or ""
            # A Snowstorm term search is a lexical match over descriptions, so
            # only an equal preferred term is an identity claim.
            kind_ = (MatchKind.EXACT if pt.strip().lower() == phrase.lower()
                     else MatchKind.APPROXIMATE)
            out.append(Coding(system=SYSTEM, system_uri=SYSTEM_URI, code=str(code),
                              display=display or pt, queried_text=phrase,
                              match_kind=kind_, resolved_at=now_iso()))
        return out


def _edition_version(data) -> str | None:
    for cs in ((data or {}).get("items") or []):
        v = (cs.get("latestVersion") or {}).get("version")
        if v:
            return str(v)
    return None
