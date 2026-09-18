"""Provider configuration, read from the environment.

Credentials are read from the process environment and held in memory. They are
never written to the database, never returned by any API response, and never
logged -- `redacted()` is the only representation that leaves this module.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

#: Environment variable names, so a deployment can be configured without code.
ENV = {
    "loinc": {"username": "CARETRACE_LOINC_USERNAME",
              "password": "CARETRACE_LOINC_PASSWORD"},
    "snomed": {"endpoint": "CARETRACE_SNOMED_ENDPOINT",
               "branch": "CARETRACE_SNOMED_BRANCH",
               "api_key": "CARETRACE_SNOMED_API_KEY",
               "enabled": "CARETRACE_SNOMED_LICENCE_CONFIRMED"},
    "icd11": {"client_id": "CARETRACE_ICD_CLIENT_ID",
              "client_secret": "CARETRACE_ICD_CLIENT_SECRET",
              "release": "CARETRACE_ICD_RELEASE"},
    "rxnorm": {"base": "CARETRACE_RXNAV_BASE"},
}

#: Field names whose values must never be echoed anywhere.
SECRET_FIELDS = frozenset({"password", "api_key", "client_secret"})


@dataclass
class TerminologyConfig:
    """Resolved provider settings. Built from the environment by `from_env`."""

    loinc: dict = field(default_factory=dict)
    snomed: dict = field(default_factory=dict)
    icd11: dict = field(default_factory=dict)
    rxnorm: dict = field(default_factory=dict)
    #: Wall-clock budget for a single provider call.
    timeout: float = 8.0

    @classmethod
    def from_env(cls, env: dict | None = None) -> "TerminologyConfig":
        src = env if env is not None else os.environ
        out = cls()
        for provider, mapping in ENV.items():
            vals = {}
            for field_name, var in mapping.items():
                raw = (src.get(var) or "").strip()
                if not raw:
                    continue
                if field_name == "enabled":
                    vals[field_name] = raw not in ("0", "false", "False", "no")
                else:
                    vals[field_name] = raw
            setattr(out, provider, vals)
        t = (src.get("CARETRACE_TERMINOLOGY_TIMEOUT") or "").strip()
        if t:
            try:
                out.timeout = float(t)
            except ValueError:
                pass
        return out

    def redacted(self) -> dict:
        """Which settings are present, never their values."""
        out = {}
        for provider in ENV:
            vals = getattr(self, provider)
            out[provider] = {
                k: ("<set>" if k in SECRET_FIELDS else v)
                for k, v in sorted(vals.items())
            }
        return out
