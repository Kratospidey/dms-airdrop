"""Discover optional desktop test tools without fixed user IDs or Qt paths."""
import os
from pathlib import Path
import shutil
import subprocess


def dms_source():
    configured = os.environ.get("DMS_SOURCE")
    if configured:
        path = Path(configured).expanduser().resolve()
        if (path / "Modules/Plugins/PopoutComponent.qml").is_file(): return path
        raise RuntimeError("DMS_SOURCE must point to the DMS QML source directory")
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    candidates = sorted(runtime.glob("danklinux-shell/*/Modules/Plugins/PopoutComponent.qml"))
    if candidates: return candidates[-1].parents[2]
    raise RuntimeError("DMS sources unavailable: set DMS_SOURCE to a DMS QML checkout (including DankCommon)")


def qt_tool(name):
    for candidate in (name, name + "6", name + "-qt6"):
        found = shutil.which(candidate)
        if found: return found
    for query in ("qtpaths6", "qtpaths", "qmake6"):
        path = shutil.which(query)
        if not path: continue
        for key in ("QT_INSTALL_BINS", "QT_HOST_BINS", "QT_INSTALL_LIBEXECS"):
            result = subprocess.run([path, "--query" if "qtpaths" in query else "-query", key], capture_output=True, text=True)
            candidate = Path(result.stdout.strip()) / name
            if result.returncode == 0 and candidate.is_file(): return str(candidate)
    raise RuntimeError(f"Qt 6 development tool {name} not found in PATH or Qt's installation query")
