"""Terminology provider contract.

A terminology provider maps a phrase as written in a document onto a code in a
published vocabulary (RxNorm, LOINC, SNOMED CT, ICD-11).

Three rules govern this layer, and they are the reason it is separate from the
audit engine rather than part of it:

1.  A coding is ADVISORY METADATA. It records that a phrase in a document
    plausibly denotes a published concept. It never decides an audit outcome.
    Conflict, change and gap detection read pack concepts and documented
    values -- never codings. A network service being reachable or not must
    never change what the audit reports, so the audit cannot depend on one.

2.  An approximate match is not an identity claim. Providers return a match
    kind, and only an exact or a publisher-listed synonym match is assertable.
    An approximate match is recorded so a reviewer can see what was considered,
    and is marked non-assertable so no downstream code can treat it as fact.

3.  A vocabulary that requires a licence CARETRACE does not hold is reported
    UNLICENSED, not silently skipped. A reviewer must be able to tell "this
    phrase has no LOINC code" from "we are not licensed to look it up".
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional, Protocol, Sequence


class MatchKind:
    """How closely a returned code corresponds to the queried phrase."""

    EXACT = "EXACT"              # phrase equals a publisher's preferred term
    SYNONYM = "SYNONYM"          # phrase equals a publisher-listed synonym
    APPROXIMATE = "APPROXIMATE"  # fuzzy/scored match; NOT an identity claim
    NONE = "NONE"                # provider searched and found nothing

    #: Kinds that may be treated as denoting the concept. An approximate match
    #: is deliberately excluded: "ferous sulphate" scoring highly against
    #: ferrous sulfate is a suggestion for a human, not a fact about the record.
    ASSERTABLE = frozenset({EXACT, SYNONYM})

    ALL = (EXACT, SYNONYM, APPROXIMATE, NONE)


class ProviderState:
    """Why a provider is or is not usable right now."""

    ACTIVE = "ACTIVE"            # configured, reachable, answering
    UNLICENSED = "UNLICENSED"    # needs credentials CARETRACE does not hold
    UNREACHABLE = "UNREACHABLE"  # configured but the endpoint did not answer
    DISABLED = "DISABLED"        # switched off by configuration
    UNKNOWN = "UNKNOWN"          # not yet probed

    ALL = (ACTIVE, UNLICENSED, UNREACHABLE, DISABLED, UNKNOWN)


@dataclass(frozen=True)
class Coding:
    """One code from one vocabulary, with the provenance of how it was obtained.

    `queried_text` is preserved verbatim: the point of a coding is to connect a
    document's own wording to a published concept, so the wording must survive
    alongside the code.
    """

    system: str                  # e.g. "RxNorm", "LOINC"
    system_uri: str              # e.g. "http://www.nlm.nih.gov/research/umls/rxnorm"
    code: str
    display: str                 # the publisher's term for the code
    queried_text: str            # the phrase as it appeared in the document
    match_kind: str
    #: Provider-reported score where one exists. Not comparable across
    #: providers, and never converted into a probability of correctness.
    score: Optional[float] = None
    #: Vocabulary release the code was resolved against, when the provider
    #: reports one. Codes are stable but their preferred terms are not, so a
    #: coding without a version cannot be reproduced exactly.
    version: Optional[str] = None
    resolved_at: Optional[str] = None
    #: True only for match kinds in MatchKind.ASSERTABLE.
    assertable: bool = False

    def __post_init__(self) -> None:
        if self.match_kind not in MatchKind.ALL:
            raise ValueError(f"unknown match kind: {self.match_kind}")
        object.__setattr__(self, "assertable",
                           self.match_kind in MatchKind.ASSERTABLE)


@dataclass(frozen=True)
class LicenceRequirement:
    """What a provider needs before it can be used, in the user's terms."""

    required: bool
    #: Name of the licence or agreement, e.g. "SNOMED CT Affiliate Licence".
    licence_name: Optional[str] = None
    #: Where the user obtains it.
    obtain_url: Optional[str] = None
    #: Credential field names the user must supply, e.g. ("username","password").
    credential_fields: tuple[str, ...] = ()
    #: One sentence a UI can show verbatim.
    note: str = ""


@dataclass
class ProviderHealth:
    """Result of probing a provider. This is what the admin screen renders."""

    key: str
    label: str
    state: str
    licence: LicenceRequirement
    detail: str = ""
    version: Optional[str] = None
    latency_ms: Optional[float] = None
    checked_at: Optional[str] = None
    #: Which credential fields are present. Never the values.
    credentials_present: tuple[str, ...] = ()
    credentials_missing: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "state": self.state,
            "detail": self.detail,
            "version": self.version,
            "latency_ms": self.latency_ms,
            "checked_at": self.checked_at,
            "licence": {
                "required": self.licence.required,
                "licence_name": self.licence.licence_name,
                "obtain_url": self.licence.obtain_url,
                "credential_fields": list(self.licence.credential_fields),
                "note": self.licence.note,
            },
            "credentials_present": list(self.credentials_present),
            "credentials_missing": list(self.credentials_missing),
        }


class TerminologyProvider(Protocol):
    """What every vocabulary adapter implements.

    Implementations must not raise on network failure: they return an empty
    result and report UNREACHABLE through `health()`. A terminology outage
    degrades annotation quality; it must never fail an audit.
    """

    key: str
    label: str
    system: str
    system_uri: str
    licence: LicenceRequirement

    def health(self) -> ProviderHealth: ...

    def lookup(self, text: str, *, kind: str = "any",
               limit: int = 3) -> Sequence[Coding]: ...


class HttpError(Exception):
    """Transport or protocol failure, carrying the status where there was one."""

    def __init__(self, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.status = status


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
