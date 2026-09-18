"""Executes every frontend screen in a DOM and fails on a runtime error.

Python tests cover the engine and the API; nothing above covered the screens,
where the real defect classes are runtime rather than syntactic -- a view-map
entry that was never registered, a helper that does not exist, a field the API
never returns. `uiharness/render_screens.js` renders each screen against
captured API responses and reports what landed in the DOM.

The harness needs Node and jsdom. Where either is absent the test skips rather
than failing: a missing dev tool is not a defect in CARETRACE, and silently
passing would be worse than either.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "uiharness"
SCRIPT = HARNESS / "render_screens.js"
FIXTURES = HARNESS / "fixtures" / "api.json"


def _node() -> str | None:
    return shutil.which("node")


requires_harness = pytest.mark.skipif(
    _node() is None
    or not SCRIPT.exists()
    or not (HARNESS / "node_modules" / "jsdom").exists(),
    reason="node + jsdom harness not installed (see uiharness/README.md)",
)


@pytest.fixture(scope="module")
def fixtures() -> Path:
    """Refresh the captured API responses before rendering against them.

    Regenerating here is what keeps the fixtures honest: a response-shape
    change is picked up by the next test run rather than drifting silently.
    """
    subprocess.run(
        [sys.executable, str(HARNESS / "snapshot_api.py"), str(FIXTURES.parent)],
        cwd=ROOT, check=True, capture_output=True,
    )
    assert FIXTURES.exists()
    return FIXTURES


@requires_harness
def test_every_screen_renders_without_a_runtime_error(fixtures):
    r = subprocess.run([_node(), str(SCRIPT)], cwd=HARNESS,
                       capture_output=True, text=True, timeout=300)
    out = r.stdout + r.stderr
    assert "LOADFAIL" not in out, out
    assert "HARNESS ERROR" not in out, out
    failures = [ln for ln in out.splitlines() if ln.startswith("FAIL")]
    assert not failures, "screens failed to render:\n" + "\n".join(failures) \
        + "\n\nfull output:\n" + out
    assert r.returncode == 0, out


@requires_harness
def test_the_harness_covers_every_registered_screen(fixtures):
    """A screen absent from the harness is untested; fail rather than skip it."""
    r = subprocess.run([_node(), str(SCRIPT)], cwd=HARNESS,
                       capture_output=True, text=True, timeout=300)
    rendered = {ln.split()[1] for ln in r.stdout.splitlines()
                if ln[:4] in ("OK  ", "FAIL", "SKIP")}
    registered = set()
    for js in (ROOT / "caretrace" / "web" / "js").glob("*.js"):
        for line in js.read_text().splitlines():
            if "Router.register(" in line:
                registered.add(line.split("Router.register(")[1].split("'")[1])
    assert registered, "no screens discovered in the source"
    assert registered <= rendered, \
        f"screens never rendered by the harness: {sorted(registered - rendered)}"


@requires_harness
def test_terminology_screens_state_that_the_audit_is_independent(fixtures):
    """The independence claim is load-bearing product language, not decoration.

    If a future edit drops it, a reader could reasonably conclude that an
    unlicensed vocabulary weakened the audit. It did not.
    """
    for screen in ("codings", "terminology"):
        r = subprocess.run([_node(), str(SCRIPT), screen, "--dump"],
                           cwd=HARNESS, capture_output=True, text=True,
                           timeout=180)
        text = r.stdout.lower()
        assert "no audit result depends" in text or \
               "audit results do not depend" in text, \
               f"{screen} does not state audit independence:\n{r.stdout}"


@requires_harness
def test_no_screen_renders_a_placeholder_or_undefined(fixtures):
    """Guards the markers that mean a field was renamed or never returned."""
    r = subprocess.run([_node(), str(SCRIPT)], cwd=HARNESS,
                       capture_output=True, text=True, timeout=300)
    for marker in ("undefined", "NaN", "[object Object]"):
        assert f'suspect="{marker}"' not in r.stdout, \
            f"a screen rendered {marker!r}:\n{r.stdout}"


# ------------------------------------------------------------ offline build ---
# The single-file demo is a distinct artifact: it inlines the scripts and
# answers fetch from a captured response table. A screen can work when served
# and fail there -- most often because the builder never captured an endpoint
# the screen calls. So the shipped file is rendered too, not just the source.

OFFLINE_CHECK = HARNESS / "check_offline.js"
OFFLINE_HTML = ROOT / "caretrace_demo.html"


@requires_harness
@pytest.mark.skipif(not OFFLINE_CHECK.exists(), reason="offline checker absent")
def test_offline_build_renders_every_screen(tmp_path):
    """Rebuild the single-file demo, then render every screen out of it."""
    built = subprocess.run(
        [sys.executable, "build_offline.py"], cwd=ROOT,
        capture_output=True, text=True, timeout=600)
    assert built.returncode == 0, built.stdout + built.stderr
    assert OFFLINE_HTML.exists()

    r = subprocess.run([_node(), str(OFFLINE_CHECK), str(OFFLINE_HTML)],
                       cwd=HARNESS, capture_output=True, text=True, timeout=300)
    out = r.stdout + r.stderr
    failures = [ln for ln in r.stdout.splitlines() if ln.startswith("FAIL")]
    assert not failures, "offline screens failed:\n" + "\n".join(failures) \
        + "\n\nfull output:\n" + out
    assert r.returncode == 0, out


@requires_harness
@pytest.mark.skipif(not OFFLINE_CHECK.exists(), reason="offline checker absent")
def test_offline_build_carries_the_terminology_endpoints():
    """A screen whose endpoint was not captured renders an error, not data."""
    html = OFFLINE_HTML.read_text()
    for path in ("/api/cases", "/codings", "/api/terminology/providers",
                 "/api/terminology/config"):
        assert path in html, f"offline build never captured {path}"
