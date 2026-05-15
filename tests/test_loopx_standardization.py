import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK_PATH = ROOT / "loopx" / "tools" / "loopx_check.py"


def load_check_module():
    spec = importlib.util.spec_from_file_location("loopx_check", CHECK_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class LoopXStandardizationTest(unittest.TestCase):
    def setUp(self):
        self.check = load_check_module()

    def test_standardization_assets_pass_kit_harness(self):
        report = self.check.evaluate_kit(ROOT)
        messages = "\n".join(f"{item.name}: {item.message}" for item in report.checks)
        self.assertEqual(report.status, self.check.PASS, messages)

    def test_each_required_standard_declares_gate_language(self):
        base = ROOT / "loopx" / "standards"
        for name in self.check.REQUIRED_STANDARDS:
            with self.subTest(name=name):
                text = (base / name).read_text(encoding="utf-8").lower()
                self.assertIn("pass criteria", text)
                self.assertTrue("fail" in text or "return rules" in text)
                self.assertIn("evidence", text)

    def test_required_skills_are_small_contracts(self):
        base = ROOT / "loopx" / "skills"
        for name in self.check.REQUIRED_SKILLS:
            with self.subTest(name=name):
                text = (base / name).read_text(encoding="utf-8").lower()
                self.assertIn("purpose", text)
                self.assertIn("inputs", text)
                self.assertIn("output", text)
                self.assertIn("pass criteria", text)
                self.assertIn("failure", text)


if __name__ == "__main__":
    unittest.main()
