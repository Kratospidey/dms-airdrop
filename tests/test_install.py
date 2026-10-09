import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("installer", ROOT / "scripts/install.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class InstallTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".qa").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".qa")
        self.plugins = Path(self.temp.name) / "plugins"
    def tearDown(self): self.temp.cleanup()
    def test_dry_run_creates_nothing(self):
        m.install(ROOT, self.plugins)
        self.assertFalse(self.plugins.exists())
    def test_reversible_symlink_only(self):
        p = m.install(ROOT, self.plugins, True)
        self.assertTrue(p.is_symlink())
        m.uninstall(ROOT, self.plugins, True)
        self.assertFalse(p.exists())
        self.assertTrue((ROOT / "plugin.json").exists())
    def test_existing_path_refused(self):
        self.plugins.mkdir()
        (self.plugins / m.ID).write_text("existing")
        with self.assertRaises(ValueError): m.install(ROOT, self.plugins, True)
        self.assertEqual((self.plugins / m.ID).read_text(), "existing")
    def test_duplicate_id_elsewhere(self):
        other = self.plugins / "different-name"
        other.mkdir(parents=True)
        (other / "plugin.json").write_text(json.dumps({"id": m.ID}))
        with self.assertRaises(ValueError): m.install(ROOT, self.plugins, True)
    def test_uninstall_foreign_path_refused(self):
        self.plugins.mkdir()
        (self.plugins / m.ID).symlink_to(self.plugins)
        with self.assertRaises(ValueError): m.uninstall(ROOT, self.plugins, True)
    def test_manifest_components_exist(self):
        manifest = json.loads((ROOT / "plugin.json").read_text())
        self.assertEqual(manifest["type"], "composite")
        self.assertEqual(manifest["requires_dms"], ">=1.6.2")
        self.assertIn("settings_write", manifest["permissions"])
        for file in [*manifest["components"].values(), manifest["settings"]]:
            self.assertTrue((ROOT / file).is_file(), file)

    def test_restore_exact_original_and_refuse_later_edits(self):
        home = Path(self.temp.name)
        config = home / "config"
        source = config / "airdrop/config.toml"
        source.parent.mkdir(parents=True)
        source.write_text('name = "New"\n')
        folder = config / "DankMaterialShell/dms-airdrop-backups"
        folder.mkdir(parents=True, mode=0o700)
        record = {"path": str(source), "existed": True, "content": 'name = "Original"\n', "mode": 0o600,
                  "last_applied_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
        (folder / "config.toml.original.json").write_text(json.dumps(record))
        m.restore_settings(home, config, False)
        self.assertEqual(source.read_text(), 'name = "New"\n')
        m.restore_settings(home, config, True)
        self.assertEqual(source.read_text(), 'name = "Original"\n')
        source.write_text('name = "Independent edit"\n')
        with self.assertRaises(ValueError): m.restore_settings(home, config, True)
        self.assertEqual(source.read_text(), 'name = "Independent edit"\n')

    def test_restore_original_absent_visibility(self):
        home = Path(self.temp.name)
        config = home / "config"
        source = config / "omdrop/visibility"
        source.parent.mkdir(parents=True)
        source.write_text("contacts\n")
        folder = config / "DankMaterialShell/dms-airdrop-backups"
        folder.mkdir(parents=True, mode=0o700)
        record = {"path": str(source), "existed": False, "content": None, "mode": 0o600,
                  "last_applied_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
        (folder / "visibility.original.json").write_text(json.dumps(record))
        m.restore_settings(home, config, True)
        self.assertFalse(source.exists())
