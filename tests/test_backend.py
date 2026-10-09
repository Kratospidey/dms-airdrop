import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("backend", ROOT / "scripts/backend.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
Backend, Error = module.Backend, module.BackendError
MAC = "aa:bb:cc:dd:ee:ff"
OFF = dict(receiving=False, visible=False, remaining=None, name="Mock", dir="/mock/Downloads",
           mode="off", reason="stopped", rx_proven=False, visibility="everyone", senders=0)


class BackendTests(unittest.TestCase):
    def setUp(self):
        qa = ROOT / ".qa"
        qa.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=qa)
        self.home = Path(self.temp.name)
        self.runtime = self.home / "runtime"
        self.runtime.mkdir(mode=0o700)
        self.source = self.home / "omdrop-plugin"
        (self.source / "bin").mkdir(parents=True)
        self.cli = self.source / "bin/omdrop"
        shutil.copyfile(ROOT / "tests/fake_omdrop.py", self.cli)
        self.cli.chmod(0o755)
        (self.home / ".local/bin").mkdir(parents=True)
        (self.home / ".local/bin/omdrop").symlink_to(self.cli)
        (self.source / "share").mkdir()
        (self.source / "share/airdrop-receiver.service").write_text("ExecStart=@PLUGIN_DIR@/bin/receiver\n")
        self.config = self.home / ".config"
        (self.config / "systemd/user").mkdir(parents=True)
        self.service = self.config / "systemd/user/airdrop-receiver.service"
        self.service.write_text("ExecStart=" + str(self.source) + "/bin/receiver\n")
        keys = self.home / ".omdrop/keys"
        keys.mkdir(parents=True)
        for name in ("certificate.self-signed.pem", "key.self-signed.pem"):
            (keys / name).write_text("TEST PLACEHOLDER, NOT AN IDENTITY")
        self.data = {"status": dict(OFF), "peers": [{"mac": MAC, "rssi": None, "name": None}]}
        self.save()
        self.systemctl = self.home / "fake-systemctl"
        self.systemctl.write_text('''#!/usr/bin/env python3
import json,sys
from pathlib import Path
d=json.loads((Path(__file__).parent/'scenario.json').read_text())
if 'cat' in sys.argv: sys.exit(0)
if d.get('service_unavailable'): sys.exit(1)
print('LoadState=loaded')
print('ActiveState='+d.get('unit_state', 'active' if d['status']['receiving'] else 'inactive'))
''')
        self.systemctl.chmod(0o755)
        self.radio = self.home / "fake-radio"
        self.radio.write_text('''#!/usr/bin/env python3
import json,sys
from pathlib import Path
d=json.loads((Path(__file__).parent/'scenario.json').read_text())
if d.get('radio_unavailable'): print('bad'); sys.exit(1)
print(json.dumps({'visible':d['status']['visible'], 'remaining':d['status']['remaining']}))
''')
        self.radio.chmod(0o755)
        self.b = Backend(home=self.home, runtime=self.runtime, config=self.config, cli=self.cli,
                         systemctl=str(self.systemctl), radio_helper=self.radio)
        # Inject fixture-owned tools at the Python constructor boundary, with
        # no production environment override that could select a fake backend.
        self.wrapper = self.home / "mock-backend.py"
        self.wrapper.write_text("import sys\nsys.path.insert(0, " + repr(str(ROOT / "scripts")) + ")\nfrom backend import Backend, main\n"
            + "sys.exit(main(Backend(home=" + repr(str(self.home)) + ", runtime=" + repr(str(self.runtime))
            + ", config=" + repr(str(self.config)) + ", cli=" + repr(str(self.cli))
            + ", systemctl=" + repr(str(self.systemctl)) + ", radio_helper=" + repr(str(self.radio)) + ")))\n")

    def tearDown(self):
        self.temp.cleanup()

    def save(self):
        (self.home / "scenario.json").write_text(json.dumps(self.data))

    def receiving(self, **values):
        self.data["status"].update(receiving=True, visible=True, mode="timed", remaining=600, **values)
        self.save()

    def file(self, name="photo.jpg"):
        path = self.home / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("mock data")
        return str(path)

    def send(self, **values):
        return self.b.operation(dict(action="send", peer=MAC, files=[self.file()], **values), "test")

    def calls(self):
        p = self.home / "calls.jsonl"
        return [json.loads(line) for line in p.read_text().splitlines()] if p.exists() else []

    def test_off_and_active_schema(self):
        self.assertFalse(self.b.snapshot()["status"]["receiving"])
        self.receiving()
        self.assertEqual(self.b.snapshot()["status"]["remaining"], 600)

    def test_unknown_visibility_is_not_false(self):
        self.data["status"]["visible"] = None
        self.save()
        self.assertFalse(self.b.snapshot()["ok"])

    def test_malformed_status(self):
        self.data["malformed"] = True
        self.save()
        self.assertFalse(self.b.snapshot()["ok"])
        self.assertEqual(self.b.snapshot()["code"], "schema")

    def test_rejects_wrong_field_types(self):
        for key, value in (("receiving", "false"), ("remaining", True), ("dir", "relative"), ("mode", "invented")):
            raw = dict(OFF, **{key: value})
            with self.subTest(key=key), self.assertRaises(Error):
                module.status_schema(raw)

    def test_missing_executable(self):
        self.b.cli = str(self.home / "absent")
        self.assertEqual(self.b.snapshot()["code"], "missing")

    def test_reads_are_bounded(self):
        start = time.monotonic()
        with self.assertRaises(Error) as e:
            self.b.run([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.15)
        self.assertEqual(e.exception.code, "timeout")
        self.assertLess(time.monotonic() - start, 2)

    def test_no_timeout_after_streams_close_early(self):
        start = time.monotonic()
        rc, _, _ = self.b.run([sys.executable, "-c", "import os,time; os.close(1); os.close(2); time.sleep(2.2)"], timeout=None)
        self.assertEqual(rc, 0)
        self.assertGreater(time.monotonic() - start, 2)

    def test_bad_job_file_does_not_break_status(self):
        self.b.prepare_runtime()
        for value in ([], ["bad"], {"state": "running", "updated": "unknown"}):
            module.atomic_json(self.b.runtime / "job.json", value)
            self.assertTrue(self.b.snapshot()["ok"])
            self.assertEqual(self.b.snapshot()["job"], {})

    def test_all_conflicting_actions_share_lock(self):
        self.receiving()
        with self.b.lock():
            for data in ({"action": "on"}, {"action": "off"}, {"action": "names"}, {"action": "name", "name": "New"}, {"action": "send", "peer": MAC, "files": [self.file()]}):
                with self.subTest(action=data["action"]), self.assertRaises(Error) as e:
                    self.b.operation(data, "other")
                self.assertEqual(e.exception.code, "busy")
        self.assertEqual(self.calls(), [])

    def test_empty_room_exit_one(self):
        self.receiving()
        self.data["peers"] = []
        self.save()
        self.assertEqual(self.b.peers(), [])

    def test_discovery_failure_is_not_empty_room(self):
        self.receiving()
        self.data.update(peers=[], peer_failure=True)
        self.save()
        with self.assertRaises(Error): self.b.peers()

    def test_named_and_unnamed_peers(self):
        self.receiving()
        self.data["peers"].append({"mac": "11:22:33:44:55:66", "rssi": -44, "name": "Test iPhone"})
        self.save()
        peers = self.b.peers()
        self.assertEqual(peers[0]["label"], "Apple device · dd:ee:ff")
        self.assertEqual(peers[1]["label"], "Test iPhone")

    def test_owl_empty_output_error_has_actionable_message(self):
        self.receiving()
        self.data["peer_unreadable"] = True
        self.save()
        with self.assertRaises(Error) as error:
            self.b.peers()
        self.assertEqual(error.exception.code, "peers")
        self.assertIn("Open AirDrop on your iPhone", str(error.exception))
        self.assertNotIn("-n", self.calls()[-1])

    def test_invalid_peer_address(self):
        with self.assertRaises(Error): module.peers_schema([{"mac": "$(touch nope)"}])

    def test_preservation_guard(self):
        self.service.write_text("custom receiver service")
        job = self.b.operation({"action": "on", "duration": "10m"}, "test")
        self.assertEqual(job["code"], "preservation")
        self.assertFalse(any(c[0] == "on" for c in self.calls()))
        self.assertEqual(self.service.read_text(), "custom receiver service")

    def test_missing_identity_blocks_start_without_reading_it(self):
        (self.home / ".omdrop/keys/key.self-signed.pem").unlink()
        self.assertEqual(self.b.operation({"action": "on"}, "test")["code"], "preservation")

    def test_unavailable_service_manager_blocks_implicit_setup(self):
        self.systemctl.write_text("#!/bin/sh\nexit 4\n")
        self.assertEqual(self.b.operation({"action": "on"}, "test")["code"], "status")
        self.assertFalse(any(c[0] == "on" for c in self.calls()))

    def test_masked_radio_and_service_failures_are_not_off(self):
        for failure in ("radio_unavailable", "service_unavailable"):
            self.data[failure] = True
            self.save()
            self.assertFalse(self.b.snapshot()["ok"])
            self.data[failure] = False

    def test_failed_receiver_is_reported(self):
        self.data["unit_state"] = "failed"
        self.save()
        self.assertEqual(self.b.snapshot()["status"]["receiver_state"], "failed")

    def test_version_change_blocks_mutation(self):
        self.data["version"] = "omdrop 0.15.0"
        self.save()
        self.assertEqual(self.b.operation({"action": "on"}, "test")["code"], "version")

    def test_receive_once_and_verified_stop(self):
        self.assertEqual(self.b.operation({"action": "on", "duration": "once"}, "a")["state"], "complete")
        self.assertEqual(self.b.status()["mode"], "once")
        self.assertEqual(self.b.operation({"action": "off"}, "b")["state"], "complete")
        self.assertFalse(self.b.status()["visible"])
        self.assertFalse(any("--force" in c for c in self.calls()))

    def test_start_failure(self):
        self.data["start_failure"] = True
        self.save()
        j = self.b.operation({"action": "on"}, "test")
        self.assertEqual(j["exit_code"], 3)
        self.assertIn("compatible Wi-Fi channel", j["message"])

    def test_success_exit_without_state_change_is_failure(self):
        self.data["unconfirmed"] = True
        self.save()
        self.assertEqual(self.b.operation({"action": "on"}, "test")["code"], "unconfirmed")
        self.receiving()
        self.assertEqual(self.b.operation({"action": "off"}, "test")["code"], "unconfirmed")

    def test_argv_spaces_unicode_newline_metacharacters_multiple_files(self):
        self.receiving()
        names = ["space photo.jpg", "画像.png", "line\nbreak.txt", "$(touch INJECTION)`hi`.txt", "-option.txt", "x" * 220 + ".txt"]
        files = [self.file(n) for n in names]
        j = self.b.operation({"action": "send", "peer": MAC, "files": files}, "test")
        self.assertEqual(j["state"], "complete")
        call = next(c for c in self.calls() if c[0] == "send")
        self.assertEqual(call, ["send", "--to", MAC, "--wait", "30", "--", *files])
        self.assertFalse((self.home / "INJECTION").exists())
        self.assertNotIn(str(self.home), (self.b.runtime / "job.json").read_text())

    def test_deleted_folder_empty_duplicate_selection(self):
        cases = [[], [str(self.home / "missing")], [str(self.home)], [self.file("a/same"), self.file("b/same")]]
        for files in cases:
            with self.subTest(files=files), self.assertRaises(Error):
                self.b.validate_request({"action": "send", "peer": MAC, "files": files})

    def test_missing_destination(self):
        with self.assertRaises(Error): self.b.validate_request({"action": "send", "files": [self.file()]})

    def test_disappeared_peer(self):
        self.receiving()
        self.data["peers"] = []
        self.save()
        self.assertEqual(self.send()["code"], "peers")
        self.assertFalse(any(c[0] == "send" for c in self.calls()))

    def test_rejected_and_timeout_exit_codes(self):
        self.receiving()
        for result, text in (("reject", "declined"), ("timeout", "did not answer")):
            self.data["send_result"] = result
            self.save()
            j = self.send()
            self.assertEqual(j["state"], "failed")
            self.assertIn(text, j["message"])

    def test_window_expiry_and_once_block_send(self):
        self.receiving()
        for mode, left in (("once", None), ("timed", 119), ("timed", None)):
            self.data["status"].update(mode=mode, remaining=left)
            self.save()
            self.assertEqual(self.send()["code"], "window")
        self.data["status"] = dict(OFF)
        self.save()
        self.assertEqual(self.send()["code"], "off")

    def test_names_only_explicit(self):
        self.receiving()
        self.assertEqual(self.b.operation({"action": "names"}, "test")["state"], "complete")
        self.assertIn(["peers", "--json", "-n"], self.calls())

    def test_long_transfer_survives_ten_seconds_and_status_poll(self):
        self.receiving()
        self.data["send_delay"] = 10.4
        self.save()
        job_id = "a" * 32
        self.b.prepare_runtime()
        request = self.b.runtime / ("request-" + job_id + ".json")
        module.atomic_json(request, {"action": "send", "peer": MAC, "files": [self.file()]})
        env = dict(os.environ, HOME=str(self.home), XDG_RUNTIME_DIR=str(self.runtime), XDG_CONFIG_HOME=str(self.config))
        proc = subprocess.Popen([sys.executable, str(self.wrapper), "worker", job_id], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            end = time.monotonic() + 5
            while time.monotonic() < end and not self.b.busy(): time.sleep(0.02)
            self.assertTrue(self.b.busy())
            self.assertFalse(request.exists())
            snap = self.b.snapshot()
            self.assertTrue(snap["ok"])
            self.assertTrue(snap["busy"])
            with self.assertRaises(Error) as e: self.b.operation({"action": "off"}, "other")
            self.assertEqual(e.exception.code, "busy")
            out, err = proc.communicate(timeout=16)
            self.assertEqual(proc.returncode, 0, err)
            self.assertEqual(self.b.snapshot()["job"]["state"], "complete")
            self.assertFalse(self.b.busy())
        finally:
            if proc.poll() is None:
                proc.terminate()
                proc.communicate(timeout=8)

    def test_stale_running_job_is_interrupted_not_success(self):
        self.b.prepare_runtime()
        module.atomic_json(self.b.runtime / "job.json", {"state": "running", "phase": "Uploading", "updated": time.time() - 30})
        self.assertEqual(self.b.snapshot()["job"]["state"], "interrupted")

    def test_cancel_worker_cleans_child_and_releases_lock(self):
        self.receiving()
        self.data["send_delay"] = 30
        self.save()
        job_id = "b" * 32
        self.b.prepare_runtime()
        module.atomic_json(self.b.runtime / ("request-" + job_id + ".json"),
                           {"action": "send", "peer": MAC, "files": [self.file()]})
        env = dict(os.environ, HOME=str(self.home), XDG_RUNTIME_DIR=str(self.runtime), XDG_CONFIG_HOME=str(self.config))
        proc = subprocess.Popen([sys.executable, str(self.wrapper), "worker", job_id], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            end = time.monotonic() + 5
            while time.monotonic() < end:
                job = module.read_json(self.b.runtime / "job.json", {})
                if job.get("phase") == "Waiting for acceptance": break
                time.sleep(0.02)
            self.assertEqual(job.get("phase"), "Waiting for acceptance")
            proc.terminate()
            proc.communicate(timeout=8)
            snap = self.b.snapshot()
            self.assertFalse(snap["busy"])
            self.assertEqual(snap["job"]["code"], "cancelled")
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()

    def test_unreadable_and_large_sparse_file(self):
        path = Path(self.file("unreadable"))
        path.chmod(0)
        try:
            with self.assertRaises(Error): self.b.validate_request({"action": "send", "peer": MAC, "files": [str(path)]})
        finally:
            path.chmod(0o600)
        large = self.home / "large.bin"
        with large.open("wb") as stream: stream.truncate(5 * 1024**3)
        self.receiving()
        job = self.b.operation({"action": "send", "peer": MAC, "files": [str(large)]}, "test")
        self.assertEqual(job["state"], "complete")

    def test_deleted_after_submission_reports_failure(self):
        self.receiving()
        data = {"action": "send", "peer": MAC, "files": [self.file()]}
        self.b.validate_request(data)
        Path(data["files"][0]).unlink()
        self.assertEqual(self.b.operation(data, "test")["code"], "files")

    def test_output_is_bounded(self):
        rc, out, err = self.b.run([sys.executable, "-c", "import sys; print('x'*600000); print('y'*600000,file=sys.stderr)"])
        self.assertEqual(rc, 0)
        self.assertLessEqual(len(out), module.MAX_OUTPUT)
        self.assertLessEqual(len(err), module.MAX_OUTPUT)

    def test_active_setting_change_refused(self):
        self.receiving()
        self.assertEqual(self.b.operation({"action": "name", "name": "New"}, "test")["code"], "busy")

    def test_bounded_duration_validation(self):
        for duration in ("forever", "0m", "61m", "-1m", "10m; touch bad"):
            with self.assertRaises(Error): self.b.validate_request({"action": "on", "duration": duration})

    def test_inspect_files_reports_total_without_backend_calls(self):
        a, b = self.file("hello 日本語.txt"), self.file("b.txt")
        result = self.b.inspect_files([a, b])
        self.assertEqual(result, {"ok": True, "count": 2, "size_label": "18 B"})
        self.assertEqual(self.calls(), [])

    def test_inspect_files_rejects_deleted_file(self):
        path = self.file(); Path(path).unlink()
        with self.assertRaises(Error): self.b.inspect_files([path])

    def test_inspect_files_rejects_directories(self):
        with self.assertRaises(Error): self.b.inspect_files([str(self.home)])

    def test_inspect_files_rejects_nonlocal_and_empty(self):
        for files in ([], ["relative.txt"], ["/tmp/a\0b"], None):
            with self.assertRaises(Error): self.b.inspect_files(files)

    def test_inspect_files_large_metadata_only(self):
        path = self.file()
        with open(path, "wb") as file: file.truncate(5 * 1024 ** 3)
        self.assertEqual(self.b.inspect_files([path])["size_label"], "5.0 GiB")

    def test_submit_uses_unique_unit_private_request_and_argv(self):
        file = self.file("space 日本語.txt")
        request = {"action": "send", "peer": MAC, "files": [file]}
        with patch.object(self.b, "run", return_value=(0, "", "")) as launch:
            result = self.b.submit(request)
        argv = launch.call_args.args[0]
        self.assertIn("--unit=dms-airdrop-operation-" + result["id"] + ".service", argv)
        self.assertIn("--property=UMask=0022", argv)
        self.assertIn("--property=KillMode=process", argv)
        self.assertIn("--property=StandardOutput=null", argv)
        self.assertNotIn(file, argv)
        self.assertEqual(argv[-2:], ["worker", result["id"]])
        path = self.b.runtime / ("request-" + result["id"] + ".json")
        self.assertEqual(module.read_json(path), request)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.b.runtime.stat().st_mode & 0o777, 0o700)
        # A second submit cannot slip through before the worker takes its lock.
        with patch.object(self.b, "run") as duplicate, self.assertRaises(Error):
            self.b.submit(request)
        duplicate.assert_not_called()
        self.assertEqual(list(self.b.runtime.glob("request-*.json")), [path])

    def test_abandoned_launch_reconciled_before_next_submit(self):
        self.b.prepare_runtime()
        path = self.b.runtime / ("request-" + "a" * 32 + ".json")
        module.atomic_json(path, {"action": "off"})
        os.utime(path, (time.time() - 60, time.time() - 60))
        with patch.object(self.b, "run", side_effect=[(0, "inactive\n", ""), (0, "", "")]):
            self.b.submit({"action": "off"})
        self.assertFalse(path.exists())

    def test_pending_live_unit_blocks_duplicate_and_keeps_request(self):
        self.b.prepare_runtime()
        path = self.b.runtime / ("request-" + "b" * 32 + ".json")
        module.atomic_json(path, {"action": "off"})
        os.utime(path, (time.time() - 60, time.time() - 60))
        with patch.object(self.b, "run", return_value=(0, "activating\n", "")), self.assertRaises(Error):
            self.b.submit({"action": "off"})
        self.assertTrue(path.exists())

    def test_failed_launch_removes_only_own_request(self):
        with patch.object(self.b, "run", return_value=(1, "", "failed")), self.assertRaises(Error):
            self.b.submit({"action": "off"})
        self.assertEqual(list(self.b.runtime.glob("request-*.json")), [])

    def test_worker_waits_for_submitter_then_claims_private_request(self):
        self.b.prepare_runtime()
        job_id = "c" * 32
        path = self.b.runtime / ("request-" + job_id + ".json")
        module.atomic_json(path, {"action": "off"})
        with self.b.lock("submit.lock"):
            child = subprocess.Popen([sys.executable, str(self.wrapper), "worker", job_id],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            time.sleep(0.2)
            self.assertIsNone(child.poll())
            self.assertTrue(path.exists())
            self.assertTrue(self.b.queued())
        output, error = child.communicate(timeout=5)
        self.assertEqual(child.returncode, 0, output + error)
        self.assertFalse(path.exists())
        self.assertEqual(module.read_json(self.b.runtime / "job.json")["state"], "complete")


if __name__ == "__main__":
    unittest.main()
