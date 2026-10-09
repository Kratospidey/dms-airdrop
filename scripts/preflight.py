#!/usr/bin/env python3
"""Read-only prerequisite report. Never sets up Omdrop or changes the radio."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from backend import Backend, BackendError, find_omdrop


def run(argv, timeout=15):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout + p.stderr
    except (OSError, subprocess.SubprocessError):
        return 127, ""


def version(text):
    match = re.search(r"(?<!\d)(\d+)\.(\d+)\.(\d+)\b", text)
    return tuple(map(int, match.groups())) if match else None


def native_probe(root):
    missing = [name for name in ("cmake", "c++", "make") if not shutil.which(name)]
    if missing:
        return False, "Missing build tools: " + ", ".join(missing)
    rc, out = run(["cmake", "--version"])
    if rc or (version(out) or (0,)) < (3, 20, 0):
        return False, "CMake 3.20 or newer is required"
    # CMake resolves development headers and transitive library dependencies
    # more accurately than hardcoded distro library paths. Temporary files only.
    with tempfile.TemporaryDirectory(prefix="dms-airdrop-deps-") as tmp:
        rc, _ = run(["cmake", "-S", str(root / "native"), "-B", tmp,
                     "-G", "Unix Makefiles", "-DDMS_PICKER_TESTS=OFF"], timeout=60)
    return (True, "Qt 6 Widgets, KF6 KIO and IconThemes development packages found") if rc == 0 else (
        False, "CMake dependency check failed: Qt 6 Widgets, KF6 KIO/IconThemes and C++17 are needed; run scripts/build-picker.py for details")


def wifi_info(sys_net=Path("/sys/class/net")):
    rows = []
    for interface in sorted(sys_net.glob("*")):
        if not (interface / "wireless").exists() and not (interface / "phy80211").exists():
            continue
        device = interface / "device"
        driver = (device / "driver").resolve().name if (device / "driver").exists() else "unknown"
        ids = []
        for key in ("vendor", "device"):
            try: ids.append((device / key).read_text().strip())
            except OSError: ids.append("unknown")
        chipset = ":".join(ids)
        if all(re.fullmatch(r"0x[0-9a-fA-F]{4}", x) for x in ids) and shutil.which("lspci"):
            rc, out = run(["lspci", "-d", ":".join(x[2:] for x in ids)])
            if rc == 0 and out.strip(): chipset += " " + out.strip().splitlines()[0][:200]
        channel = "unknown (iw unavailable or disconnected)"
        if shutil.which("iw"):
            rc, out = run(["iw", "dev", interface.name, "info"])
            m = re.search(r"\bchannel (\d+) \((\d+) MHz\)", out)
            if rc == 0 and m: channel = f"{m[1]} ({m[2]} MHz)"
        # Do not report SSIDs, MACs, IPs, hostname or iw's raw output.
        rows.append({"interface": interface.name, "chipset": chipset, "driver": driver, "channel": channel})
    return rows


def check(root, native=True):
    root = Path(root).resolve()
    report = {"blocking": [], "warnings": [], "frontend": {}, "backend": {},
              "native_ready": False, "native": "Skipped; use basic Qt picker", "wifi": wifi_info()}
    try:
        distro = {}
        for line in Path("/etc/os-release").read_text().splitlines():
            if "=" in line:
                k, v = line.split("=", 1); distro[k] = v.strip('"')
        report["distribution"] = distro.get("PRETTY_NAME", "Unknown Linux")
    except OSError: report["distribution"] = sys.platform
    if sys.platform != "linux": report["blocking"].append("Linux is required")
    if sys.version_info < (3, 10): report["blocking"].append("Python >=3.10 is required")
    report["frontend"]["python"] = ".".join(map(str, sys.version_info[:3]))
    for tool, command, minimum in (("dms", "version", (1, 6, 2)), ("qs", "--version", (0, 3, 1))):
        path = shutil.which(tool)
        rc, out = run([path, command]) if path else (127, "")
        found = version(out)
        report["frontend"][tool] = {"path": path, "version": found}
        if rc or not found or found < minimum:
            report["blocking"].append(f"{tool} >= {'.'.join(map(str, minimum))} is required; version is missing, older or unrecognized")
        elif found != minimum:
            report["warnings"].append(f"{tool} {found} is outside the exact tested version {minimum}; installation permitted, compatibility unverified")
    if native:
        report["native_ready"], report["native"] = native_probe(root)
    if not report["native_ready"]:
        report["warnings"].append("Native thumbnails unavailable unless a working helper already exists. Choose 'Use basic file picker' if Send Files reports a picker error.")
    report["backend"]["omdrop"] = find_omdrop()
    path = report["backend"]["omdrop"]
    rc, out = run([path, "version"])
    report["backend"]["version"] = version(out) if rc == 0 else None
    if rc or out.strip() != "omdrop 0.14.1":
        report["warnings"].append("AirDrop unavailable: an already-configured Omdrop 0.14.1 installation is required; the frontend can still install")
    else:
        try:
            Backend().preservation_check()
            report["backend"]["existing_setup"] = "preservation checks passed (not a transfer test)"
        except BackendError as error:
            report["backend"]["existing_setup"] = "not ready"
            report["warnings"].append(str(error))
    for tool in ("systemctl", "systemd-run", "ss"):
        if not shutil.which(tool): report["warnings"].append(f"Backend dependency missing: {tool}")
    rc, _ = run(["systemctl", "--user", "show", "--property=Version", "--value"])
    if rc: report["warnings"].append("No accessible systemd user manager; AirDrop operations require a desktop user session")
    helper = Path("/usr/lib/omdrop/omdrop-discoverable")
    report["backend"]["radio_helper"] = str(helper) if os.access(helper, os.X_OK) else None
    if report["backend"]["radio_helper"]:
        rc, raw = run([str(helper), "probe", "--json"])
        try:
            probe = json.loads(raw)
            if rc or not isinstance(probe, dict): raise ValueError()
            # Only contract fields, never arbitrary diagnostics or identities.
            report["backend"]["radio_probe"] = {k: probe.get(k) for k in ("backend", "version", "contract", "hardware")}
            missing = [str(x.get("id", "unknown")) for x in probe.get("missing", []) if isinstance(x, dict)]
            report["backend"]["radio_probe"]["missing"] = missing
            if missing: report["warnings"].append("Radio prerequisites incomplete: " + ", ".join(missing) + "; see upstream backend instructions")
            if probe.get("backend") != "owl": report["warnings"].append("This radio backend is untested by DMS AirDrop; automatic cleanup requires OWL ownership metadata")
        except (ValueError, TypeError):
            report["warnings"].append("Radio prerequisite probe unavailable or unrecognized; hardware readiness unknown")
    else:
        report["warnings"].append("AirDrop unavailable: radio helper missing; install a compatible backend separately")
    return report


def print_report(report):
    print("Prerequisites — " + report["distribution"])
    for key, value in report["frontend"].items(): print(f"  {key}: {value}")
    print("  Native picker: " + report["native"])
    for key, value in report["backend"].items(): print(f"  {key}: {value}")
    for row in report["wifi"]: print("  Wi-Fi: " + json.dumps(row))
    if not report["wifi"]: print("  Wi-Fi: no interface detected; hardware compatibility unknown")
    for item in report["blocking"]: print("  BLOCK: " + item)
    for item in report["warnings"]: print("  WARNING: " + item)
    print("Checks never activate AirDrop. A passing probe does not prove transfers work.")
    print("Dependencies and backend setup: docs/FRIEND_SETUP.md and docs/COMPATIBILITY.md")


if __name__ == "__main__":
    result = check(Path(__file__).resolve().parents[1])
    if "--json" in sys.argv: print(json.dumps(result, indent=2))
    else: print_report(result)
    raise SystemExit(bool(result["blocking"]))
