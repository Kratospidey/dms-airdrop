#!/usr/bin/env python3
"""Dry-run-first installation and narrowly scoped rollback. No dependencies."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile

ID = "dmsAirDrop"
SOURCE = Path(__file__).resolve().parents[1]


def install(source, directory, apply=False):
    source = source.resolve(strict=True)
    target = directory / ID
    manifest = json.loads((source / "plugin.json").read_text())
    if manifest.get("id") != ID:
        raise ValueError("Unexpected source plugin ID")
    same_source = target.is_symlink() and target.resolve() == source
    if os.path.lexists(target) and not same_source:
        raise ValueError(f"Refusing to overwrite existing path: {target}")
    if directory.exists():
        for entry in directory.iterdir():
            if entry == target and same_source: continue
            file = entry / "plugin.json"
            if not file.is_file(): continue
            try:
                existing = json.loads(file.read_text())
            except (ValueError, OSError):
                raise ValueError(f"Cannot inspect existing manifest: {file}; resolve it before installing")
            if existing.get("id") == ID:
                raise ValueError(f"The same plugin ID is already installed at {entry}")
    if same_source:
        print(f"Already installed: {target} -> {source}")
        return target
    print(f"Create symlink: {target} -> {source}")
    print("DMS enablement, bar layout and Omdrop configuration remain under your control.")
    if apply:
        directory.mkdir(parents=True, exist_ok=True)
        target.symlink_to(source, target_is_directory=True)
    return target


def uninstall(source, directory, apply=False):
    target = directory / ID
    if not os.path.lexists(target):
        print(f"Already uninstalled: {target}")
        return
    if not target.is_symlink() or target.resolve() != source.resolve():
        raise ValueError(f"Refusing removal: {target} is not this project's symlink")
    print(f"Remove only symlink: {target}")
    if apply:
        target.unlink()


def restore_settings(home, config, apply=False):
    folder = config / "DankMaterialShell/dms-airdrop-backups"
    allowed = {"config.toml.original.json": config / "airdrop/config.toml",
               "visibility.original.json": config / "omdrop/visibility"}
    planned = []
    for filename, target in allowed.items():
        backup = folder / filename
        if not backup.exists(): continue
        if backup.is_symlink() or backup.stat().st_uid != os.getuid():
            raise ValueError("Refusing an untrusted settings backup")
        data = json.loads(backup.read_text())
        current = hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None
        if data.get("path") != str(target) or "last_applied_sha256" not in data or current != data["last_applied_sha256"]:
            raise ValueError(f"Configuration changed independently or its last write is unverified: {target}. Review backup {backup} manually.")
        if target.is_symlink():
            raise ValueError(f"Refusing to replace a symlink: {target}")
        print(f"Restore original plugin-edited setting: {target}")
        planned.append((target, data))
    if not planned:
        print("No plugin-edited settings need restoration.")
    if apply:
        for target, data in planned:
            if not data["existed"]:
                target.unlink(missing_ok=True)
                continue
            fd, temp = tempfile.mkstemp(prefix=".airdrop-restore-", dir=target.parent)
            try:
                with os.fdopen(fd, "w") as stream:
                    stream.write(data["content"])
                os.chmod(temp, data["mode"] & 0o777)
                os.replace(temp, target)
            finally:
                if os.path.exists(temp): os.unlink(temp)
        # Backups are retained for review; no broad cleanup.


def ensure_idle(config, home):
    from backend import Backend, BackendError
    backend = Backend(home=home, config=config)
    try:
        with backend.lock("submit.lock"):
            if backend.busy() or backend.queued():
                raise ValueError("An AirDrop operation is still running. Wait for completion before uninstalling or restoring settings.")
            backend.reconcile_requests()
    except BackendError as error:
        raise ValueError(str(error)) from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "check", "uninstall", "restore-settings"), nargs="?", default="install")
    parser.add_argument("--apply", action="store_true", help="perform the printed change (default is dry run)")
    parser.add_argument("--picker", choices=("auto", "native", "basic"), default="auto", help="auto builds when dependencies exist; native requires a successful build; basic skips building")
    parser.add_argument("--disabled", action="store_true", help="confirm you disabled the plugin in DMS before rollback")
    args = parser.parse_args()
    home = Path.home()
    raw_config = os.environ.get("XDG_CONFIG_HOME", "")
    config = Path(raw_config) if raw_config and Path(raw_config).is_absolute() else home / ".config"
    try:
        if args.action in ("uninstall", "restore-settings") and args.apply:
            if not args.disabled:
                raise ValueError("Disable the plugin in DMS, then use --disabled to confirm that step")
            ensure_idle(config, home)
        if args.action in ("install", "check"):
            from preflight import check, print_report
            report = check(SOURCE, native=args.picker != "basic")
            print_report(report)
            if report["blocking"]:
                raise ValueError("Resolve the blocking frontend requirements above, then retry.")
            if args.action == "check":
                return 0
            directory = config / "DankMaterialShell/plugins"
            # Validate conflicts before building or publishing a symlink.
            install(SOURCE, directory, False)
            if args.picker == "native" and not report["native_ready"]:
                raise ValueError("Native picker prerequisites are incomplete. Install them or choose --picker basic.")
            if args.apply:
                if args.picker != "basic" and report["native_ready"]:
                    from picker_build import build_picker
                    # A detected-but-broken build fails before the symlink is created.
                    build_picker(SOURCE)
                install(SOURCE, directory, True)
                print("Frontend installed. Scan for AirDrop in DMS Settings > Plugins, enable it, and add its bar widget.")
                print("AirDrop radio readiness is separate; review backend warnings above.")
            else:
                print("Picker plan: " + ("compile and verify locally" if args.picker != "basic" and report["native_ready"] else "use the basic Qt picker recovery option"))
        elif args.action == "uninstall":
            uninstall(SOURCE, config / "DankMaterialShell/plugins", args.apply)
        else:
            if args.apply:
                from backend import find_omdrop
                result = subprocess.run([find_omdrop(home), "status", "--json"], capture_output=True, text=True, timeout=15)
                s = json.loads(result.stdout)
                if result.returncode or s.get("receiving") is not False or s.get("visible") is not False:
                    raise ValueError("Turn receiving off yourself before restoring settings")
            restore_settings(home, config, args.apply)
        if not args.apply:
            print("Dry run only. Add --apply after reviewing the paths above.")
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
