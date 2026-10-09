#!/usr/bin/env python3
"""Omdrop 0.14.1 adapter. No shell commands, automatic setup or radio recovery.

Read commands are short-lived. Mutations are finite transient user services;
only the explicit `submit` entry point can create one. Tests inject fake tools
through Backend's constructor, never a production environment override.
"""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import uuid

UNIT_PREFIX = "dms-airdrop-operation-"
MAC = re.compile(r"(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\Z", re.I)
MAX_OUTPUT = 256 * 1024


def find_omdrop(home=None):
    """Keep the upstream per-user install preferred; also support PATH installs."""
    local = Path(home or Path.home()) / ".local/bin/omdrop"
    if local.is_file() and os.access(local, os.X_OK):
        return str(local)
    found = shutil.which("omdrop")
    return str(Path(found).absolute()) if found else str(local)


def xdg_path(name, fallback):
    value = os.environ.get(name, "")
    return Path(value) if value and Path(value).is_absolute() else Path(fallback)


class BackendError(Exception):
    def __init__(self, message, code="backend", exit_code=None):
        super().__init__(message)
        self.code, self.exit_code = code, exit_code


def emit(value):
    print(json.dumps(value, ensure_ascii=True), flush=True)


def read_json(path, default=None):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def atomic_json(path, value):
    fd, name = tempfile.mkstemp(prefix=".airdrop-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, ensure_ascii=True)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def status_schema(raw):
    if not isinstance(raw, dict):
        raise BackendError("Omdrop returned an invalid status object.", "schema")
    for key in ("receiving", "rx_proven"):
        if type(raw.get(key)) is not bool:
            raise BackendError("Omdrop returned an incomplete status.", "schema")
    if raw.get("visible") is not None and type(raw["visible"]) is not bool:
        raise BackendError("Omdrop returned invalid visibility.", "schema")
    if "visible" not in raw or "remaining" not in raw:
        raise BackendError("Omdrop returned an incomplete status.", "schema")
    left = raw["remaining"]
    if left is not None and (type(left) is not int or left < 0):
        raise BackendError("Omdrop returned an invalid countdown.", "schema")
    if raw.get("mode") not in ("off", "timed", "once", "forever"):
        raise BackendError("Omdrop returned an unknown window mode.", "schema")
    if raw["receiving"] and raw["mode"] == "off":
        raise BackendError("Omdrop returned an inconsistent receiver state.", "schema")
    if raw.get("visibility") not in ("everyone", "contacts"):
        raise BackendError("Omdrop returned an unknown audience.", "schema")
    if not isinstance(raw.get("dir"), str) or not raw["dir"].startswith("/"):
        raise BackendError("Omdrop did not report a valid download folder.", "schema")
    if raw.get("name") is not None and not isinstance(raw["name"], str):
        raise BackendError("Omdrop returned an invalid device name.", "schema")
    return {k: raw.get(k) for k in ("receiving", "visible", "remaining", "mode",
            "name", "dir", "reason", "rx_proven", "visibility", "senders")}


def peers_schema(raw):
    if not isinstance(raw, list) or len(raw) > 256:
        raise BackendError("Omdrop returned an invalid device list.", "schema")
    peers, seen = [], set()
    for p in raw:
        if not isinstance(p, dict) or not isinstance(p.get("mac"), str) or not MAC.fullmatch(p["mac"]):
            raise BackendError("Omdrop returned an invalid device address.", "schema")
        if p.get("name") is not None and not isinstance(p["name"], str):
            raise BackendError("Omdrop returned an invalid device name.", "schema")
        mac = p["mac"].lower()
        if mac not in seen:
            peers.append({"mac": mac, "name": (p.get("name") or "")[:120],
                          "label": (p.get("name") or "Apple device · " + mac[-8:])[:120]})
            seen.add(mac)
    return peers


def explain(text, fallback="AirDrop could not complete the request."):
    """Map known complaints; never echo logs, file paths or identity details."""
    t = text.lower()
    if "declin" in t or "reject" in t:
        return "The recipient declined the transfer."
    if "cancel" in t:
        return "The transfer was cancelled."
    if "still sending" in t:
        return "AirDrop is busy sending. Wait for the transfer to finish."
    if "channel" in t or "mhz" in t:
        return "AirDrop requires a compatible Wi-Fi channel (6, 44 or 149)."
    if "not connected" in t or "isn't connected" in t:
        return "Wi-Fi is disconnected. Reconnect before trying AirDrop."
    if "bluetooth" in t or re.search(r"\bble\b", t):
        return "Bluetooth wake-up failed. Open AirDrop on the recipient and retry."
    if "no device" in t or "not in the peer table" in t or "no peer" in t:
        return "The device is no longer available. Open its AirDrop sheet and refresh."
    if "could not read the peer table" in t:
        return "Nearby devices could not be checked. Open AirDrop on your iPhone and refresh."
    if "upload" in t or "the transfer failed" in t:
        return "The upload failed. Check the connection and try again."
    if "never opened" in t or "never answered" in t or "timed out" in t or "timeout" in t:
        return "The device did not answer in time. Open its AirDrop sheet and retry."
    if "polkit" in t or "not authorized" in t or "authentication" in t:
        return "AirDrop could not obtain permission to operate the radio."
    if "firewall" in t:
        return "Incoming connections may be blocked by the firewall."
    if "receiver would not start" in t or "radio" in t:
        return "The AirDrop radio or receiver could not start. Check diagnostics."
    if "no such file" in t or "not a file" in t or "cannot be read" in t:
        return "A selected file is missing or cannot be read. Choose the files again."
    return fallback


class Backend:
    def __init__(self, home=None, runtime=None, config=None, cli=None, systemctl="systemctl", radio_helper="/usr/lib/omdrop/omdrop-discoverable", radio_state="/run/omdrop-owl"):
        self.home = Path(home or Path.home())
        self.config = Path(config) if config else xdg_path("XDG_CONFIG_HOME", self.home / ".config")
        self.runtime_base = Path(runtime) if runtime else xdg_path("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
        self.runtime = self.runtime_base / "dms-airdrop"
        self.cli = str(cli or find_omdrop(self.home))
        self.systemctl = systemctl
        self.radio_helper = str(radio_helper)
        self.radio_state = Path(radio_state)
        self.lock_fd = None
        self.child = None

    def prepare_runtime(self):
        self.runtime.mkdir(mode=0o700, parents=True, exist_ok=True)
        s = self.runtime.lstat()
        if not stat.S_ISDIR(s.st_mode) or s.st_uid != os.getuid() or s.st_mode & 0o077:
            raise BackendError("AirDrop's private runtime folder is not secure.", "runtime")

    @contextlib.contextmanager
    def lock(self, name="operation.lock", wait=False):
        self.prepare_runtime()
        fd = os.open(self.runtime / name, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
            except BlockingIOError:
                raise BackendError("AirDrop is busy. Wait for the current operation.", "busy")
            yield fd
        finally:
            os.close(fd)

    def busy(self):
        try:
            with self.lock():
                return False
        except BackendError as e:
            if e.code == "busy":
                return True
            raise

    def queued(self):
        for path in self.runtime.glob("request-*.json"):
            try:
                if time.time() - path.stat().st_mtime < 30:
                    return True
            except FileNotFoundError:
                pass  # A worker has just claimed it.
        return False

    def reconcile_requests(self):
        # Called only under submit.lock. A delayed worker must take this same
        # lock before claiming its request, so removing an abandoned request
        # cannot race with that worker starting a stale operation.
        for path in self.runtime.glob("request-*.json"):
            job_id = path.stem.removeprefix("request-")
            if not re.fullmatch(r"[0-9a-f]{32}", job_id):
                raise BackendError("An invalid pending request needs review.", "runtime")
            if time.time() - path.stat().st_mtime < 30:
                raise BackendError("AirDrop is starting an operation. Please wait.", "busy")
            rc, out, _ = self.run([self.systemctl, "--user", "show",
                UNIT_PREFIX + job_id + ".service", "--property=ActiveState", "--value"])
            if rc or out.strip() not in ("inactive", "failed"):
                raise BackendError("A previous launch is still pending. Check status before retrying.", "busy")
            path.unlink()

    def run(self, argv, timeout=12, on_line=None):
        """Drain both channels with bounded buffers. No plugin timeout for send.

        The lock descriptor is inherited by the CLI, so a worker crash cannot
        make a still-running command appear unlocked. Omdrop owns its send
        process groups and cleans them up on TERM.
        """
        try:
            proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
                    pass_fds=(() if self.lock_fd is None else (self.lock_fd,)))
        except FileNotFoundError:
            raise BackendError("An AirDrop dependency is missing. Check Omdrop in ~/.local/bin or PATH and run install.sh check.", "missing")
        except OSError:
            raise BackendError("AirDrop could not launch the requested program.", "launch")
        self.child = proc
        output = {"stdout": bytearray(), "stderr": bytearray()}
        pending = {"stdout": bytearray(), "stderr": bytearray()}
        deadline = time.monotonic() + timeout if timeout is not None else None
        try:
            with selectors.DefaultSelector() as sel:
                for channel in output:
                    sel.register(getattr(proc, channel), selectors.EVENT_READ, channel)
                while sel.get_map():
                    if deadline is not None and time.monotonic() >= deadline:
                        raise BackendError("AirDrop did not answer in time. Check the current status before retrying.", "timeout", 124)
                    for key, _ in sel.select(0.2):
                        data = os.read(key.fileobj.fileno(), 65536)
                        if not data:
                            sel.unregister(key.fileobj)
                            continue
                        ch = key.data
                        output[ch].extend(data)
                        del output[ch][:-MAX_OUTPUT]
                        pending[ch].extend(data)
                        while b"\n" in pending[ch]:
                            line, _, rest = pending[ch].partition(b"\n")
                            pending[ch] = bytearray(rest)
                            if on_line:
                                on_line(ch, line.decode("utf-8", "replace"))
                        del pending[ch][:-MAX_OUTPUT]
                try:
                    rc = proc.wait(timeout=max(0.001, deadline - time.monotonic()) if deadline else None)
                except subprocess.TimeoutExpired:
                    raise BackendError("AirDrop did not answer in time. Check its status before retrying.", "timeout", 124)
            return rc, *(output[k].decode("utf-8", "replace") for k in ("stdout", "stderr"))
        finally:
            if proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                # Any ordinary children which ignored TERM stay in this group.
                # Omdrop itself traps TERM to clean its separate send group.
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            proc.stdout.close()
            proc.stderr.close()
            self.child = None

    def cli_run(self, args, timeout=12, on_line=None):
        return self.run([self.cli, *args], timeout, on_line)

    def status(self):
        rc, out, err = self.cli_run(["status", "--json"])
        if rc:
            raise BackendError(explain(err, "AirDrop status is unavailable."), "status", rc)
        try:
            result = status_schema(json.loads(out))
        except ValueError:
            raise BackendError("Omdrop returned unreadable status. Try refreshing.", "schema")
        # Omdrop 0.14.1 suppresses errors from systemctl and the radio helper,
        # which otherwise turns a failed probe into a false Off indication.
        rc, unit, _ = self.run([self.systemctl, "--user", "show", "airdrop-receiver.service",
                              "--property=LoadState", "--property=ActiveState"])
        fields = dict(line.split("=", 1) for line in unit.splitlines() if "=" in line)
        if rc or fields.get("LoadState") != "loaded" or fields.get("ActiveState") not in ("active", "inactive", "failed"):
            raise BackendError("The receiver state could not be confirmed. Check AirDrop status again.", "status")
        if result["receiving"] != (fields["ActiveState"] == "active"):
            raise BackendError("The receiver changed state while checking. Refresh AirDrop status.", "status")
        rc, out, _ = self.run([self.radio_helper, "status", "--json"])
        try:
            radio = json.loads(out)
        except ValueError:
            raise BackendError("The radio returned unreadable status. Its state is unknown.", "status")
        if rc or not isinstance(radio, dict) or type(radio.get("visible")) is not bool:
            raise BackendError("The radio status could not be confirmed. Its state is unknown.", "status")
        if radio["visible"] != result["visible"]:
            raise BackendError("The radio changed state while checking. Refresh AirDrop status.", "status")
        result["receiver_state"] = fields["ActiveState"]
        left = radio.get("remaining")
        if type(left) is int and left >= 0 and result["remaining"] is not None:
            result["remaining"] = min(left, result["remaining"])
        return result

    def external_sends(self):
        # No cleanup or reads of marker contents (which may contain device names).
        folder = self.runtime_base / "omdrop/sends"
        try:
            markers = list(folder.iterdir()) if folder.exists() else []
            for marker in markers:
                if not marker.name.isdigit():
                    continue
                try:
                    cmd = Path(f"/proc/{marker.name}/cmdline").read_bytes().split(b"\0")
                except FileNotFoundError:
                    continue
                except PermissionError:
                    return True  # Unknown process ownership is not permission to stop.
                if any(Path(os.fsdecode(arg)).name == "omdrop" for arg in cmd[:3]) and b"send" in cmd:
                    return True
            return False
        except OSError:
            return True

    def snapshot(self):
        result = {"ok": True, "checked_at": time.time(), "busy": self.busy() or self.queued(),
                  "external_send": self.external_sends()}
        job = read_json(self.runtime / "job.json", {})
        if not isinstance(job, dict):
            job = {}
        if job and (job.get("state") not in ("running", "complete", "failed", "interrupted") or not isinstance(job.get("updated"), (int, float))):
            job = {}
        if job and job.get("state") == "running" and not result["busy"]:
            if job.get("phase") == "Queued" and time.time() - job.get("updated", 0) < 15:
                result["busy"] = True
            else:
                job = dict(job, state="interrupted", phase="Interrupted",
                           message="The previous operation was interrupted. Check AirDrop status before retrying.")
        result["job"] = job
        try:
            result["status"] = self.status()
            result["session"] = self.session_summary(result["status"])
        except BackendError as e:
            result.update(ok=False, error=str(e), code=e.code)
        return result

    def peers(self, names=False):
        status = self.status()
        if status["visible"] is not True:
            raise BackendError("Choose files to start looking for nearby devices.", "off")
        rc, out, err = self.cli_run(["peers", "--json", *(["-n"] if names else [])], 90 if names else 15)
        try:
            peers = peers_schema(json.loads(out))
        except ValueError:
            if rc:
                raise BackendError(explain(err, "Nearby devices could not be checked. Try refreshing."), "peers", rc)
            raise BackendError("Omdrop returned an unreadable device list.", "schema")
        if rc and not (rc == 1 and peers == [] and "No devices found yet" in err):
            raise BackendError(explain(err, "Nearby devices could not be checked."), "peers", rc)
        return peers

    def preservation_check(self):
        rc, out, _ = self.cli_run(["version"])
        if rc or out.strip() != "omdrop 0.14.1":
            raise BackendError("This adapter requires the audited Omdrop 0.14.1. Re-audit before changing versions.", "version")
        source = Path(self.cli).resolve().parent.parent
        target = self.config / "systemd/user/airdrop-receiver.service"
        try:
            expected = (source / "share/airdrop-receiver.service").read_text().replace("@PLUGIN_DIR@", str(source)).rstrip("\n")
            if target.read_text().rstrip("\n") != expected:
                raise BackendError("Omdrop would replace the existing receiver service. Startup is blocked to preserve it.", "preservation")
            dropin = target.parent / (target.name + ".d/10-download-dir.conf")
            if dropin.exists() and "ReadWritePaths=%h/.opendrop" in dropin.read_text().splitlines():
                raise BackendError("Omdrop would update a receiver drop-in. The operation is blocked.", "preservation")
        except OSError:
            raise BackendError("The existing receiver service could not be verified. Automatic setup is disabled.", "preservation")
        rc, _, _ = self.run([self.systemctl, "--user", "cat", "airdrop-receiver.service"])
        if rc:
            raise BackendError("The user service manager cannot find the existing receiver. Automatic setup is disabled.", "preservation")
        for name in ("certificate.self-signed.pem", "key.self-signed.pem"):
            path = self.home / ".omdrop/keys" / name
            if not path.is_file() or not os.access(path, os.R_OK):
                raise BackendError("The existing AirDrop identity is unavailable. Automatic identity creation is disabled.", "preservation")

    def validate_request(self, data):
        if not isinstance(data, dict) or data.get("action") not in ("on", "off", "send", "prepare-send", "cleanup-send", "names", "name", "everyone"):
            raise BackendError("Unknown AirDrop operation.", "request")
        action = data["action"]
        if action == "cleanup-send" and not re.fullmatch(r"[0-9a-f]{32}", str(data.get("token", ""))):
            raise BackendError("Invalid temporary session identifier.", "request")
        if action == "on":
            duration = data.get("duration", "10m")
            if duration != "once" and not re.fullmatch(r"(?:[1-9]|[1-5][0-9]|60)m", str(duration)):
                raise BackendError("Choose a receiving window between 1 and 60 minutes.", "request")
        if action == "name":
            name = data.get("name", "")
            if not isinstance(name, str) or not name.strip() or len(name) > 63 or re.search(r"[/\\\x00-\x1f\x7f]", name):
                raise BackendError("Use a name of 1–63 characters without slashes or control characters.", "request")
        if action == "send":
            if not isinstance(data.get("peer"), str) or not MAC.fullmatch(data["peer"]):
                raise BackendError("Select an available device before sending.", "request")
            self.inspect_files(data.get("files"))
        return data

    def window_fingerprint(self):
        """Read public lifecycle metadata only, never identity file contents.

        Omdrop has no compare-and-stop API. Exact invocation/deadline equality
        is a conservative guard; independent CLI mutations can still race it.
        """
        values = {}
        for unit, props in (("omdrop-watch.service", ("InvocationID", "ActiveState", "ExecStart")),
                            ("omdrop-window.timer", ("InvocationID", "ActiveState", "NextElapseUSecMonotonic"))):
            rc, out, _ = self.run([self.systemctl, "--user", "show", unit, *["--property=" + p for p in props]])
            fields = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
            if rc or fields.get("ActiveState") != "active" or not re.fullmatch(r"[0-9a-f]{32}", fields.get("InvocationID", "")):
                raise BackendError("Temporary receiving ownership could not be verified. Use Turn Off when finished.", "ownership")
            if unit.endswith("timer") and fields.get("NextElapseUSecMonotonic") in (None, "", "0", "n/a", "infinity"):
                raise BackendError("The temporary window deadline could not be verified.", "ownership")
            values[unit] = fields
        try:
            for name in ("owl.pid", "supervisor.pid", "until"):
                path = self.radio_state / name
                data = path.read_text().strip()
                if not data.isdecimal() or len(data) > 20: raise ValueError()
                info = path.stat()
                values[name] = [data, info.st_ino, info.st_mtime_ns]
            info = (self.runtime_base / "omdrop/window").stat()
            values["window"] = [info.st_ino, info.st_mtime_ns]
        except (OSError, ValueError):
            raise BackendError("Temporary receiving ownership could not be verified. Use Turn Off when finished.", "ownership")
        return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()

    def session_record(self):
        value = read_json(self.runtime / "send-session.json", {})
        return value if isinstance(value, dict) else {}

    def save_session(self, record):
        atomic_json(self.runtime / "send-session.json", record)

    def session_summary(self, status):
        record = self.session_record()
        if not record: return {}
        summary = {k: record[k] for k in ("token", "owned", "phase", "expires_at", "message") if k in record}
        if record.get("owned"):
            if not status["receiving"] and not status["visible"]:
                summary.update(owned=False, phase="expired", message="The temporary session ended. Choose files again to retry.")
            else:
                try: same = record.get("fingerprint") == self.window_fingerprint()
                except BackendError: same = False
                if not same:
                    summary.update(owned=False, phase="preserved", message="Receiving changed or could not be verified. It will remain active; use Turn Off when finished.")
        return summary

    def schedule_session_cleanup(self, token):
        # A finite user timer, using this same adapter and its existing locks.
        # It owns no radio process and requires no installation or privilege.
        rc, _, _ = self.run(["systemd-run", "--user", "--quiet", "--collect",
            "--unit=dms-airdrop-expire-" + token, "--on-active=300s", "--timer-property=AccuracySec=1s",
            "--property=UMask=0022", "--property=StandardOutput=null", "--property=StandardError=null",
            "--setenv=XDG_RUNTIME_DIR=" + str(self.runtime_base),
            "--setenv=XDG_CONFIG_HOME=" + str(self.config), "--", sys.executable,
            str(Path(__file__).resolve()), "expire-session", token], 15)
        if rc: raise BackendError("The discovery cleanup timer could not start. Temporary receiving will be closed.", "cleanup")

    def cancel_session_timer(self, token):
        if re.fullmatch(r"[0-9a-f]{32}", str(token)):
            try: self.run([self.systemctl, "--user", "stop", "dms-airdrop-expire-" + token + ".timer"], 10)
            except BackendError: pass  # Idempotent expiry still checks the token.

    def incoming_busy(self):
        # The audited receiver binds 8771. An accepted TCP connection can be
        # an incoming upload; uncertainty is never permission to stop it.
        try:
            rc, out, _ = self.run(["ss", "-Hnt", "state", "connected", "( sport = :8771 )"], 5)
            return rc != 0 or bool(out.strip())
        except BackendError:
            return True

    def prepare_send(self, status):
        if status["receiving"] and status["visible"]:
            if status["mode"] == "once":
                raise BackendError("Receive Once may close during a send. Finish or turn off that window, then choose files again.", "window")
            return  # Preserve all existing receiving windows and their deadline.
        if status["receiving"] or status["visible"] is not False:
            raise BackendError("AirDrop is changing state. Check status before trying again.", "status")
        self.preservation_check()
        # A five-minute independent idle timer bounds discovery. The normal
        # Omdrop window has a 60-minute hard cap, allowing a send to continue
        # without restarting its receiver watcher or extending any deadline.
        rc, _, err = self.cli_run(["on", "60m"], 180)
        verified = self.status()
        if rc or not verified["receiving"] or verified["visible"] is not True or verified["mode"] != "timed":
            raise BackendError(explain(err, "Discovery could not start. Check AirDrop status and retry."), "prepare", rc)
        if type(verified.get("remaining")) is not int or not 3500 <= verified["remaining"] <= 3600:
            raise BackendError("The discovery deadline changed or could not be confirmed. Receiving is preserved; use Turn Off when finished.", "ownership")
        record = {"token": uuid.uuid4().hex, "owned": True, "phase": "discovering",
                  "expires_at": time.time() + 300, "fingerprint": self.window_fingerprint()}
        self.save_session(record)
        try: self.schedule_session_cleanup(record["token"])
        except BackendError:
            self.cleanup_send(record["token"])
            raise

    def cleanup_send(self, token):
        record = self.session_record()
        if not record.get("owned") or record.get("token") != token: return
        status = self.status()
        if not status["receiving"] and status["visible"] is False:
            record.update(owned=False, phase="closed", message="")
        else:
            if self.external_sends() or self.incoming_busy():
                record.update(message="A transfer or incoming connection may still be active. Receiving remains on; use Turn Off after it finishes.")
                self.save_session(record)
                return
            try: same = record.get("fingerprint") == self.window_fingerprint()
            except BackendError: same = False
            if not same:
                record.update(owned=False, phase="preserved", message="Receiving changed or could not be verified. It remains active; use Turn Off when finished.")
            else:
                self.preservation_check()
                # Check again immediately before ordinary off. Never force.
                if record["fingerprint"] != self.window_fingerprint() or self.incoming_busy():
                    raise BackendError("Receiving changed before cleanup. Use Turn Off when finished.", "ownership")
                record.update(phase="cleaning")
                self.save_session(record)
                rc, _, err = self.cli_run(["off"], 180)
                verified = self.status()
                if rc or verified["receiving"] or verified["visible"] is not False:
                    record.update(phase="cleanup-failed", message="Temporary receiving is still active or unconfirmed. Use Turn Off when finished.")
                    self.save_session(record)
                    raise BackendError(explain(err, record["message"]), "cleanup", rc)
                record.update(owned=False, phase="closed", message="")
        self.save_session(record)
        self.cancel_session_timer(token)

    def prepare_owned_transfer(self, status):
        record = self.session_record()
        if not record.get("owned"): return status
        if record.get("fingerprint") != self.window_fingerprint():
            record.update(owned=False, phase="preserved", message="Receiving was changed independently; its deadline will be preserved.")
            self.save_session(record)
            return status
        record.update(phase="sending")
        self.save_session(record)
        return status

    def expire_session(self, token):
        if not re.fullmatch(r"[0-9a-f]{32}", str(token)):
            raise BackendError("Invalid session identifier.", "request")
        # Wait behind an already-running worker; never time out or cancel send.
        with self.lock("submit.lock", wait=True), self.lock() as fd:
            self.lock_fd = fd
            try: self.cleanup_send(token)
            finally: self.lock_fd = None

    def inspect_files(self, files):
        """Read metadata only; no requests, units, history, or radio activity."""
        if not isinstance(files, list) or not 1 <= len(files) <= 256:
            raise BackendError("Select between 1 and 256 files.", "files")
        basenames, total = set(), 0
        for f in files:
            if not isinstance(f, str) or "\x00" in f or not os.path.isabs(f):
                raise BackendError("Choose local files with the file picker.", "files")
            try:
                info = Path(f).stat()
            except OSError:
                raise BackendError("A selected file is missing or cannot be read. Choose the files again.", "files")
            if not stat.S_ISREG(info.st_mode) or not os.access(f, os.R_OK):
                raise BackendError("A selected file is missing or cannot be read. Choose the files again.", "files")
            name = Path(f).name
            if name in basenames:
                raise BackendError("Two selected files have the same name. Rename one or send them separately.", "files")
            basenames.add(name)
            total += info.st_size
        size = float(total)
        unit = "B"
        for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB"):
            if size < 1024 or unit == "EiB": break
            size /= 1024
        label = f"{total} B" if unit == "B" else f"{size:.1f} {unit}"
        return {"ok": True, "count": len(files), "size_label": label}

    def backup_settings(self, action):
        # Only mutable non-secret configuration; never identities or certificates.
        root = self.config / "DankMaterialShell/dms-airdrop-backups"
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if root.is_symlink() or root.stat().st_uid != os.getuid() or root.stat().st_mode & 0o077:
            raise BackendError("AirDrop's settings backup directory is not private.", "backup")
        source = self.config / "airdrop/config.toml" if action == "name" else self.config / "omdrop/visibility"
        target = root / ("config.toml.original.json" if action == "name" else "visibility.original.json")
        if not target.exists():
            atomic_json(target, {"path": str(source), "existed": source.exists(),
                                 "content": source.read_text() if source.exists() else None,
                                 "mode": stat.S_IMODE(source.stat().st_mode) if source.exists() else 0o600})
        return source, target

    def record_applied_setting(self, source, backup):
        record = read_json(backup)
        record["last_applied_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest() if source.exists() else None
        atomic_json(backup, record)

    def operation(self, data, job_id):
        if not isinstance(data, dict):
            raise BackendError("Invalid operation request.", "request")
        with self.lock() as fd:
            self.lock_fd = fd
            job = {"id": job_id, "action": data.get("action", "unknown"), "state": "running",
                   "phase": "Checking", "count": len(data["files"]) if isinstance(data.get("files"), list) else 0,
                   "destination": "Apple device · " + data["peer"][-8:] if isinstance(data.get("peer"), str) else ""}
            def update(**fields):
                job.update(fields, updated=time.time())
                atomic_json(self.runtime / "job.json", job)
            update()
            action = data.get("action")
            terminal = {}
            try:
                self.validate_request(data)
                if self.external_sends():
                    raise BackendError("Another Omdrop transfer is in progress. Wait for it to finish.", "busy")
                s = self.status()
                action = data["action"]
                if action in ("on", "off"):
                    self.preservation_check()
                    previous = self.session_record()
                    if previous.get("owned"):
                        previous.update(owned=False, phase="manual", message="")
                        self.save_session(previous)
                        self.cancel_session_timer(previous.get("token"))
                    update(phase="Starting" if action == "on" else "Stopping")
                    rc, out, err = self.cli_run(["on", data.get("duration", "10m")] if action == "on" else ["off"], 180)
                    if rc:
                        raise BackendError(explain(err), "command", rc)
                    verified = self.status()
                    expected = action == "on"
                    if verified["receiving"] is not expected or verified["visible"] is not expected:
                        raise BackendError("The requested state was not confirmed. Check AirDrop status before retrying.", "unconfirmed")
                elif action == "prepare-send":
                    update(phase="Looking for nearby devices")
                    self.prepare_send(s)
                elif action == "cleanup-send":
                    update(phase="Finishing sending session")
                    self.cleanup_send(data["token"])
                elif action == "send":
                    if not s["receiving"] or s["visible"] is not True:
                        raise BackendError("The discovery session ended. Choose files again to retry.", "off")
                    update(phase="Preparing to send")
                    s = self.prepare_owned_transfer(s)
                    if s["mode"] not in ("timed", "forever") or (s["mode"] == "timed" and (s["remaining"] is None or s["remaining"] < 120)):
                        raise BackendError("Choose a longer timed receiving window before sending. Receive Once can stop during a transfer.", "window")
                    update(phase="Finding device")
                    fresh = self.peers()
                    if not any(p["mac"] == data["peer"].lower() for p in fresh):
                        raise BackendError("The selected device disappeared. Refresh nearby devices and try again.", "peers")
                    update(phase="Waiting for recipient…")
                    def phase(ch, line):
                        if line == "Asking them to accept it...":
                            update(phase="Waiting for acceptance")
                        elif line == "They accepted. Sending...":
                            update(phase="Uploading")
                    rc, out, err = self.cli_run(["send", "--to", data["peer"], "--wait", "30", "--", *data["files"]], None, phase)
                    if rc:
                        raise BackendError(explain(err + "\n" + out, "The transfer failed. Check the recipient and try again."), "send", rc)
                elif action == "names":
                    update(phase="Asking devices for names")
                    peers = self.peers(True)
                    update(peers=peers)
                elif action in ("name", "everyone"):
                    if s["receiving"] or s["visible"] is not False:
                        raise BackendError("Turn AirDrop off before changing these settings. A receiver restart could interrupt an incoming transfer.", "busy")
                    source, backup = self.backup_settings(action)
                    argv = ["name", data["name"]] if action == "name" else ["visibility", "everyone"]
                    rc, _, err = self.cli_run(argv, 20)
                    self.record_applied_setting(source, backup)
                    verified = self.status()
                    matches = verified["name"] == data["name"] if action == "name" else verified["visibility"] == "everyone"
                    # visibility's final `receiving && ... || true` currently returns 0;
                    # verify the actual setting regardless of the exit code.
                    if rc or not matches:
                        raise BackendError(explain(err, "The setting change was not confirmed."), "unconfirmed", rc)
                terminal = dict(state="complete", phase="Complete", message="Files sent successfully." if action == "send" else "Done.", exit_code=0)
            except BackendError as e:
                terminal = dict(state="failed", phase="Failed", message=str(e), code=e.code, exit_code=e.exit_code)
            except Exception:
                terminal = dict(state="failed", phase="Failed", message="AirDrop encountered an unexpected error. Refresh its status.", code="internal")
            finally:
                if action == "send":
                    record = self.session_record()
                    if record.get("owned"):
                        update(phase="Finishing sending session")
                        try: self.cleanup_send(record.get("token"))
                        except BackendError as e:
                            record = self.session_record()
                            record.update(phase="cleanup-failed", message="Temporary receiving may still be active. Use Turn Off when finished.")
                            self.save_session(record)
                            terminal["cleanup_warning"] = str(e)
                update(**terminal)
                self.lock_fd = None
            return job

    def submit(self, data):
        data = self.validate_request(data)
        with self.lock("submit.lock"):
            if self.busy():
                raise BackendError("AirDrop is busy. Wait for the current operation.", "busy")
            self.reconcile_requests()
            # Unique units accommodate OWL's existing root-owned background
            # processes, which outlive `on`. Locks plus a pending reservation
            # prevent duplicates across both the launch gap and shell reloads.
            job_id = uuid.uuid4().hex
            request = self.runtime / ("request-" + job_id + ".json")
            atomic_json(request, data)
            queued_job = {"id": job_id, "action": data["action"], "state": "running",
                          "phase": "Queued", "updated": time.time(),
                          "count": len(data.get("files", [])), "destination": ""}
            atomic_json(self.runtime / "job.json", queued_job)
            # OWL inherits this mask through pkexec and publishes non-secret
            # radio PID/deadline files for unprivileged status readers. A 0077
            # mask breaks its contract. Our request/job files use mkstemp (0600)
            # inside an explicitly private 0700 runtime directory independently.
            argv = ["systemd-run", "--user", "--quiet", "--collect", "--service-type=exec",
                    "--unit=" + UNIT_PREFIX + job_id + ".service",
                    "--property=KillMode=process", "--property=UMask=0022", "--property=StandardOutput=null",
                    "--property=StandardError=null", "--property=TimeoutStopSec=10s",
                    "--setenv=XDG_RUNTIME_DIR=" + str(self.runtime_base),
                    "--setenv=XDG_CONFIG_HOME=" + str(self.config),
                    "--", sys.executable, str(Path(__file__).resolve()), "worker", job_id]
            try:
                rc, _, _ = self.run(argv, 15)
            except BackendError:
                # A timed-out launch may have succeeded. Keep its private request
                # for the worker; reconciliation must decide, never auto-retry.
                raise BackendError("The operation could not be confirmed. Refresh status before retrying.", "launch")
            if rc:
                request.unlink(missing_ok=True)
                atomic_json(self.runtime / "job.json", dict(queued_job, state="failed",
                    phase="Failed", updated=time.time(), message="The operation service could not start.", exit_code=rc))
                raise BackendError("AirDrop is busy or the user service could not start. Refresh status before retrying.", "launch", rc)
            return {"ok": True, "id": job_id}

    def diagnostics(self):
        rc, out, _ = self.cli_run(["doctor", "--json"])
        if rc:
            raise BackendError("Omdrop diagnostics could not be read.", "diagnostics", rc)
        doctor = json.loads(out)
        rc, out, _ = self.run([self.radio_helper, "probe", "--json"])
        if rc:
            raise BackendError("The OWL backend probe could not be read.", "diagnostics", rc)
        probe = json.loads(out)
        for report in (doctor, probe):
            if not isinstance(report, dict) or not isinstance(report.get("missing"), list) or any(not isinstance(i, dict) or not isinstance(i.get("say"), str) for i in report["missing"]):
                raise BackendError("The backend returned invalid diagnostics.", "schema")
        issues = []
        for item in doctor.get("missing", []):
            if item.get("id") == "hardware" and probe.get("backend") == "owl":
                continue
            issues.append(explain(item.get("say", ""), "Omdrop reports a missing prerequisite: " + str(item.get("id", "unknown"))))
        for item in probe.get("missing", []):
            issues.append(explain(item.get("say", ""), "OWL reports a missing prerequisite: " + str(item.get("id", "unknown"))))
        try:
            self.preservation_check()
        except BackendError as e:
            issues.append(str(e))
        return {"ok": True, "issues": issues, "backend": probe.get("backend", "unknown"),
                "note": "The legacy Broadcom-only doctor check is ignored for OWL. This check does not test incoming firewall traffic or Bluetooth wake-up."}


def main(backend=None):
    backend = backend or Backend()
    def terminate(signum, frame):
        raise BackendError("The operation was cancelled or the session ended.", "cancelled", 130)
    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    try:
        command = sys.argv[1] if len(sys.argv) > 1 else "status"
        if command == "status":
            emit(backend.snapshot())
        elif command == "peers":
            emit({"ok": True, "peers": backend.peers()})
        elif command == "inspect-files":
            emit(backend.inspect_files(json.loads(sys.argv[2])))
        elif command == "diagnostics":
            emit(backend.diagnostics())
        elif command == "expire-session":
            backend.expire_session(sys.argv[2])
            emit({"ok": True})
        elif command == "submit":
            emit(backend.submit(json.loads(sys.argv[2])))
        elif command == "worker":
            job_id = sys.argv[2]
            if not re.fullmatch(r"[0-9a-f]{32}", job_id):
                raise BackendError("Invalid operation identifier.", "request")
            backend.prepare_runtime()
            with backend.lock("submit.lock", wait=True):
                path = backend.runtime / ("request-" + job_id + ".json")
                data = read_json(path)
                path.unlink(missing_ok=True)  # selected paths leave disk before execution
                job = backend.operation(data, job_id)
            return 0 if job["state"] == "complete" else 1
        else:
            raise BackendError("Unknown helper command.", "request")
        return 0
    except BackendError as e:
        emit({"ok": False, "error": str(e), "code": e.code, "exit_code": e.exit_code})
    except (ValueError, OSError, IndexError):
        emit({"ok": False, "error": "AirDrop could not read the requested data.", "code": "data"})
    return 1


if __name__ == "__main__":
    sys.exit(main())
