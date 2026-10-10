import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("asset_audit", ROOT / "scripts/audit-public.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class AssetAuditTests(unittest.TestCase):
    def check_image(self, name, data, expected):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / name; image.parent.mkdir(parents=True); image.write_bytes(data)
            (root / "PUBLIC_FILES.txt").write_text(name + "\n")
            with patch.object(audit, "ROOT", root), patch.object(sys, "argv", ["audit-public.py"]), contextlib.redirect_stdout(io.StringIO()):
                if expected: audit.audit()
                else:
                    with self.assertRaises(SystemExit): audit.audit()

    def test_reviewed_crop_passes(self):
        self.check_image("assets/airdrop-popout.png", (ROOT / "assets/airdrop-popout.png").read_bytes(), True)

    def test_changed_image_requires_review(self):
        self.check_image("assets/airdrop-popout.png", (ROOT / "assets/airdrop-popout.png").read_bytes() + b"unreviewed metadata", False)

    def test_unreviewed_image_rejected(self):
        self.check_image("assets/unreviewed.png", (ROOT / "assets/airdrop-popout.png").read_bytes(), False)
