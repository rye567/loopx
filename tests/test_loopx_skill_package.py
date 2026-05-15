import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOOPX = ROOT / "loopx"


class LoopxSkillPackageTest(unittest.TestCase):
    def test_skill_has_required_frontmatter(self):
        skill = LOOPX / "SKILL.md"
        self.assertTrue(skill.exists(), "loopx/SKILL.md should be the static skill entrypoint")

        text = skill.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        _, frontmatter, body = text.split("---", 2)
        fields = {}
        for line in frontmatter.strip().splitlines():
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()

        self.assertEqual(fields.get("name"), "loopx")
        description = fields.get("description", "")
        self.assertTrue(description.startswith("当用户"))
        self.assertIn("质量门", description)
        self.assertLessEqual(len(frontmatter), 1024)
        self.assertIn("# LoopX", body)
        for heading in ("## 入口", "## 必读资源", "## 执行流程", "## 状态控制器", "## 项目接入"):
            with self.subTest(heading=heading):
                self.assertIn(heading, body)

    def test_skill_frontloads_gatekeeper_rules(self):
        text = (LOOPX / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("## 不可跳过规则", text)
        self.assertIn("init --mode auto", text)
        self.assertIn("advance --to", text)
        self.assertIn("review-feedback", text)
        self.assertIn("can-write --kind business", text)
        self.assertIn("`validate PASS` 只代表结构合法", text)

    def test_skill_references_existing_resources(self):
        text = (LOOPX / "SKILL.md").read_text(encoding="utf-8")
        expected_resources = [
            "workflow.md",
            "project-harness.md",
            "agents/",
            "templates/",
            "schemas/",
            "health.yml",
            "risk.yml",
            "project-profiles.yml",
            "tools/loopx_controller.py",
        ]

        for resource in expected_resources:
            with self.subTest(resource=resource):
                self.assertIn(resource, text)
                self.assertTrue((LOOPX / resource).exists())

    def test_required_skill_resources_exist(self):
        self.assertGreaterEqual(len(list((LOOPX / "agents").glob("*.md"))), 9)
        self.assertTrue((LOOPX / "templates" / "10-health-check.md").exists())
        self.assertTrue((LOOPX / "templates" / "worklist.yml").exists())
        self.assertTrue((LOOPX / "schemas" / "state.schema.json").exists())
        self.assertTrue((LOOPX / "schemas" / "stage-result.schema.json").exists())
        self.assertTrue((LOOPX / "health.yml").exists())
        self.assertTrue((LOOPX / "risk.yml").exists())
        self.assertTrue((LOOPX / "project-profiles.yml").exists())
        self.assertTrue((LOOPX / "tools" / "loopx_controller.py").exists())

    def test_sync_and_installer_artifacts_are_removed(self):
        removed_paths = [
            ROOT / "install.py",
            ROOT / "install.cmd",
            ROOT / "install.sh",
            ROOT / "uninstall.py",
            ROOT / "uninstall.cmd",
            ROOT / "uninstall.sh",
            LOOPX / "tools" / "sync_loopx.py",
            LOOPX / "sync.sh",
            LOOPX / "codex-agents.md",
            LOOPX / "permissions.yml",
            LOOPX / "bin" / "loopx",
            LOOPX / "bin" / "loopx-sync",
        ]

        for path in removed_paths:
            with self.subTest(path=path):
                self.assertFalse(path.exists())

    def test_manifests_describe_git_maintained_skill_package(self):
        root_manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        loopx_manifest = json.loads((LOOPX / "manifest.json").read_text(encoding="utf-8"))

        for manifest in (root_manifest, loopx_manifest):
            self.assertNotIn("install", manifest)
            self.assertNotIn("syncCommand", manifest)
            self.assertNotIn("targets", manifest)
            self.assertIn("skill", manifest["description"].lower())
            self.assertIn("git", manifest["description"].lower())

    def test_docs_do_not_advertise_sync_or_install_commands(self):
        docs = [
            ROOT / "README.md",
            LOOPX / "README.md",
        ]
        forbidden = [
            "loopx-sync",
            "install.py",
            "uninstall.py",
            "~/.loopx",
            "~/.codex/agents",
            "~/.claude/agents",
            ".codex/loopx-project",
            "同步器",
            "中立源",
        ]

        for doc in docs:
            text = doc.read_text(encoding="utf-8")
            for phrase in forbidden:
                with self.subTest(doc=doc.name, phrase=phrase):
                    self.assertNotIn(phrase, text)

    def test_workflow_uses_controller_script_not_wrapper_command(self):
        workflow = (LOOPX / "workflow.md").read_text(encoding="utf-8")

        self.assertIn("python tools/loopx_controller.py init", workflow)
        self.assertIn("python tools/loopx_controller.py validate", workflow)
        self.assertNotIn("loopx init", workflow)
        self.assertNotIn("loopx status", workflow)
        self.assertNotIn("loopx validate", workflow)


if __name__ == "__main__":
    unittest.main()
