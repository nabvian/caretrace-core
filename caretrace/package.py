"""Build caretrace.zip — the distributable repo.

Explicit exclusions, because an ad-hoc `zip -r` shipped 2,080 vendored
node_modules files (24 MB of third-party JS) alongside 140 files of actual
project. The harness's package.json is retained so `npm install` reproduces
them; the installed tree is not ours to redistribute.

Run from the repo root. Prints the manifest summary it produced.
"""
from __future__ import annotations

import pathlib
import zipfile
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT.parent / "caretrace.zip"

# Directory names pruned wherever they appear.
PRUNE_DIRS = {
    "node_modules",      # reinstallable from uiharness/package.json
    "__pycache__",
    ".pytest_cache",
    ".git",
    "handoff",           # cross-kernel scratch, not part of the product
    ".ipynb_checkpoints",
}
# Suffixes never shipped: databases are generated, caches are noise.
PRUNE_SUFFIX = {".db", ".db-wal", ".db-shm", ".pyc", ".pyo", ".DS_Store"}


def included() -> list[pathlib.Path]:
    keep = []
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if PRUNE_DIRS & set(rel.parts):
            continue
        if p.suffix in PRUNE_SUFFIX or p.name in PRUNE_SUFFIX:
            continue
        keep.append(p)
    return keep


def main() -> None:
    files = included()
    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in files:
            z.write(p, pathlib.Path("caretrace") / p.relative_to(ROOT))

    tops = Counter(
        (p.relative_to(ROOT).parts[0] if len(p.relative_to(ROOT).parts) > 1
         else "(root)")
        for p in files
    )
    print(f"{OUT.name}  {OUT.stat().st_size / 1e6:.2f} MB  {len(files)} files")
    for name, n in tops.most_common():
        print(f"  {n:>4}  {name}")


if __name__ == "__main__":
    main()
