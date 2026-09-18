"""ICD-11 via the WHO ICD API.

The WHO API is free but requires a registered client credential pair and issues
short-lived bearer tokens, so this provider ships inactive. ICD-11 codes
diagnosis STATEMENTS found in documents -- which in CARETRACE are claims, not
facts. Coding a claim does not make it true, and the claim's evidence status is
decided by the audit engine alone.
"""
from __future__ import annotations

import time
from typing import Sequence

from ..base import (Coding, HttpError, LicenceRequirement, MatchKind,
                    ProviderHealth, ProviderState, now_iso)
from ..transport import Transport

TOKEN_URL = "https://icdaccessmanagement.who.int/connect/token"
BASE = "https://id.who.int/icd"
SYSTEM = "ICD-11"
SYSTEM_URI = "http://id.who.int/icd/release/11/mms"


class Icd11Provider:
    key = "icd11"
    label = "ICD-11 (WHO ICD API)"
    system = SYSTEM
    system_uri = SYSTEM_URI
    licence = LicenceRequirement(
        required=True,
        licence_name="WHO ICD API client credentials (free registration)",
        obtain_url="https://icd.who.int/icdapi",
        credential_fields=("client_id", "client_secret"),
        note="The WHO ICD API is free but requires registered client "
             "credentials. Supply yours to activate diagnosis-statement coding.",
    )
    codes_kinds = ("diagnosis_statement",)

    def __init__(self, client_id: str | None = None,
                 client_secret: str | None = None,
                 release: str = "2024-01", linearization: str = "mms",
                 transport: Transport | None = None, base: str = BASE,
                 token_url: str = TOKEN_URL):
        self.client_id = client_id or None
        self.client_secret = client_secret or None
        self.release = release
        self.linearization = linearization
        self.transport = transport or Transport()
        self.base = base.rstrip("/")
        self.token_url = token_url
        self._token: str | None = None
        self._token_expires: float = 0.0

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _token_value(self) -> str | None:
        """Fetch or reuse a bearer token. Tokens are short-lived, so they are
        cached in memory only and never written to the database."""
        if not self.configured:
            return None
        if self._token and time.time() < self._token_expires - 30:
            return self._token
        data, _ = self.transport.post_form(self.token_url, {
            "client_id": self.client_id, "client_secret": self.client_secret,
            "scope": "icdapi_access", "grant_type": "client_credentials"})
        token = (data or {}).get("access_token")
        if not token:
            raise HttpError("token endpoint returned no access_token")
        self._token = token
        self._token_expires = time.time() + float((data or {}).get("expires_in") or 3600)
        return token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token_value()}",
                "API-Version": "v2", "Accept-Language": "en"}

    def health(self) -> ProviderHealth:
        present = tuple(f for f in ("client_id", "client_secret") if getattr(self, f))
        missing = tuple(f for f in ("client_id", "client_secret") if not getattr(self, f))
        h = ProviderHealth(key=self.key, label=self.label,
                           state=ProviderState.UNKNOWN, licence=self.licence,
                           checked_at=now_iso(), credentials_present=present,
                           credentials_missing=missing)
        if not self.configured:
            h.state = ProviderState.UNLICENSED
            h.detail = ("No WHO ICD API credentials configured. Diagnosis "
                        "statements are still audited; they carry no ICD code.")
            return h
        try:
            data, ms = self.transport.get_json(
                f"{self.base}/release/11/{self.release}/{self.linearization}",
                headers=self._headers())
            h.state = ProviderState.ACTIVE
            h.latency_ms = round(ms, 1)
            h.version = (data or {}).get("releaseId") or self.release
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
                f"{self.base}/release/11/{self.release}/{self.linearization}/search",
                params={"q": phrase, "flatResults": "true",
                        "useFlexisearch": "false"},
                headers=self._headers())
        except HttpError:
            return []
        out = []
        for item in ((data or {}).get("destinationEntities") or [])[:limit]:
            code = item.get("theCode")
            title = _strip_em(item.get("title") or "")
            if not code:
                continue
            exact = bool(item.get("matchingPVs")) and title.lower() == phrase.lower()
            out.append(Coding(
                system=SYSTEM, system_uri=SYSTEM_URI, code=str(code),
                display=title, queried_text=phrase,
                match_kind=MatchKind.EXACT if exact else MatchKind.APPROXIMATE,
                score=_score(item), version=self.release, resolved_at=now_iso()))
        return out


def _strip_em(s: str) -> str:
    """WHO wraps matched substrings in <em> tags; the code stores plain text."""
    import re
    return re.sub(r"</?em>", "", s).strip()


def _score(item) -> float | None:
    v = item.get("score")
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None
