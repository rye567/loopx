import importlib.util
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HEALTH_PATH = ROOT / "loopx" / "tools" / "loopx_health.py"


def load_health_module():
    spec = importlib.util.spec_from_file_location("loopx_health", HEALTH_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class HealthFixture(unittest.TestCase):
    def setUp(self):
        self.health = load_health_module()
        self.tmp = Path(tempfile.mkdtemp(prefix="loopx-std-health-"))
        self.run_id = "loopx-health-v2"
        self.run_dir = self.tmp / "docs" / "loopx" / "runs" / self.run_id
        (self.run_dir / "stage-results").mkdir(parents=True)
        (self.run_dir / "artifacts").mkdir()
        self.evidence = self.run_dir / "artifacts" / "evidence.txt"
        self.evidence.write_text("本地验证证据\n", encoding="utf-8")
        (self.tmp / ".github" / "workflows").mkdir(parents=True)
        (self.tmp / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
        self._write_complete_v2_run()

    def tearDown(self):
        path = self.tmp
        shutil.rmtree(path)
        self.assertFalse(path.exists())

    def _relative(self, path):
        return str(path.relative_to(self.tmp))

    def _write_complete_v2_run(self):
        stages = self.health.STAGE_SEQUENCE[:self.health.STAGE_SEQUENCE.index("health_gate")]
        state = {
            "run_id": self.run_id,
            "contract_version": "2",
            "catalog_version": "2",
            "mode": "FULL",
            "worklist": self._relative(self.run_dir / "worklist.yml"),
            "stages": {stage: "PASS" for stage in stages},
            "mode_decision": {
                "selected_by": "user",
                "accepted_risk": {"selected_lower_than_recommended": False, "reason": ""},
            },
        }
        (self.run_dir / "worklist.yml").write_text(
            "run:\n  id: loopx-health-v2\nitems: []\n",
            encoding="utf-8",
        )
        evidence = self._relative(self.evidence)
        for stage in stages:
            result = {"stage": stage, "status": "PASS", "evidence": [evidence]}
            if stage == "development":
                result["rule_results"] = [{"rule_id": "COMMON-001", "status": "PASS", "evidence": [evidence]}]
            if stage == "test_execution":
                result["cleanup_verified"] = True
            filename = self.health.STAGE_RESULT_FILES[stage]
            (self.run_dir / "stage-results" / filename).write_text(
                json.dumps(result, ensure_ascii=False),
                encoding="utf-8",
            )
        snapshot = {
            "contract_version": "2",
            "catalog_version": "2",
            "mode": "FULL",
            "risk_tags": [],
            "rules": [{"id": "COMMON-001", "level": "required", "stages": ["development"]}],
            "stage_contracts": {},
            "thresholds": {},
            "commands": {},
            "sources": {},
        }
        payload = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        snapshot["digest"] = digest
        snapshot_path = self.run_dir / "artifacts" / "policy-snapshot.json"
        snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
        state["policy_snapshot"] = self._relative(snapshot_path)
        state["policy_snapshot_sha256"] = digest
        (self.run_dir / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


class HealthConfigTest(HealthFixture):
    def test_executes_declared_core_checks(self):
        report = self.health.execute_health(self.tmp, self.run_id, write_result=True)

        configured = self.health.load_health_config(ROOT / "loopx" / "health.yml")["core_checks"]
        names = [item.name for item in report.checks]
        self.assertEqual(report.status, self.health.PASS)
        self.assertEqual(set(names), set(configured))
        for name in configured:
            self.assertEqual(names.count(name), 1)
        self.assertTrue(report.ci_gap_declared)
        result_path = self.run_dir / "artifacts" / "health-result.json"
        written = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertEqual(written["run_id"], self.run_id)
        self.assertTrue(all({"name", "status", "evidence"}.issubset(item) for item in written["checks"]))

    def test_unknown_required_check_is_blocked(self):
        config = self.tmp / "unknown-health.yml"
        config.write_text(
            """health:
  core_required: true
  allow_auto_install: false
  core_checks:
    - unknown_required_check
""",
            encoding="utf-8",
        )
        report = self.health.execute_health(self.tmp, self.run_id, config_path=config)

        self.assertEqual(report.status, self.health.BLOCKED)
        self.assertEqual(report.checks[0].name, "unknown_required_check")
        self.assertEqual(report.checks[0].status, self.health.BLOCKED)

    def test_v1_does_not_require_v2_snapshot_or_rule_results(self):
        state_path = self.run_dir / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        for key in ("contract_version", "catalog_version", "policy_snapshot", "policy_snapshot_sha256"):
            state.pop(key, None)
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

        report = self.health.execute_health(self.tmp, self.run_id)
        names = {item.name for item in report.checks}
        self.assertFalse(names.intersection(self.health.V2_ONLY_CHECKS))
        self.assertEqual(report.status, self.health.PASS)


class HealthResultTest(unittest.TestCase):
    def setUp(self):
        self.health = load_health_module()

    def test_status_aggregation(self):
        cases = [
            ([self.health.PASS], self.health.PASS),
            ([self.health.PASS, self.health.SKIPPED], self.health.PASS_WITH_WARNINGS),
            ([self.health.PASS, self.health.CI_REQUIRED], self.health.LOCAL_INCOMPLETE_CI_REQUIRED),
            ([self.health.PASS, self.health.BLOCKED], self.health.BLOCKED),
            (["NOT_EXECUTED"], self.health.BLOCKED),
            ([self.health.SKIPPED, self.health.CI_REQUIRED], self.health.LOCAL_INCOMPLETE_CI_REQUIRED),
        ]
        for values, expected in cases:
            with self.subTest(values=values):
                self.assertEqual(self.health.aggregate_status(values), expected)


class HealthCommandTest(unittest.TestCase):
    def setUp(self):
        self.health = load_health_module()
        self.tmp = Path(tempfile.mkdtemp(prefix="loopx-std-health-command-"))

    def tearDown(self):
        path = self.tmp
        shutil.rmtree(path)
        self.assertFalse(path.exists())

    def test_safe_command_execution(self):
        calls = []

        def successful_runner(argv, **kwargs):
            calls.append((argv, kwargs))
            return subprocess.CompletedProcess(argv, 0, "token=top-secret visible-secret", "")

        success = self.health.run_project_command(
            "safe",
            {
                "argv": [sys.executable, "-c", "print('ok')"],
                "timeout_seconds": 5,
                "sensitive_values": ["visible-secret"],
            },
            self.tmp,
            command_runner=successful_runner,
        )
        self.assertEqual(success.status, self.health.PASS)
        self.assertIsInstance(calls[0][0], list)
        self.assertFalse(calls[0][1]["shell"])
        self.assertNotIn("top-secret", success.details["stdout"])
        self.assertNotIn("visible-secret", success.details["stdout"])
        self.assertIn("[REDACTED]", success.details["stdout"])

        json_secret = self.health.redact_output('{"token": "json-secret"}')
        self.assertNotIn("json-secret", json_secret)

        def nonzero_runner(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 7, "", "failed")

        failed = self.health.run_project_command(
            "failed", {"argv": ["tool"], "kind": "required"}, self.tmp, command_runner=nonzero_runner
        )
        self.assertEqual(failed.status, self.health.BLOCKED)
        self.assertEqual(failed.details["exit_code"], 7)

        def timeout_runner(argv, **kwargs):
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"], output="password=hunter2")

        timed_out = self.health.run_project_command(
            "timeout", {"argv": ["tool"], "timeout_seconds": 0.1}, self.tmp, command_runner=timeout_runner
        )
        self.assertEqual(timed_out.status, self.health.BLOCKED)
        self.assertTrue(timed_out.details["timed_out"])
        self.assertNotIn("hunter2", timed_out.details["stdout"])

        def missing_runner(argv, **kwargs):
            raise FileNotFoundError(argv[0])

        policies = {"optional": "SKIPPED", "ci_backed": "CI_REQUIRED", "required": "BLOCKED"}
        expected = {"optional": "SKIPPED", "ci_backed": "CI_REQUIRED", "required": "BLOCKED"}
        for kind, status in expected.items():
            with self.subTest(kind=kind):
                result = self.health.run_project_command(
                    kind,
                    {"argv": ["missing-loopx-tool"], "kind": kind},
                    self.tmp,
                    missing_tool_policy=policies,
                    command_runner=missing_runner,
                )
                self.assertEqual(result.status, status)
                self.assertIn("未执行自动安装", result.message)

        unsafe = self.health.run_project_command("unsafe", {"argv": "tool --flag"}, self.tmp)
        self.assertEqual(unsafe.status, self.health.BLOCKED)

        ci_only = self.health.run_project_command(
            "ci-only",
            {"argv": ["must-not-run"], "required": True, "ci_only": True},
            self.tmp,
            command_runner=lambda *args, **kwargs: self.fail("CI 命令不应在本地执行"),
        )
        self.assertEqual(ci_only.status, self.health.CI_REQUIRED)


if __name__ == "__main__":
    unittest.main()
