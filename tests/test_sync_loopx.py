import importlib.util
import json
import shutil
import tempfile
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SYNC_PATH = ROOT / "loopx" / "tools" / "sync_loopx.py"


def load_sync_module():
    spec = importlib.util.spec_from_file_location("sync_loopx", SYNC_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SyncLoopxTest(unittest.TestCase):
    def setUp(self):
        self.sync = load_sync_module()
        self.tmp = Path(tempfile.mkdtemp(prefix="loopx-sync-test-"))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_all_codex_agent_toml_is_parseable(self):
        for agent in self.sync.AGENTS:
            with self.subTest(agent=agent["name"]):
                data = tomllib.loads(self.sync.codex_agent_file(agent))
                self.assertEqual(data["name"], agent["name"])
                self.assertIn("developer_instructions", data)

    def test_review_agents_do_not_get_write_tools(self):
        write_tools = {"Edit", "MultiEdit", "Write"}
        for agent in self.sync.AGENTS:
            if agent["role"] != "review":
                continue
            with self.subTest(agent=agent["name"]):
                tools = {tool.strip() for tool in agent["tools"].split(",")}
                self.assertTrue(write_tools.isdisjoint(tools))

    def test_write_agents_keep_write_tools(self):
        development = next(agent for agent in self.sync.AGENTS if agent["name"] == "quality-development-orchestrator")
        tools = {tool.strip() for tool in development["tools"].split(",")}
        self.assertTrue({"Edit", "MultiEdit", "Write"}.issubset(tools))

    def test_cleanup_only_removes_loopx_generated_quality_agents(self):
        codex_agents = self.tmp / ".codex" / "agents"
        claude_agents = self.tmp / ".claude" / "agents"
        codex_agents.mkdir(parents=True)
        claude_agents.mkdir(parents=True)

        generated = codex_agents / "quality-generated.toml"
        generated.write_text(self.sync.LOOPX_GENERATED_MARKER + "\n", encoding="utf-8")

        custom = codex_agents / "quality-custom.toml"
        custom.write_text("name = \"quality-custom\"\n", encoding="utf-8")

        claude_generated = claude_agents / "quality-generated.md"
        claude_generated.write_text(self.sync.LOOPX_GENERATED_MARKER + "\n", encoding="utf-8")

        self.sync.PROJECT = self.tmp
        self.sync.cleanup_project_quality_agents()

        self.assertFalse(generated.exists())
        self.assertFalse(claude_generated.exists())
        self.assertTrue(custom.exists())

    def test_copy_templates_includes_yaml_templates(self):
        self.sync.copy_templates(self.tmp, "assets/templates")

        self.assertTrue((self.tmp / "assets" / "templates" / "07-quality-audit.md").exists())
        self.assertTrue((self.tmp / "assets" / "templates" / "10-health-check.md").exists())
        self.assertTrue((self.tmp / "assets" / "templates" / "worklist.yml").exists())

    def test_copy_configs_includes_health_risk_and_profiles(self):
        self.sync.copy_configs(self.tmp, "assets/config")

        self.assertTrue((self.tmp / "assets" / "config" / "health.yml").exists())
        self.assertTrue((self.tmp / "assets" / "config" / "risk.yml").exists())
        self.assertTrue((self.tmp / "assets" / "config" / "project-profiles.yml").exists())

    def test_permissions_drive_generated_adapters(self):
        settings = json.loads(self.sync.claude_settings_json())
        self.assertIn("Bash(mvn compile)", settings["permissions"]["allow"])
        self.assertIn("Bash(git reset --hard:*)", settings["permissions"]["deny"])
        self.assertIn("Read(./.env)", settings["permissions"]["deny"])

        rules = self.sync.codex_rules()
        self.assertIn('pattern = ["mvn", "compile"]', rules)
        self.assertIn('pattern = ["git", "reset", "--hard"]', rules)
        self.assertIn('decision = "forbidden"', rules)

    def test_risk_policy_is_declared_in_workflow_and_assignment_agent(self):
        workflow = (ROOT / "loopx" / "workflow.md").read_text(encoding="utf-8")
        project_manager = (ROOT / "loopx" / "agents" / "project-manager.md").read_text(encoding="utf-8")

        for text in (workflow, project_manager):
            self.assertIn("assets/config/risk.yml", text)
            self.assertIn("critical_triggers", text)
            self.assertIn("score_rules", text)
            self.assertIn("thresholds", text)

    def test_state_machine_contract_is_declared(self):
        workflow = (ROOT / "loopx" / "workflow.md").read_text(encoding="utf-8")
        self.assertIn("## 阶段状态机", workflow)
        self.assertIn("stage_result", workflow)
        self.assertIn("return_to", workflow)
        self.assertIn("CHANGES_REQUIRED", workflow)
        self.assertIn("ACCEPTED_RISK", workflow)
        self.assertIn("## 写入硬门禁", workflow)

    def test_stage_templates_require_stage_result(self):
        for template in (ROOT / "loopx" / "templates").glob("*.md"):
            with self.subTest(template=template.name):
                text = template.read_text(encoding="utf-8")
                self.assertIn("stage_result", text)
                self.assertIn("return_to", text)

    def test_quality_auditor_agent_is_registered(self):
        names = {agent["name"] for agent in self.sync.AGENTS}
        self.assertIn("quality-gate-auditor", names)
        auditor = next(agent for agent in self.sync.AGENTS if agent["name"] == "quality-gate-auditor")
        self.assertEqual(auditor["phase"], "07-quality-audit")
        self.assertEqual(auditor["role"], "review")

    def test_write_project_entry_preserves_custom_content(self):
        target = self.tmp / "AGENTS.md"
        target.write_text("# Custom Rules\n\nKeep this.\n", encoding="utf-8")

        self.sync.write_project_entry(self.tmp, "AGENTS.md", "# LoopX Section\n\nGenerated.")
        self.sync.write_project_entry(self.tmp, "AGENTS.md", "# LoopX Section\n\nRegenerated.")
        text = target.read_text(encoding="utf-8")

        self.assertIn("# Custom Rules", text)
        self.assertIn(self.sync.MANAGED_SECTION_START, text)
        self.assertIn("Regenerated.", text)
        self.assertNotIn("Generated.\n" + self.sync.MANAGED_SECTION_END + "\n\n" + self.sync.MANAGED_SECTION_START, text)

    def test_project_specific_agents_source_overwrites_generated_harness(self):
        source = self.tmp / ".codex" / "loopx-project"
        source.mkdir(parents=True)
        (source / "codex-agents.md").write_text("# Project Harness\n\nOnly this.\n", encoding="utf-8")
        (self.tmp / "AGENTS.md").write_text("# Old Harness\n\n" + self.sync.MANAGED_SECTION_START + "\nstale\n" + self.sync.MANAGED_SECTION_END, encoding="utf-8")

        old_project = self.sync.PROJECT
        try:
            self.sync.PROJECT = self.tmp
            self.sync.generate_project()
        finally:
            self.sync.PROJECT = old_project

        text = (self.tmp / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("# Project Harness", text)
        self.assertNotIn(self.sync.MANAGED_SECTION_START, text)
        self.assertNotIn("# Old Harness", text)


if __name__ == "__main__":
    unittest.main()
