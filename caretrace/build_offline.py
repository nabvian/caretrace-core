"""Build a single-file offline demo of CARETRACE.

Every screen in the SPA reads its data through one function -- `fetch()` in
core.js. So the offline build needs no application changes at all: it inlines
the CSS and JS, runs the real pipeline over the real demo corpus, captures
every API response the demo flow touches, and installs a `fetch` shim that
serves those captured responses from an embedded map.

The audit numbers in the offline file are therefore produced by the same
deterministic engine as the served application -- not transcribed by hand.
"""
from __future__ import annotations

import base64
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from caretrace.api import app as A  # noqa: E402
from caretrace.core.store import Store  # noqa: E402

WEB = ROOT / "caretrace" / "web"
JS_ORDER = ["core.js", "screens_entry.js", "screens_audit.js",
            "screen_graph.js", "screen_brief.js", "screens_registry.js",
            "screens_terminology.js"]


def capture() -> tuple[dict, str]:
    """Run the real pipeline and record every response the demo flow needs."""
    tmp = Path(tempfile.mkdtemp(prefix="caretrace-build-"))
    A.DATA_DIR = tmp
    A.UPLOAD_DIR = tmp / "uploads"
    A._store = Store(tmp / "build.db")
    client = TestClient(A.app)

    responses: dict[str, object] = {}

    def grab(path: str, method: str = "GET", body=None):
        r = client.request(method, path, json=body)
        r.raise_for_status()
        responses[f"{method} {path}"] = r.json()
        return r.json()

    meta = grab("/api/meta")
    case = grab("/api/demo", "POST")["case"]
    cid = case["id"]

    run = grab(f"/api/cases/{cid}/process", "POST")
    grab("/api/cases")
    summary = grab(f"/api/cases/{cid}")

    for view in ("documents", "facts", "claims", "medications", "changes",
                 "series", "conflicts", "evidence-gaps", "timeline", "graph",
                 "brief", "codings", "patients"):
        grab(f"/api/cases/{cid}/{view}")

    # Provider status is captured as it stood at build time, so the offline
    # file states plainly which vocabularies were consulted for these codings
    # rather than implying a live probe it cannot perform.
    grab("/api/terminology/providers")
    grab("/api/terminology/config")

    # Document drawers: every document, so the source viewer works offline.
    # The raw-text payload comes along so extraction provenance and the
    # verbatim retained text are both visible without a server.
    for doc in responses[f"GET /api/cases/{cid}/documents"]:
        grab(f"/api/documents/{doc['id']}")
        grab(f"/api/documents/{doc['id']}/text")

    # Provenance drawers. Every fact/claim/medication carries a source_id and
    # any of them can be clicked, so capture the whole sources table rather
    # than guessing which the demo flow touches.
    for src in A._store.q("SELECT id FROM sources WHERE case_id = ?", (cid,)):
        grab(f"/api/sources/{src['id']}")

    # The original PDFs, so "Open original file" works from a file:// URL.
    files: dict[str, str] = {}
    for doc in responses[f"GET /api/cases/{cid}/documents"]:
        r = client.get(f"/api/documents/{doc['id']}/file")
        if r.status_code == 200:
            files[f"/api/documents/{doc['id']}/file"] = base64.b64encode(r.content).decode()

    shutil.rmtree(tmp, ignore_errors=True)
    return {"responses": responses, "files": files,
            "case_id": cid, "meta": meta, "metrics": summary["metrics"],
            "stages": run.get("stages", [])}, cid


SHIM = """
/* Offline transport shim.
   The application is unmodified: it still calls fetch() for every payload.
   Here fetch() is answered from the captured response map baked in above
   instead of from the network, so this single file runs from file://. */
(() => {
  const DB = window.__CARETRACE_OFFLINE__;
  const json = (body, status = 200) => new Response(JSON.stringify(body), {
    status, headers: { 'Content-Type': 'application/json' } });

  window.fetch = async (input, opts = {}) => {
    const url = typeof input === 'string' ? input : input.url;
    const path = url.replace(/^https?:\\/\\/[^/]+/, '').split('?')[0];
    const method = (opts.method || 'GET').toUpperCase();

    if (DB.files[path]) {
      const bin = Uint8Array.from(atob(DB.files[path]), c => c.charCodeAt(0));
      return new Response(bin, { headers: { 'Content-Type': 'application/pdf' } });
    }
    const hit = DB.responses[`${method} ${path}`];
    if (hit !== undefined) {
      // Processing is instantaneous offline; pace it so the pipeline view is legible.
      if (method === 'POST' && path.endsWith('/process')) {
        await new Promise(r => setTimeout(r, 900));
      }
      return json(hit);
    }
    if (method === 'POST' && path === '/api/cases') {
      return json({ detail: 'Creating new cases requires the CARETRACE server. '
        + 'This offline build carries the demo case only.' }, 501);
    }
    if (method === 'POST' && path.includes('/documents')) {
      return json({ detail: 'Uploading requires the CARETRACE server. Run '
        + '`python -m caretrace.api.app` for the full application; this offline '
        + 'build carries the pre-processed demo case only.' }, 501);
    }
    if (method === 'DELETE') {
      return json({ detail: 'Deletion requires the CARETRACE server.' }, 501);
    }
    return json({ detail: `Not available in the offline build: ${method} ${path}` }, 404);
  };
})();
"""

BANNER = """
<div class="offline-banner">
  <strong>Offline build.</strong> This single file contains the CARETRACE
  interface and one fully processed synthetic case ({case_ref}), captured from
  the real deterministic audit engine. Upload and re-processing need the server
  &mdash; run <code>python -m caretrace.api.app</code> for those.
</div>
"""


def build(out: Path) -> Path:
    db, cid = capture()
    css = (WEB / "styles.css").read_text()
    js = "\n\n".join(f"/* ===== {n} ===== */\n" + (WEB / "js" / n).read_text()
                     for n in JS_ORDER)
    case_ref = db["responses"][f"GET /api/cases/{cid}"]["case"]["case_ref"]

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CARETRACE — Evidence Audit for Fragmented Medical Records</title>
<style>
{css}
.offline-banner {{
  background: var(--ink-900); color: #dbe4ec; font-size: 12px;
  padding: 7px 20px; text-align: center; letter-spacing: .01em;
}}
.offline-banner strong {{ color: #fff; }}
.offline-banner code {{
  background: rgba(255,255,255,.13); padding: 1px 5px; border-radius: 3px;
  font-size: 11px;
}}
@media print {{ .offline-banner {{ display: none; }} }}
</style>
</head>
<body>
{BANNER.format(case_ref=case_ref)}
<div id="app"></div>
<script>window.__CARETRACE_OFFLINE__ = {json.dumps(db, separators=(",", ":"))};</script>
<script>{SHIM}</script>
<script>
{js}
</script>
<script>
  (async () => {{
    try {{ State.meta = await API.get('/api/meta'); }} catch (e) {{}}
    State.caseId = window.__CARETRACE_OFFLINE__.case_id;
    localStorage.setItem('caretrace.case', State.caseId);
    Router.start();
  }})();
</script>
</body>
</html>
"""
    out.write_text(html)
    return out


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "caretrace_demo.html")
    p = build(target)
    print(f"{p} {p.stat().st_size / 1024:.0f} KB")
