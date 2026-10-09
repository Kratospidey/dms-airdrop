import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import install
import preflight
import backend
import public_files


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()

    def test_version_prefixes(self):
        self.assertEqual(preflight.version("dms v1.6.2\n"), (1, 6, 2))
        self.assertEqual(preflight.version("Quickshell 0.3.1 (distribution)"), (0, 3, 1))
        self.assertIsNone(preflight.version("not a version"))

    def test_existing_local_cli_preferred(self):
        path = self.home / ".local/bin/omdrop"
        path.parent.mkdir(parents=True); path.write_text("fixture"); path.chmod(0o755)
        with patch.object(backend.shutil, "which", return_value="/other/omdrop"):
            self.assertEqual(backend.find_omdrop(self.home), str(path))

    def test_cli_on_path(self):
        with patch.object(backend.shutil, "which", return_value="/opt/example/bin/omdrop"):
            self.assertEqual(backend.find_omdrop(self.home), "/opt/example/bin/omdrop")

    def test_backend_invalid_xdg_falls_back(self):
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "relative", "XDG_RUNTIME_DIR": ""}):
            instance = backend.Backend(home=self.home)
        self.assertEqual(instance.config, self.home / ".config")
        self.assertEqual(instance.runtime_base, Path(f"/run/user/{os.getuid()}"))

    def test_duplicate_id_refused_even_with_matching_link(self):
        directory = self.home / "plugins"
        install.install(ROOT, directory, True)
        other = directory / "duplicate"; other.mkdir()
        (other / "plugin.json").write_text(json.dumps({"id": install.ID}))
        with self.assertRaises(ValueError): install.install(ROOT, directory, True)

    def test_missing_native_tools(self):
        with patch.object(preflight.shutil, "which", return_value=None):
            ok, reason = preflight.native_probe(ROOT)
        self.assertFalse(ok); self.assertIn("cmake", reason)

    def test_native_configure_failure(self):
        with patch.object(preflight.shutil, "which", return_value="/mock/tool"), patch.object(preflight, "run", side_effect=[(0, "cmake version 3.30.0"), (1, "missing KF6")]):
            ok, reason = preflight.native_probe(ROOT)
        self.assertFalse(ok); self.assertIn("KF6", reason)

    def test_frontend_missing_is_blocking(self):
        with patch.object(preflight.shutil, "which", return_value=None), patch.object(preflight, "run", return_value=(127, "")), patch.object(preflight, "wifi_info", return_value=[]):
            report = preflight.check(ROOT, native=False)
        self.assertTrue(any("dms" in x for x in report["blocking"]))
        self.assertTrue(any("qs" in x for x in report["blocking"]))
        self.assertTrue(any("Omdrop" in x for x in report["warnings"]))

    def test_missing_backend_does_not_block_frontend(self):
        def fake(argv, **kwargs):
            if argv[-1] == "version" and "dms" in argv[0]: return 0, "dms v1.6.2"
            if argv[-1] == "--version": return 0, "Quickshell 0.3.1"
            return 127, ""
        with patch.object(preflight.shutil, "which", side_effect=lambda x: "/mock/"+x), patch.object(preflight, "run", side_effect=fake), patch.object(preflight, "wifi_info", return_value=[]):
            report = preflight.check(ROOT, native=False)
        self.assertEqual(report["blocking"], [])
        self.assertTrue(any("Omdrop" in x for x in report["warnings"]))

    def test_idempotent_install_and_uninstall(self):
        directory = self.home / "config with spaces/plugins"
        target = install.install(ROOT, directory, True)
        install.install(ROOT, directory, True)
        self.assertEqual(target.resolve(), ROOT)
        install.uninstall(ROOT, directory, True)
        install.uninstall(ROOT, directory, True)
        self.assertTrue((ROOT / "plugin.json").is_file())

    def test_dangling_foreign_link_is_preserved(self):
        directory = self.home / "plugins"; directory.mkdir()
        target = directory / install.ID; target.symlink_to(self.home / "absent")
        with self.assertRaises(ValueError): install.install(ROOT, directory, True)
        self.assertTrue(target.is_symlink())

    def test_failed_build_does_not_install(self):
        report = dict(blocking=[], native_ready=True)
        import picker_build
        with patch.dict(os.environ, {"HOME":str(self.home), "XDG_CONFIG_HOME":str(self.home / "xdg")}), patch.object(sys, "argv", ["install.py", "--apply"]), patch.object(preflight, "check", return_value=report), patch.object(preflight, "print_report"), patch.object(picker_build, "build_picker", side_effect=ValueError("build failed")):
            self.assertEqual(install.main(), 1)
        self.assertFalse((self.home / "xdg/DankMaterialShell/plugins/dmsAirDrop").exists())

    def test_relative_xdg_ignored(self):
        report = dict(blocking=[], native_ready=False)
        with patch.dict(os.environ, {"HOME":str(self.home), "XDG_CONFIG_HOME":"relative-config"}), patch.object(sys, "argv", ["install.py", "--apply", "--picker", "basic"]), patch.object(preflight, "check", return_value=report), patch.object(preflight, "print_report"):
            self.assertEqual(install.main(), 0)
        self.assertTrue((self.home / ".config/DankMaterialShell/plugins/dmsAirDrop").is_symlink())

    def test_public_manifest_rejects_escape(self):
        (self.home / "PUBLIC_FILES.txt").write_text("../outside\n")
        with self.assertRaises(ValueError): public_files.public_files(self.home)

    def test_public_manifest_rejects_symlink(self):
        (self.home / "PUBLIC_FILES.txt").write_text("linked\n")
        (self.home / "linked").symlink_to(ROOT / "LICENSE")
        with self.assertRaises(ValueError): public_files.public_files(self.home)

    def test_wifi_reports_no_raw_identity(self):
        net = self.home / "net"; (net / "wifi-example/wireless").mkdir(parents=True)
        raw = "Interface wifi-example\n addr 12:34:56:78:90:ab\n ssid PRIVATE-NETWORK\n channel 44 (5220 MHz)"
        with patch.object(preflight.shutil, "which", return_value="/mock/iw"), patch.object(preflight, "run", return_value=(0, raw)):
            rows = preflight.wifi_info(net)
        result = json.dumps(rows)
        self.assertIn("5220 MHz", result)
        self.assertNotIn("PRIVATE-NETWORK", result); self.assertNotIn("12:34", result)
