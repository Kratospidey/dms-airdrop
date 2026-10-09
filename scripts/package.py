#!/usr/bin/env python3
"""Reproducible source-only release from the audited explicit public inventory."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
from public_files import public_files

root = Path(__file__).resolve().parents[1]
subprocess.run([sys.executable, str(root / "scripts/audit-public.py")], check=True)
version = json.loads((root / "plugin.json").read_text())["version"]
dist = root / "dist"
dist.mkdir(exist_ok=True)
archive = dist / f"dms-airdrop-{version}.tar.gz"
# No UID, username, local timestamps, symlinks or local binaries in releases.
with archive.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz, tarfile.open(fileobj=gz, mode="w") as tar:
    for path in sorted(public_files(root)):
        data = path.read_bytes()
        info = tarfile.TarInfo(f"dms-airdrop-{version}/" + str(path.relative_to(root)))
        info.size = len(data)
        info.mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
        tar.addfile(info, io.BytesIO(data))
checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
(dist / (archive.name + ".sha256")).write_text(checksum + "  " + archive.name + "\n")
print(archive)
print(checksum)
