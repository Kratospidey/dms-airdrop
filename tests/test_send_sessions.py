"""Lifecycle tests use an isolated fake Omdrop, never the real radio."""
import json
import time
import unittest
from unittest.mock import patch

import test_backend as fixtures
Error, MAC, OFF = fixtures.Error, fixtures.MAC, fixtures.OFF


class SendSessionTests(unittest.TestCase):
    # Reuse only fixture helpers, not the original tests.
    tearDown = fixtures.BackendTests.tearDown
    save = fixtures.BackendTests.save
    receiving = fixtures.BackendTests.receiving
    file = fixtures.BackendTests.file
    send = fixtures.BackendTests.send
    calls = fixtures.BackendTests.calls

    def setUp(self):
        fixtures.BackendTests.setUp(self)
        self.scheduled = []
        self.cancelled = []
        self.b.schedule_session_cleanup = self.scheduled.append
        self.b.cancel_session_timer = self.cancelled.append
        self.b.incoming_busy = lambda: False
        self.b.window_fingerprint = lambda: str(json.loads((self.home / "scenario.json").read_text()).get("generation", 0))

    def prepare(self):
        return self.b.operation({"action": "prepare-send"}, "prepare")

    def mutations(self):
        return [c for c in self.calls() if c[0] in ("on", "off", "send")]

    def change(self, **fields):
        self.data = json.loads((self.home / "scenario.json").read_text())
        self.data.update(fields)
        self.save()

    def test_off_prepares_finite_owned_session_and_timer(self):
        self.assertEqual(self.prepare()["state"], "complete")
        s = self.b.snapshot()
        self.assertTrue(s["session"]["owned"])
        self.assertEqual(s["status"]["remaining"], 3600)
        self.assertEqual(self.mutations(), [["on", "60m"]])
        self.assertEqual(self.scheduled, [s["session"]["token"]])
        self.assertAlmostEqual(s["session"]["expires_at"], time.time() + 300, delta=2)

    def test_inspect_or_cancel_before_accept_never_starts_radio(self):
        self.b.inspect_files([self.file()])
        self.b.snapshot()
        self.b.expire_session("a" * 32)
        self.assertEqual(self.mutations(), [])

    def test_changed_deadline_during_start_is_not_claimed(self):
        receiving = dict(OFF, receiving=True, visible=True, mode="timed", remaining=600)
        with patch.object(self.b, "status", side_effect=[OFF.copy(), receiving]):
            self.assertEqual(self.prepare()["code"], "ownership")
        self.assertEqual(self.b.session_record(), {})
        self.assertEqual(self.scheduled, [])

    def test_existing_receiving_is_reused_without_claim_or_deadline_change(self):
        self.receiving()
        self.assertEqual(self.prepare()["state"], "complete")
        self.assertEqual(self.b.session_record(), {})
        self.assertEqual(self.send()["state"], "complete")
        self.assertTrue(self.b.status()["receiving"])
        self.assertEqual(self.b.status()["remaining"], 600)
        self.assertEqual([c[0] for c in self.mutations()], ["send"])

    def test_receive_once_is_preserved_and_send_refused(self):
        self.receiving()
        self.data["status"].update(mode="once", remaining=None)
        self.save()
        self.assertEqual(self.prepare()["code"], "window")
        self.assertEqual(self.send()["code"], "window")
        self.assertEqual(self.mutations(), [])

    def test_success_reuses_owned_session_without_restart_and_cleans_up(self):
        self.prepare()
        self.assertEqual(self.send()["state"], "complete")
        self.assertEqual([c[:2] for c in self.mutations() if c[0] != "send"], [["on", "60m"], ["off"]])
        self.assertFalse(self.b.status()["visible"])
        self.assertFalse(self.b.session_record()["owned"])
        self.assertNotIn("--force", str(self.calls()))

    def test_reject_and_timeout_cleanup_with_useful_error(self):
        for result, expected in (("reject", "declined"), ("timeout", "in time")):
            with self.subTest(result=result):
                self.prepare()
                self.change(send_result=result)
                job = self.send()
                self.assertEqual(job["state"], "failed")
                self.assertIn(expected, job["message"])
                self.assertFalse(self.b.status()["visible"])

    def test_disappeared_device_cleans_up_and_allows_retry(self):
        self.prepare()
        self.change(peers=[])
        self.assertEqual(self.send()["code"], "peers")
        self.assertFalse(self.b.status()["visible"])
        self.assertEqual(self.prepare()["state"], "complete")

    def test_no_peers_is_recoverable_then_cancel(self):
        self.prepare()
        self.change(peers=[])
        self.assertEqual(self.b.peers(), [])
        token = self.b.session_record()["token"]
        self.assertEqual(self.b.operation({"action": "cleanup-send", "token": token}, "cancel")["state"], "complete")
        self.assertFalse(self.b.status()["visible"])

    def test_abandonment_expiry_and_late_token_are_idempotent(self):
        self.prepare()
        token = self.b.session_record()["token"]
        self.b.expire_session("0" * 32)
        self.assertTrue(self.b.status()["visible"])
        self.b.expire_session(token)
        self.b.expire_session(token)
        self.assertEqual(self.mutations().count(["off"]), 1)

    def test_external_extension_is_never_stopped_or_extended(self):
        self.prepare()
        self.change(generation=100)
        self.assertFalse(self.b.snapshot()["session"]["owned"])
        self.assertEqual(self.send()["state"], "complete")
        self.assertTrue(self.b.status()["visible"])
        self.assertNotIn(["off"], self.mutations())
        self.assertEqual(self.mutations().count(["on", "60m"]), 1)

    def test_external_change_during_transfer_preserves_window(self):
        self.prepare()
        self.change(change_during_send=True)
        self.assertEqual(self.send()["state"], "complete")
        self.assertTrue(self.b.status()["receiving"])
        self.assertNotIn(["off"], self.mutations())

    def test_external_send_blocks_cleanup(self):
        self.prepare()
        with patch.object(self.b, "external_sends", return_value=True):
            self.b.expire_session(self.b.session_record()["token"])
        self.assertTrue(self.b.status()["visible"])
        self.assertIn("transfer", self.b.session_record()["message"])

    def test_incoming_connection_prevents_automatic_stop(self):
        self.prepare()
        with patch.object(self.b, "incoming_busy", return_value=True):
            self.b.expire_session(self.b.session_record()["token"])
        self.assertTrue(self.b.status()["visible"])
        self.assertIn("incoming connection", self.b.session_record()["message"])

    def test_unknown_incoming_probe_is_not_permission_to_stop(self):
        with patch.object(self.b, "run", side_effect=Error("ss unavailable")):
            self.assertTrue(fixtures.Backend.incoming_busy(self.b))

    def test_manual_receiving_relinquishes_ownership(self):
        self.prepare()
        token = self.b.session_record()["token"]
        self.b.operation({"action": "on", "duration": "30m"}, "manual")
        self.b.expire_session(token)
        self.assertTrue(self.b.status()["visible"])
        self.assertEqual(self.b.status()["remaining"], 1800)
        self.assertFalse(self.b.session_record()["owned"])

    def test_cleanup_failure_is_not_false_off_or_failed_transfer(self):
        self.prepare()
        self.change(off_failure=True)
        job = self.send()
        self.assertEqual(job["state"], "complete")
        self.assertIn("cleanup_warning", job)
        self.assertTrue(self.b.snapshot()["status"]["visible"])
        self.assertEqual(self.b.session_record()["phase"], "cleanup-failed")

    def test_expired_window_is_truthful_and_does_not_restart(self):
        self.prepare()
        self.change(status=OFF.copy())
        self.assertEqual(self.b.snapshot()["session"]["phase"], "expired")
        self.assertEqual(self.send()["code"], "off")
        self.assertEqual(self.mutations(), [["on", "60m"]])

    def test_timer_failure_closes_verified_temporary_window(self):
        with patch.object(self.b, "schedule_session_cleanup", side_effect=Error("timer unavailable", "cleanup")):
            self.assertEqual(self.prepare()["code"], "cleanup")
        self.assertFalse(self.b.status()["visible"])

    def test_unverifiable_ownership_never_stops(self):
        self.prepare()
        with patch.object(self.b, "window_fingerprint", side_effect=Error("unknown", "ownership")):
            self.b.expire_session(self.b.session_record()["token"])
        self.assertTrue(self.b.status()["visible"])
        self.assertFalse(self.b.session_record()["owned"])

    def test_cleanup_under_operation_lock_is_rejected(self):
        self.prepare()
        with self.b.lock(), self.assertRaises(Error):
            self.b.operation({"action": "cleanup-send", "token": self.b.session_record()["token"]}, "duplicate")
        self.assertTrue(self.b.status()["visible"])

    def test_fingerprint_detects_deadline_and_window_replacement(self):
        Backend = fixtures.Backend
        self.b.radio_state = self.home / "radio-state"
        self.b.radio_state.mkdir()
        for name, value in (("owl.pid", "123"), ("supervisor.pid", "456"), ("until", "99999")):
            (self.b.radio_state / name).write_text(value)
        window = self.runtime / "omdrop/window"
        window.parent.mkdir()
        window.write_text("not read")
        fields = "InvocationID=" + "a"*32 + "\nActiveState=active\nNextElapseUSecMonotonic=1h\nExecStart=watch --window 10m\n"
        with patch.object(self.b, "run", return_value=(0, fields, "")):
            first = Backend.window_fingerprint(self.b)
            (self.b.radio_state / "until").write_text("100000")
            self.assertNotEqual(first, Backend.window_fingerprint(self.b))
            second = Backend.window_fingerprint(self.b)
            window.write_text("changed")
            self.assertNotEqual(second, Backend.window_fingerprint(self.b))

    def test_expiry_launch_is_finite_unprivileged_and_contains_no_paths(self):
        Backend = fixtures.Backend
        with patch.object(self.b, "run", return_value=(0, "", "")) as run:
            Backend.schedule_session_cleanup(self.b, "a"*32)
        argv = run.call_args.args[0]
        self.assertIn("--on-active=300s", argv)
        self.assertIn("--user", argv)
        self.assertEqual(argv[-2:], ["expire-session", "a"*32])
