#!/usr/bin/env python3
"""Check the explicit public file set; report categories, never matched secrets."""
from pathlib import Path
import hashlib
import re
import subprocess
import sys
from public_files import public_files

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:[A-Z ]+)?PRIVATE KEY-----"),
    "GitHub credential": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    "credential assignment": re.compile(r'''(?im)\b(?:password|api_key|access_token|secret)\s*[:=]\s*["'][A-Za-z0-9_+/=.-]{12,}["']'''),
    "personal absolute path": re.compile('/' + r'home/[^/\s]+/|/run/user/\d+/'),
}
FORBIDDEN = {".qa", ".build", "dist", "__pycache__", ".git", ".env"}
# This exact crop was visually reviewed; additional or changed images require
# another privacy review rather than allowing arbitrary binary artifacts.
APPROVED_IMAGES = {
    "assets/airdrop-popout.png": "3564c843182834207273d816f28c80b40066e8c3deb095bb5be4faf80609d6f8",
}


def audit():
    failures = []
    files = public_files(ROOT)
    for path in files:
        name = str(path.relative_to(ROOT))
        if name in APPROVED_IMAGES:
            if hashlib.sha256(path.read_bytes()).hexdigest() != APPROVED_IMAGES[name]:
                failures.append((name, "image changed since privacy review"))
            continue
        if FORBIDDEN.intersection(path.relative_to(ROOT).parts) or path.suffix in (".pem", ".key", ".pyc", ".log", ".png", ".jpg", ".p12", ".pfx"):
            failures.append((name, "excluded artifact type")); continue
        try: content = path.read_text()
        except UnicodeDecodeError:
            failures.append((name, "unreviewed binary")); continue
        for category, pattern in PATTERNS.items():
            if pattern.search(content): failures.append((name, category))
    if "--staged" in sys.argv:
        names = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split('\0')
        expected = {str(p.relative_to(ROOT)) for p in files}
        if set(filter(None, names)) != expected:
            failures.append(("Git index", "tracked/staged paths differ from public inventory"))
        for path in files:
            name = str(path.relative_to(ROOT))
            if subprocess.check_output(["git", "show", ":" + name], cwd=ROOT) != path.read_bytes():
                failures.append((name, "staged content differs from audited working file"))
    for name, category in failures: print(f"FAIL: {name}: {category}")
    if failures: raise SystemExit(1)
    print(f"PASS: {len(files)} public files, only text or explicitly reviewed images; no excluded artifacts or recognized credential patterns. Manual review still required.")


if __name__ == "__main__": audit()
