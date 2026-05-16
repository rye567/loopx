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
                text = (base / name).read_text(encoding="utf-8")
                self.assertIn("通过标准", text)
                self.assertTrue("失败" in text or "返回规则" in text)
                self.assertIn("证据", text)

    def test_required_skills_are_small_contracts(self):
        base = ROOT / "loopx" / "skills"
        for name in self.check.REQUIRED_SKILLS:
            with self.subTest(name=name):
                text = (base / name).read_text(encoding="utf-8")
                self.assertIn("目的", text)
                self.assertIn("输入", text)
                self.assertIn("输出", text)
                self.assertIn("通过标准", text)
                self.assertIn("失败处理", text)


    def test_required_front_gate_schemas_are_first_class_contracts(self):
        required = {
            "interview.schema.json",
            "spec.schema.json",
            "mode.schema.json",
            "tracking.schema.json",
        }
        self.assertTrue(required.issubset(set(self.check.REQUIRED_SCHEMAS)))
        base = ROOT / "loopx" / "schemas"
        for name in required:
            with self.subTest(name=name):
                text = (base / name).read_text(encoding="utf-8")
                self.assertIn('"type": "object"', text)

    def test_front_gate_agent_docs_define_role_boundaries(self):
        required = [
            "requirement-interviewer-agent.md",
            "spec-writer-agent.md",
            "spec-reviewer-agent.md",
            "mode-selector-agent.md",
        ]
        self.assertTrue(set(required).issubset(set(self.check.REQUIRED_AGENT_DOCS)))
        base = ROOT / "loopx" / "agents"
        for name in required:
            with self.subTest(name=name):
                text = (base / name).read_text(encoding="utf-8")
                for term in ("职责", "输入", "输出", "门禁", "禁止事项"):
                    self.assertIn(term, text)
                self.assertIn("不得", text)


if __name__ == "__main__":
    unittest.main()
