"""Minimal JSON-over-HTTP transport for terminology providers.

Deliberately built on the standard library: this layer is optional at runtime,
and an optional feature should not add a hard dependency. It exists mainly so
providers share one place where timeouts, status handling and the
offline switch live -- and so tests can substitute a fake transport without
patching a third-party client.
"""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

from .base import HttpError

#: Set CARETRACE_TERMINOLOGY_OFFLINE=1 to forbid all outbound terminology
#: calls. Resolution then serves from cache only. Used by the test suite so a
#: run can never depend on a network service, and available to deployments that
#: disallow egress.
OFFLINE_ENV = "CARETRACE_TERMINOLOGY_OFFLINE"


def offline() -> bool:
    return os.environ.get(OFFLINE_ENV, "").strip() not in ("", "0", "false", "False")


class Transport:
    """Performs JSON GET/POST requests. One instance per provider."""

    def __init__(self, timeout: float = 8.0, user_agent: str = "CARETRACE/0.1"):
        self.timeout = timeout
        self.user_agent = user_agent

    def get_json(self, url: str, *, params: Optional[dict] = None,
                 headers: Optional[dict] = None) -> tuple[Any, float]:
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        return self._request(url, None, headers, "GET")

    def post_form(self, url: str, form: dict,
                  headers: Optional[dict] = None) -> tuple[Any, float]:
        body = urllib.parse.urlencode(form).encode()
        hdrs = {"Content-Type": "application/x-www-form-urlencoded", **(headers or {})}
        return self._request(url, body, hdrs, "POST")

    def _request(self, url: str, body, headers, method) -> tuple[Any, float]:
        if offline():
            raise HttpError("terminology transport is offline by configuration")
        hdrs = {"Accept": "application/json", "User-Agent": self.user_agent}
        hdrs.update(headers or {})
        req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                elapsed = (time.perf_counter() - started) * 1000.0
        except urllib.error.HTTPError as e:
            raise HttpError(f"HTTP {e.code} from {_host(url)}", status=e.code) from e
        except Exception as e:  # URLError, timeout, TLS, DNS
            raise HttpError(f"{type(e).__name__} contacting {_host(url)}") from e
        if not raw:
            return None, elapsed
        try:
            return json.loads(raw), elapsed
        except ValueError as e:
            raise HttpError(f"non-JSON response from {_host(url)}") from e


def basic_auth(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"


def _host(url: str) -> str:
    """Host only. Query strings can carry credentials, so they are never logged."""
    try:
        return urllib.parse.urlsplit(url).netloc or url
    except Exception:
        return "endpoint"
