import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("rollback_v020", ROOT / "scripts/rollback-v020.py")
rollback = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rollback)

class RollbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".qa")
        self.root = Path(self.temp.name)
        qa = self.root / ".qa"
        qa.mkdir()
        self.path = self.root / "component.qml"
        self.path.write_bytes(b"new")
        with tarfile.open(qa / "source.tar.gz", "w:gz") as tar:
            member = tarfile.TarInfo("component.qml")
            member.size = 3
            tar.addfile(member, io.BytesIO(b"old"))
        self.manifest = {"baseline": str(qa), "changed": {"component.qml": {
            "before": hashlib.sha256(b"old").hexdigest(), "after": hashlib.sha256(b"new").hexdigest()}}}
        (qa / "v020-update.json").write_text(json.dumps(self.manifest))
    def tearDown(self): self.temp.cleanup()
    def test_dry_run_then_restore(self):
        rollback.restore(self.root)
        self.assertEqual(self.path.read_bytes(), b"new")
        result = subprocess.CompletedProcess([], 0, json.dumps({"ok": True, "busy": False}))
        with patch.object(rollback.subprocess, "run", return_value=result):
            rollback.restore(self.root, True)
        self.assertEqual(self.path.read_bytes(), b"old")
    def test_later_edits_are_preserved(self):
        self.path.write_bytes(b"independent")
        with self.assertRaises(ValueError): rollback.restore(self.root, True)
        self.assertEqual(self.path.read_bytes(), b"independent")
    def test_active_temporary_session_refuses_restore(self):
        result = subprocess.CompletedProcess([], 0, json.dumps({"ok": True, "session": {"owned": True}}))
        with patch.object(rollback.subprocess, "run", return_value=result), self.assertRaises(ValueError):
            rollback.restore(self.root, True)
        self.assertEqual(self.path.read_bytes(), b"new")
    def test_symlink_refused(self):
        self.path.unlink()
        self.path.symlink_to("/dev/null")
        with self.assertRaises(ValueError): rollback.restore(self.root)
