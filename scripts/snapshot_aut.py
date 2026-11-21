#!/usr/bin/env python3
"""Make an isolated copy of the starter application in .aut/starter_code.

Docker builds from this copy only, so the starter repository is never written to (no
target/, no node_modules/.vite). It reads from AUT_DIR (default ../git-demo/starter_code)
and skips build output, dependencies and logs. Afterwards every file is verified by
SHA-256, and a manifest is written to .aut/MANIFEST.sha256.

Usage: python3 -I scripts/snapshot_aut.py
"""

import hashlib
import os
import shutil
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get("AUT_DIR", PROJECT.parent / "git-demo" / "starter_code")).resolve()
DEST_ROOT = PROJECT / ".aut"
DEST = DEST_ROOT / "starter_code"
SKIP_DIRS = {"node_modules", "target", ".git"}
SKIP_FILES = {"agent-audit.log"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            if name not in SKIP_FILES:
                yield Path(dirpath, name)


def main() -> int:
    if not (SOURCE / "backend" / "pom.xml").is_file():
        print(f"snapshot: AUT source not found at {SOURCE}", file=sys.stderr)
        return 1
    if DEST.exists():
        shutil.rmtree(DEST)
    manifest = []
    for src in source_files(SOURCE):
        rel = src.relative_to(SOURCE)
        dst = DEST / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)  # reads the source, writes only under .aut/
        if sha256(src) != sha256(dst):
            print(f"snapshot: checksum mismatch for {rel}", file=sys.stderr)
            return 1
        manifest.append(f"{sha256(dst)}  {rel}")
    (DEST_ROOT / "MANIFEST.sha256").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    print(f"snapshot: {len(manifest)} files copied from {SOURCE} to {DEST} (all SHA-256 verified)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
