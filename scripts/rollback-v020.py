#!/usr/bin/env python3
"""Restore the preserved 0.1.1 source; refuse later edits and active sessions."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def restore(root, apply=False):
    root = root.resolve()
    manifest = json.loads((root / ".qa/v020-update.json").read_text())
    pending = []
    with tarfile.open(Path(manifest["baseline"]) / "source.tar.gz") as archive:
        for relative, hashes in manifest["changed"].items():
            path = root / relative
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise ValueError("Unsafe path: " + relative)
            current = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
            if current == hashes["before"]:
                continue
            if current != hashes["after"]:
                raise ValueError("Independently edited since this release; preserve it first: " + relative)
            if hashes["before"] is None:
                continue  # New files remain inert; no file deletion.
            member = archive.getmember(relative)
            data = archive.extractfile(member).read()
            if hashlib.sha256(data).hexdigest() != hashes["before"]:
                raise ValueError("Baseline checksum mismatch: " + relative)
            pending.append((path, data, member.mode))
    for path, _, _ in pending: print("Restore:", path.relative_to(root))
    if not apply:
        print("Dry run. Close the picker; finish transfers and turn off any plugin-owned temporary session before --apply.")
        return
    result = subprocess.run([sys.executable, str(root / "scripts/backend.py"), "status"],
                            capture_output=True, text=True, timeout=25)
    status = json.loads(result.stdout)
    if result.returncode or not status.get("ok") or status.get("busy") or status.get("external_send") or status.get("session", {}).get("owned"):
        raise ValueError("Wait for operations and close the temporary sending session before rollback.")
    for path, data, mode in pending:
        fd, name = tempfile.mkstemp(dir=path.parent, prefix=".v020-rollback-")
        try:
            with os.fdopen(fd, "wb") as stream: stream.write(data)
            os.chmod(name, mode & 0o777)
            os.replace(name, path)
        finally:
            if os.path.exists(name): os.unlink(name)
    print("Restored source. Reload only dmsAirDrop to use 0.1.1. Omdrop, settings, symlink, and new support files were retained.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try: restore(ROOT, args.apply)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error))
