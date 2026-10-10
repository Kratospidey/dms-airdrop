#!/usr/bin/env python3
"""Run non-destructive checks; all test HOME/runtime paths stay under .qa/."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

from support import qt_tool

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--portable", action="store_true", help="stdlib tests and source/package validation only; no desktop dependencies")
args = parser.parse_args()

ROOT = Path(__file__).resolve().parents[1]
QA = ROOT / ".qa"
QA.mkdir(exist_ok=True)
for name in ("qml-runtime", "cache", "config"):
    (QA / name).mkdir(exist_ok=True)
(QA / "qml-runtime").chmod(0o700)
env = dict(os.environ, QT_QPA_PLATFORM="offscreen", XDG_RUNTIME_DIR=str(QA / "qml-runtime"),
           XDG_CACHE_HOME=str(QA / "cache"), XDG_CONFIG_HOME=str(QA / "config"))


def run(argv, name, custom_env=None):
    print(name, flush=True)
    result = subprocess.run(argv, cwd=ROOT, env=custom_env, capture_output=True, text=True)
    (QA / (name + ".log")).write_text(result.stdout + result.stderr)
    if result.returncode:
        print(result.stdout + result.stderr)
        sys.exit(result.returncode)
    print("PASS", flush=True)

run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"], "python-tests")
run([sys.executable, "scripts/audit-public.py"], "public-audit")
if args.portable:
    print("Portable checks passed; Qt/KDE, DMS, Wayland and radio were not tested.")
    sys.exit(0)
run([sys.executable, "scripts/build-picker.py"], "build-picker")
run([sys.executable, "tests/native_picker.py"], "native-picker")
for file in [*ROOT.glob("*.qml"), *(ROOT / "components").glob("*.qml"), *(ROOT / "picker").glob("*.qml"), *(ROOT / "workflow").glob("*.qml")]:
    run([qt_tool("qmlformat"), "-n", str(file)], "syntax-" + file.stem)
run([qt_tool("qmltestrunner"), "-input", "tests/tst_state.qml", "-o", "-,txt"], "qml-state", env)
run([qt_tool("qmltestrunner"), "-input", "tests/tst_selection.qml", "-o", "-,txt"], "qml-selection", env)
run([sys.executable, "tests/controller_smoke.py"], "controller-smoke")
run([sys.executable, "tests/polling_smoke.py"], "polling-smoke")
run([sys.executable, "tests/ui_smoke.py"], "ui-smoke")
run([sys.executable, "tests/marketplace_smoke.py"], "marketplace-smoke")
run([sys.executable, "tests/picker_lifecycle.py"], "picker-lifecycle")
run([sys.executable, "tests/kde_adapter_smoke.py"], "kde-adapter")
run([sys.executable, "tests/notification_smoke.py"], "notification-smoke")
run([sys.executable, "tests/command_smoke.py"], "command-smoke")
run([sys.executable, "tests/widget_compile.py"], "widget-compile")
run([sys.executable, "tests/preview.py"], "native-preview")
print("All checks passed. No live radio, transfer or installation test was performed.")
