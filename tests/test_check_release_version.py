import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_release_version.py"


def load_check_module():
    spec = importlib.util.spec_from_file_location("check_release_version", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReleaseVersionCheckTest(unittest.TestCase):
    def setUp(self):
        self.check = load_check_module()
        self.tmp = Path(tempfile.mkdtemp(prefix="loopx-release-check-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))

    def write_manifests(self, root_version: str, loopx_version: str):
        (self.tmp / "loopx").mkdir(exist_ok=True)
        (self.tmp / "manifest.json").write_text(json.dumps({"version": root_version}), encoding="utf-8")
        (self.tmp / "loopx" / "manifest.json").write_text(json.dumps({"version": loopx_version}), encoding="utf-8")

    def test_branch_push_skips_check(self):
        ok, messages = self.check.check_release("refs/heads/main", self.tmp)
        self.assertTrue(ok)
        self.assertTrue(any("SKIP" in message for message in messages))

    def test_missing_ref_skips_check(self):
        ok, _ = self.check.check_release("", self.tmp)
        self.assertTrue(ok)

    def test_matching_tag_passes(self):
        self.write_manifests("0.2.0", "0.2.0")
        ok, messages = self.check.check_release("refs/tags/v0.2.0", self.tmp)
        self.assertTrue(ok)
        self.assertTrue(any("PASS" in message for message in messages))

    def test_tag_with_suffix_passes(self):
        self.write_manifests("0.2.0-beta.1", "0.2.0-beta.1")
        ok, _ = self.check.check_release("refs/tags/v0.2.0-beta.1", self.tmp)
        self.assertTrue(ok)

    def test_mismatched_tag_fails(self):
        self.write_manifests("0.1.1", "0.1.1")
        ok, messages = self.check.check_release("refs/tags/v0.2.0", self.tmp)
        self.assertFalse(ok)
        self.assertEqual(len([m for m in messages if "不一致" in m]), 2)

    def test_manifests_drift_fails(self):
        self.write_manifests("0.2.0", "0.1.1")
        ok, messages = self.check.check_release("refs/tags/v0.2.0", self.tmp)
        self.assertFalse(ok)
        self.assertTrue(any("两个 manifest 版本不一致" in message for message in messages))

    def test_missing_manifest_reported_not_crash(self):
        ok, messages = self.check.check_release("refs/tags/v0.2.0", self.tmp)
        self.assertFalse(ok)
        self.assertTrue(any("无法读取" in message for message in messages))


if __name__ == "__main__":
    unittest.main()
