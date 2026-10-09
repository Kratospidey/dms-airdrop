#!/usr/bin/env python3
"""Real KDE widget/process tests, isolated config, optional visible Wayland."""
import argparse
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import time
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--wayland", action="store_true")
args = parser.parse_args()
qa = ROOT / ".qa/native-picker"
qa.mkdir(parents=True, exist_ok=True)
build = ROOT / ".build/picker-tests"
subprocess.run(["cmake", "-S", str(ROOT / "native"), "-B", str(build), "-DDMS_PICKER_TESTS=ON"], check=True, capture_output=True)
subprocess.run(["cmake", "--build", str(build), "--parallel", "2"], check=True, capture_output=True)
env = dict(os.environ)
if not args.wayland: env["QT_QPA_PLATFORM"] = "offscreen"
options = {"folder": str(qa), "palette": {"surface": "#141218", "base": "#211f24", "text": "#e6e0e9", "primary": "#d0bcff", "onPrimary": "#381e72"}}
binary = build / "dms-airdrop-picker"
def start(extra=None, executable=binary):
    p = subprocess.Popen([str(executable), json.dumps(dict(options, **(extra or {})))], env=env,
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if not select.select([p.stdout], [], [], 8)[0]:
        p.kill(); out, err = p.communicate(); raise AssertionError("Chooser did not open: " + err)
    assert json.loads(p.stdout.readline())["event"] == "opened"
    return p

for cycle in range(20):
    p = start()
    p.stdin.write("focus\n" * 5)
    p.stdin.flush()
    if args.wayland and cycle % 2:
        until = time.monotonic() + 3
        matches = []
        while not matches and time.monotonic() < until:
            wins = json.loads(subprocess.check_output(["niri", "msg", "--json", "windows"]))
            matches = [w for w in wins if w.get("pid") == p.pid or w.get("app_id") == "dmsAirDrop"]
            if not matches: time.sleep(0.05)
        assert len(matches) == 1, matches
        subprocess.run(["niri", "msg", "action", "close-window", "--id", str(matches[0]["id"])], check=True, capture_output=True)
    else:
        p.stdin.write("cancel\n"); p.stdin.flush()
    out, err = p.communicate(timeout=10)
    assert p.returncode == 0 and json.loads(out)["accepted"] is False, (out, err)

files = []
for name in ("one photo.txt", '日本語 "quote"\nline $().txt'):
    path = qa / name
    path.write_text("fixture")
    files.append(path)
for chosen in (files[:1], files):
    urls = [p.as_uri() for p in chosen]
    p = start({"test_urls": urls}, build / "picker-selection-test")
    # Leave the parent lifeline open until the test-only widget driver accepts.
    p.wait(timeout=12)
    out, err = p.communicate()
    result = json.loads(out)
    assert result["accepted"] and list(map(unquote, result["urls"])) == list(map(unquote, urls)), (result, urls, err)

p = start()
p.send_signal(signal.SIGTERM)
out, err = p.communicate(timeout=10)
assert p.returncode == 0 and json.loads(out)["accepted"] is False
p = start()
p.kill(); p.communicate(timeout=5)
p = start()
p.stdin.write("cancel\n"); p.stdin.flush(); p.communicate(timeout=10)
assert p.returncode == 0
print("PASS: 20 native KDE open/cancel cycles, repeated focus requests, single/multiple native acceptance, Unicode/spaces/quotes/newline path round-trip, TERM, unexpected death and reopen; " + ("real Wayland, alternating WM close" if args.wayland else "offscreen"))
