#!/usr/bin/env python3
"""Isolated fake. Its location determines its home; cannot reach the real CLI."""
import json
from pathlib import Path
import sys
import time

home = Path(__file__).resolve().parents[2]
scenario = home / "scenario.json"
d = json.loads(scenario.read_text())
args = sys.argv[1:]
with (home / "calls.jsonl").open("a") as f:
    f.write(json.dumps(args) + "\n")

def save():
    scenario.write_text(json.dumps(d))

if args == ["version"]:
    print(d.get("version", "omdrop 0.14.1"))
elif args == ["status", "--json"]:
    time.sleep(d.get("status_delay", 0))
    if d.get("malformed"):
        print("{bad json")
    else:
        print(json.dumps(d["status"]))
    sys.exit(d.get("status_rc", 0))
elif args and args[0] == "peers":
    if d.get("peer_unreadable"):
        print("could not read the peer table (/usr/lib/omdrop/omdrop-discoverable exited 1)", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(d.get("peers", [])))
    if d.get("peer_failure"):
        print("Permission denied while reading peer table", file=sys.stderr)
        sys.exit(4)
    if not d.get("peers"):
        print("No devices found yet. Open the AirDrop sheet", file=sys.stderr)
        sys.exit(1)
elif args and args[0] == "on":
    if d.get("start_failure"):
        print("Wi-Fi network is on an unsupported channel", file=sys.stderr)
        sys.exit(3)
    if not d.get("unconfirmed"):
        d["generation"] = d.get("generation", 0) + 1
        d["status"].update(receiving=True, visible=True, mode="once" if args[1] == "once" else "timed", remaining=None if args[1] == "once" else int(args[1][:-1])*60)
        save()
elif args and args[0] == "off":
    if d.get("off_failure"):
        print("receiver would not stop", file=sys.stderr)
        sys.exit(1)
    if not d.get("unconfirmed"):
        d["status"].update(receiving=False, visible=False, mode="off", remaining=None)
        save()
elif args and args[0] == "send":
    print("Asking them to accept it...", flush=True)
    time.sleep(d.get("send_delay", 0))
    if d.get("send_result") == "reject":
        print("They declined it.", file=sys.stderr)
        sys.exit(1)
    if d.get("send_result") == "timeout":
        print("They never answered: timed out", file=sys.stderr)
        sys.exit(3)
    if d.get("change_during_send"):
        d["generation"] = d.get("generation", 0) + 1
        save()
    print("They accepted. Sending...", flush=True)
    if d.get("output_flood"):
        print("x" * 500000, file=sys.stderr)
    print("Sent files (done)", flush=True)
elif args and args[0] == "name":
    d["status"]["name"] = args[1]
    save()
elif args and args[0] == "visibility":
    d["status"]["visibility"] = args[1]
    save()
else:
    print("Unsupported mock operation", file=sys.stderr)
    sys.exit(2)
