"""Snapshot every GET endpoint of an audited demo case to JSON fixtures.

The UI harness runs in Node with no listening socket available, so the API is
captured here and replayed from disk. Fixtures are generated, never edited by
hand: if a response shape changes, re-running this is the only update needed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from caretrace.api import app as A

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "uiharness/fixtures")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    c = TestClient(A.app)
    case = c.post("/api/demo").json()["case"]
    cid = case["id"]
    c.post(f"/api/cases/{cid}/process")

    paths = ["/api/meta", "/api/cases", f"/api/cases/{cid}",
             "/api/terminology/providers", "/api/terminology/config"]
    paths += [f"/api/cases/{cid}/{v}" for v in
              ("documents", "facts", "claims", "medications", "changes",
               "series", "conflicts", "evidence-gaps", "timeline", "graph",
               "brief", "codings", "patients", "run")]

    # Source and document detail routes, for the drawer.
    facts = c.get(f"/api/cases/{cid}/facts").json()
    src_ids = {f["provenance"]["source_id"] for f in facts
               if f.get("provenance")}
    paths += [f"/api/sources/{s}" for s in list(src_ids)[:4]]
    docs = c.get(f"/api/cases/{cid}/documents").json()
    paths += [f"/api/documents/{d['id']}" for d in docs[:3]]
    paths += [f"/api/documents/{d['id']}/text" for d in docs[:3]]

    index = {}
    for p in paths:
        r = c.get(p)
        index[p] = {"status": r.status_code,
                    "body": r.json() if r.status_code == 200 else None}
    (OUT / "api.json").write_text(json.dumps(
        {"case_id": cid, "responses": index}, indent=1))
    print(f"{len(index)} endpoints -> {OUT / 'api.json'}")


if __name__ == "__main__":
    main()
