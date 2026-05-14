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

        self.assertTrue((self.tmp / "assets" / "templates" / "09-health-check.md").exists())
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


if __name__ == "__main__":
    unittest.main()
