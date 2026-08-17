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
        for phrase in ("质量门", "门禁", "闸门"):
            self.assertNotIn(phrase, description)
        self.assertLessEqual(len(frontmatter), 1024)
        self.assertIn("# LoopX", body)
        for heading in ("## 入口", "## 必读资源", "## 执行流程", "## 状态控制器", "## 项目接入"):
            with self.subTest(heading=heading):
                self.assertIn(heading, body)
        self.assertLessEqual(len(text.splitlines()), 75)

    def test_skill_frontloads_gatekeeper_rules(self):
        text = (LOOPX / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("## 不可跳过规则", text)
        self.assertIn("init --mode auto", text)
        self.assertIn("advance --to", text)
        self.assertIn("fail-review", text)
        self.assertIn("claim-stage", text)
        self.assertIn("close-repair", text)
        self.assertIn("confirm-stage --stage requirement_interview", text)
        self.assertIn("can-write --kind business", text)
        self.assertIn("docs/loopx/<date>-<slug>/", text)
        self.assertIn("`validate PASS` 只代表结构合法", text)
        self.assertIn("返工任务", text)
        for phrase in ("质量门", "门禁", "闸门"):
            self.assertNotIn(phrase, text)

    def test_confirmation_docs_match_the_two_stage_contract(self):
        test_review = (LOOPX / "templates" / "05-test-review.md").read_text(encoding="utf-8")
        release_readiness = (LOOPX / "templates" / "11-release-readiness.md").read_text(encoding="utf-8")
        agent_docs = {
            name: (LOOPX / "agents" / name).read_text(encoding="utf-8")
            for name in ("test-reviewer.md", "code-reviewer.md", "test-runner.md")
        }

        for text in (test_review, release_readiness):
            self.assertNotIn("NEED_HUMAN", text)
            self.assertNotIn("confirm-stage", text)
            self.assertIn("user_confirmation_required: false", text)

        for text in agent_docs.values():
            self.assertIn("自动进入", text)
            self.assertNotIn("等待用户确认", text)

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
            "standards/catalog.yml",
            "tools/loopx_controller.py",
        ]

        for resource in expected_resources:
            with self.subTest(resource=resource):
                self.assertIn(resource, text)
                self.assertTrue((LOOPX / resource).exists())

    def test_required_skill_resources_exist(self):
        self.assertGreaterEqual(len(list((LOOPX / "agents").glob("*.md"))), 9)
        self.assertTrue((LOOPX / "skills" / "compound-capture-skill.md").exists())
        self.assertTrue((LOOPX / "templates" / "13-compound-capture.md").exists())
        self.assertTrue((LOOPX / "schemas" / "compound-learning.schema.json").exists())
        self.assertTrue((LOOPX / "templates" / "10-health-check.md").exists())
        self.assertTrue((LOOPX / "templates" / "worklist.yml").exists())
        self.assertTrue((LOOPX / "schemas" / "state.schema.json").exists())
        self.assertTrue((LOOPX / "schemas" / "stage-result.schema.json").exists())
        self.assertTrue((LOOPX / "health.yml").exists())
        self.assertTrue((LOOPX / "risk.yml").exists())
        self.assertTrue((LOOPX / "project-profiles.yml").exists())
        self.assertTrue((LOOPX / "standards" / "catalog.yml").exists())
        self.assertTrue((LOOPX / "templates" / "loopx-policy.yml").exists())
        for name in (
            "standard-catalog.schema.json",
            "project-policy.schema.json",
            "solution.schema.json",
            "test-plan.schema.json",
            "development-evidence.schema.json",
            "quality-result.schema.json",
            "performance-result.schema.json",
            "security-result.schema.json",
        ):
            with self.subTest(schema=name):
                self.assertTrue((LOOPX / "schemas" / name).exists())
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

        for manifest, base in ((root_manifest, ROOT), (loopx_manifest, LOOPX)):
            resources = manifest.get("resources", {})
            self.assertTrue(resources.get("standards"))
            self.assertTrue(resources.get("schemas"))
            for group in ("standards", "schemas"):
                for resource in resources[group]:
                    with self.subTest(resource=resource):
                        self.assertTrue((base / resource).exists())
            self.assertTrue((base / resources["policyTemplate"]).exists())

    def test_readmes_describe_rules_and_structured_artifacts(self):
        english = (ROOT / "README.md").read_text(encoding="utf-8")
        chinese = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
        package = (LOOPX / "README.md").read_text(encoding="utf-8")
        self.assertIn("versioned rule catalog", english)
        self.assertIn("structured solution", english)
        self.assertIn("版本化规则目录", chinese)
        self.assertIn("方案、测试、开发、质量、性能和安全产物", chinese)
        self.assertIn("standards/catalog.yml", package)
        self.assertIn("templates/loopx-policy.yml", package)

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

    def test_workflow_requires_project_docs_loopx_stage_document_directory(self):
        workflow = (LOOPX / "workflow.md").read_text(encoding="utf-8")

        self.assertIn("docs/loopx/<date>-<slug>/", workflow)
        self.assertIn("docs/loopx/runs/<run_id>/", workflow)

    def test_workflow_documents_compound_capture_paths(self):
        workflow = (LOOPX / "workflow.md").read_text(encoding="utf-8")

        self.assertIn("python tools/loopx_controller.py compound", workflow)
        self.assertIn("docs/loopx/runs/<run_id>/artifacts/compound-capture.md", workflow)
        self.assertIn("docs/loopx/solutions/<category>/<slug>.md", workflow)
        self.assertNotIn("`.loopx" "/knowledge", workflow)

    def test_controller_entrypoint_is_thin_facade(self):
        entrypoint = LOOPX / "tools" / "loopx_controller.py"
        core = LOOPX / "tools" / "loopx_controller_core.py"
        contracts = LOOPX / "tools" / "loopx_controller_contracts.py"
        io_helpers = LOOPX / "tools" / "loopx_controller_io.py"
        yaml_helpers = LOOPX / "tools" / "loopx_controller_yaml.py"
        artifact_helpers = LOOPX / "tools" / "loopx_controller_artifacts.py"
        state_helpers = LOOPX / "tools" / "loopx_controller_state.py"
        flow_helpers = LOOPX / "tools" / "loopx_controller_flow.py"
        validation_helpers = LOOPX / "tools" / "loopx_controller_validation.py"
        repair_helpers = LOOPX / "tools" / "loopx_controller_repair.py"
        release_helpers = LOOPX / "tools" / "loopx_controller_release.py"
        text = entrypoint.read_text(encoding="utf-8")

        self.assertTrue(core.exists(), "controller implementation should live outside the CLI facade")
        self.assertTrue(contracts.exists(), "process contracts should be split from command orchestration")
        self.assertTrue(io_helpers.exists(), "file and schema helpers should be split from command orchestration")
        self.assertTrue(yaml_helpers.exists(), "YAML/worklist helpers should be split from the controller core")
        self.assertTrue(artifact_helpers.exists(), "artifact rendering helpers should be split from the controller core")
        for helper in (state_helpers, flow_helpers, validation_helpers, repair_helpers, release_helpers):
            with self.subTest(helper=helper.name):
                helper_text = helper.read_text(encoding="utf-8")
                self.assertTrue(helper_text.startswith("#!/usr/bin/env python3\n\"\"\""))
                self.assertIn("# ", helper_text, "split Python helpers should explain non-obvious process rules")
        self.assertLessEqual(len(text.splitlines()), 80)
        self.assertLessEqual(len(core.read_text(encoding="utf-8").splitlines()), 900)
        self.assertIn("loopx_controller_core", text)


if __name__ == "__main__":
    unittest.main()
