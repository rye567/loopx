import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "loopx" / "tools"
CONTROLLER = TOOLS / "loopx_controller.py"


def load_controller():
    spec = importlib.util.spec_from_file_location("loopx_controller_v2", CONTROLLER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class V2Fixture(unittest.TestCase):
    def setUp(self):
        self.backend_patch = mock.patch.dict(os.environ, {"LOOPX_STATE_BACKEND": "project"})
        self.backend_patch.start()
        self.addCleanup(self.backend_patch.stop)
        self.controller = load_controller()
        self.root = Path(tempfile.mkdtemp(prefix=f"loopx-std-evidence-{uuid.uuid4().hex[:8]}-"))
        self.run_id = f"loopx-std-{uuid.uuid4().hex[:10]}"

    def tearDown(self):
        root = self.root
        shutil.rmtree(root)
        self.assertFalse(root.exists())

    @property
    def run_dir(self):
        return self.root / "docs" / "loopx" / "runs" / self.run_id

    def init(self, mode="LIGHT", risk_tags=None):
        args = [
            "init",
            "验证 LoopX v2 结构化证据",
            "--run-id",
            self.run_id,
            "--mode",
            mode,
        ]
        if risk_tags:
            args.extend(["--risk-tags", *risk_tags])
        args.extend(["--project", str(self.root)])
        out = io.StringIO()
        self.assertEqual(self.controller.main(args, stdout=out), 0, out.getvalue())
        return json.loads((self.run_dir / "state.json").read_text(encoding="utf-8"))

    def write_text(self, relative, text="证据\n"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return relative

    def write_json(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        return relative

    def evidence_path(self):
        return self.write_text(f"docs/loopx/runs/{self.run_id}/artifacts/check.log")

    def document_path(self, name="solution.md"):
        return self.write_text(f"docs/loopx/{self.run_id}/{name}", "# 已审核文档\n\n内容完整。\n")

    def quality_attributes(self, evidence):
        return {
            name: {
                "status": "APPLICABLE",
                "approach": f"已验证 {name}",
                "reason": "",
                "evidence": [evidence],
            }
            for name in (
                "simplicity",
                "module_boundaries",
                "security",
                "performance",
                "extensibility",
                "compatibility",
                "reliability",
                "observability",
            )
        }

    def solution_artifact(self, evidence=None, document=None, rule_results=None, work_items=None):
        evidence = evidence or self.evidence_path()
        document = document or self.document_path()
        rule_results = rule_results or [{
            "rule_id": "COMMON-EVIDENCE-001",
            "status": "PASS",
            "evidence": [evidence],
            "reason": "",
        }]
        work_items = work_items or [{
            "id": "W1",
            "title": "实现结构化证据",
            "risk_tags": [],
            "owner_agent": "development",
            "read_scope": ["loopx/tools"],
            "write_scope": ["loopx/tools"],
            "dependencies": [],
            "validation": ["python3 -m unittest tests.test_loopx_evidence"],
        }]
        return {
            "artifact_type": "solution",
            "artifact_version": "1",
            "run_id": self.run_id,
            "stage": "solution_design",
            "document": document,
            "requirement_ids": ["AC-001"],
            "rule_results": rule_results,
            "decisions": [{
                "id": "D1",
                "requirement_ids": ["AC-001"],
                "summary": "沿用现有控制器",
                "rationale": "保持兼容并减少变更面",
                "alternatives": ["另建流程引擎"],
            }],
            "impact": {
                "modules": ["loopx/tools"],
                "contracts": ["stage-result"],
                "data": [],
                "configuration": ["catalog.yml"],
                "dependencies": [],
            },
            "quality_attributes": self.quality_attributes(evidence),
            "performance_targets": [],
            "rollback": {
                "strategy": "恢复旧控制器路径",
                "steps": ["恢复 v1 分派"],
                "validation": ["运行 v1 回归测试"],
                "reason": "",
            },
            "verification_refs": [evidence],
            "work_items": work_items,
        }

    def write_solution(self, artifact=None, filename="solution.json"):
        artifact = artifact or self.solution_artifact()
        relative = f"docs/loopx/runs/{self.run_id}/artifacts/{filename}"
        self.write_json(relative, artifact)
        return relative

    def rule_result(self, rule_id, evidence):
        return {"rule_id": rule_id, "status": "PASS", "evidence": [evidence], "reason": ""}

    def build_test_plan_artifact(self, evidence, document, rule_ids):
        return {
            "artifact_type": "test_plan",
            "artifact_version": "1",
            "run_id": self.run_id,
            "stage": "test_design",
            "document": document,
            "requirement_ids": ["AC-001"],
            "rule_results": [
                self.rule_result("TEST-MAPPING-001", evidence),
                self.rule_result("TEST-CLEANUP-002", evidence),
            ],
            "mappings": [{
                "requirement_id": "AC-001",
                "rule_ids": list(rule_ids),
                "test_case_ids": ["TC-001"],
            }],
            "cases": [{
                "id": "TC-001",
                "covers": ["AC-001"],
                "risk_tags": ["core_state_transition"],
                "preconditions": ["FULL v2 运行已初始化"],
                "data_setup": {"run_id_strategy": "uuid", "records": ["临时运行目录"]},
                "execution": {"entrypoint": "python3 -m unittest", "steps": ["执行完整流程测试"]},
                "assertions": ["全部阶段通过", "工作项已解决"],
                "cleanup": {"steps": ["退出临时目录"], "verification": ["临时目录不存在"]},
                "expected_result": "PASS",
            }],
            "environment": {"local": ["Python 3"], "ci_required": [], "manual": ["用户确认"]},
        }

    def development_artifact(self, evidence, document):
        return {
            "artifact_type": "development_evidence",
            "artifact_version": "1",
            "run_id": self.run_id,
            "stage": "development",
            "document": document,
            "requirement_ids": ["AC-001"],
            "rule_results": [self.rule_result("COMMON-EVIDENCE-001", evidence)],
            "changed_files": ["loopx/tools/example.py"],
            "write_scope": ["loopx/tools"],
            "dependency_changes": [],
            "acceptance_mapping": [{
                "requirement_id": "AC-001",
                "files": ["loopx/tools/example.py"],
                "tests": ["tests.test_loopx_evidence"],
            }],
            "commands": [{
                "argv": ["python3", "-m", "unittest"],
                "status": "PASS",
                "exit_code": 0,
                "evidence": [evidence],
                "ci_required": False,
            }],
            "residual_risks": [],
        }

    def quality_artifact(self, evidence, document):
        return {
            "artifact_type": "quality_result",
            "artifact_version": "1",
            "run_id": self.run_id,
            "stage": "quality_audit",
            "document": document,
            "requirement_ids": ["AC-001"],
            "rule_results": [self.rule_result("COMMON-EVIDENCE-001", evidence)],
            "unresolved_items": [],
            "ci_gaps": [],
            "accepted_risks": [],
            "diff_scope": {
                "allowed": ["loopx/tools"],
                "actual": ["loopx/tools/example.py"],
                "outside": [],
            },
        }

    def controller_command(self, *args, expected=0):
        out = io.StringIO()
        code = self.controller.main([*args, "--project", str(self.root)], stdout=out)
        self.assertEqual(code, expected, out.getvalue())
        return out.getvalue()

    def record_solution(self, artifact_path, item="W1"):
        out = io.StringIO()
        code = self.controller.main([
            "record-stage",
            "--run-id",
            self.run_id,
            "--stage",
            "solution_design",
            "--status",
            "PASS",
            "--artifact",
            f"solution={artifact_path}",
            "--item",
            item,
            "--project",
            str(self.root),
        ], stdout=out)
        return code, out.getvalue()

    def snapshot_files(self):
        paths = [
            self.run_dir / "state.json",
            self.run_dir / "worklist.yml",
            self.run_dir / "events.jsonl",
            self.run_dir / "stage-results" / "06-solution-design.json",
        ]
        result = {}
        for path in paths:
            result[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "MISSING"
        return result


class EvidenceTest(V2Fixture):
    def test_solution_artifact_semantics(self):
        from loopx_controller_evidence import validate_solution_semantics

        artifact = self.solution_artifact()
        self.assertEqual(validate_solution_semantics(artifact), [])
        for name in tuple(artifact["quality_attributes"]):
            broken = json.loads(json.dumps(artifact))
            del broken["quality_attributes"][name]
            self.assertTrue(validate_solution_semantics(broken), name)
        broken = json.loads(json.dumps(artifact))
        broken["quality_attributes"]["security"] = {
            "status": "NOT_APPLICABLE",
            "approach": "",
            "reason": "",
            "evidence": [],
        }
        self.assertIn("具体理由", "\n".join(validate_solution_semantics(broken)))

    def test_test_plan_coverage_and_cleanup(self):
        from loopx_controller_evidence import validate_test_plan_semantics

        artifact = {
            "requirement_ids": ["AC-001"],
            "mappings": [{"requirement_id": "AC-001", "rule_ids": ["R1"], "test_case_ids": ["TC1"]}],
            "cases": [{
                "id": "TC1",
                "covers": ["AC-001"],
                "risk_tags": [],
                "preconditions": [],
                "data_setup": {"run_id_strategy": "uuid", "records": []},
                "execution": {"entrypoint": "python3 -m unittest", "steps": ["执行"]},
                "assertions": ["退出码为 0"],
                "cleanup": {"steps": ["退出临时目录"], "verification": ["目录不存在"]},
                "expected_result": "PASS",
            }],
        }
        self.assertEqual(validate_test_plan_semantics(artifact, ["R1"]), [])
        for field in ("data_setup", "execution", "assertions", "cleanup"):
            broken = json.loads(json.dumps(artifact))
            broken["cases"][0][field] = {} if field != "assertions" else []
            self.assertTrue(validate_test_plan_semantics(broken, ["R1"]), field)
        broken = json.loads(json.dumps(artifact))
        broken["mappings"][0]["rule_ids"] = []
        self.assertIn("R1", "\n".join(validate_test_plan_semantics(broken, ["R1"])))

    def test_performance_risk_controls_solution_review(self):
        from loopx_controller_evidence import validate_solution_semantics

        self.init(mode="STANDARD", risk_tags=["performance"])
        artifact = self.solution_artifact()
        artifact["performance_targets"] = [{
            "metric": "p95",
            "unit": "ms",
            "target": "<=100",
            "target_source": "已批准规格",
            "load": "每秒 20 请求",
            "environment": "本地固定夹具",
            "baseline": "95ms",
            "allowed_variation": "+5%",
            "evidence": [self.evidence_path()],
        }]
        self.assertEqual(validate_solution_semantics(artifact, ["performance"]), [])
        for field in ("target_source", "load", "environment", "baseline", "allowed_variation"):
            broken = json.loads(json.dumps(artifact))
            broken["performance_targets"][0][field] = ""
            self.assertIn(field, "\n".join(validate_solution_semantics(broken, ["performance"])))

        broken = json.loads(json.dumps(artifact))
        broken["performance_targets"][0]["target_source"] = ""
        broken["stage"] = "solution_review"
        artifact_path = self.write_solution(broken)
        state_path = self.run_dir / "state.json"
        events_path = self.run_dir / "events.jsonl"
        result_path = self.run_dir / "stage-results" / "07-solution-review.json"
        before = (state_path.read_bytes(), events_path.read_bytes(), result_path.exists())
        out = io.StringIO()
        args = [
            "record-stage", "--run-id", self.run_id, "--stage", "solution_review",
            "--status", "PASS", "--artifact", f"solution={artifact_path}",
            "--project", str(self.root),
        ]
        self.assertEqual(self.controller.main(args, stdout=out), 1)
        self.assertIn("target_source", out.getvalue())
        self.assertEqual(before, (state_path.read_bytes(), events_path.read_bytes(), result_path.exists()))

        artifact["stage"] = "solution_review"
        self.write_json(artifact_path, artifact)
        out = io.StringIO()
        self.assertEqual(self.controller.main(args, stdout=out), 0, out.getvalue())
        self.assertEqual(json.loads(result_path.read_text(encoding="utf-8"))["status"], "NEED_HUMAN")

    def test_security_controls_by_risk(self):
        from loopx_controller_evidence import validate_security_semantics

        controls = []
        for control in ("identity", "permission", "input", "sensitive_data", "dependency"):
            controls.append({
                "control": control,
                "status": "PASS",
                "verification": "已检查",
                "evidence": ["check.log"],
                "remaining_risk": "",
            })
        artifact = {"controls": controls}
        self.assertEqual(validate_security_semantics(artifact, ["auth", "permission"]), [])
        artifact["controls"] = [item for item in controls if item["control"] != "permission"]
        self.assertIn("permission", "\n".join(validate_security_semantics(artifact, ["permission"])))


class EvidencePathTest(V2Fixture):
    def test_resolved_path_boundary(self):
        from loopx_controller_evidence import resolve_project_file

        inside = self.write_text("evidence/inside.log")
        relative, _ = resolve_project_file(self.root, inside)
        self.assertEqual(relative, inside)
        for value in (str(self.root / inside), "../outside.log", "missing.log"):
            with self.assertRaises(ValueError):
                resolve_project_file(self.root, value)
        with self.assertRaises(ValueError):
            resolve_project_file(self.root, "evidence")

        outside_root = Path(tempfile.mkdtemp(prefix="loopx-std-outside-"))
        try:
            outside = outside_root / "outside.log"
            outside.write_text("outside", encoding="utf-8")
            link = self.root / "evidence" / "outside-link.log"
            try:
                link.symlink_to(outside)
            except OSError:
                self.skipTest("当前文件系统不支持符号链接")
            with self.assertRaises(ValueError):
                resolve_project_file(self.root, "evidence/outside-link.log")
        finally:
            shutil.rmtree(outside_root)


class LoopxControllerV2Test(V2Fixture):
    def test_init_v2(self):
        state = self.init()
        self.assertEqual(state["contract_version"], "2")
        self.assertEqual(state["catalog_version"], "2")
        snapshot = self.root / state["policy_snapshot"]
        self.assertTrue(snapshot.is_file())
        payload = json.loads(snapshot.read_text(encoding="utf-8"))
        self.assertEqual(payload["digest"], state["policy_snapshot_sha256"])

    def test_record_stage_pass_with_artifacts(self):
        self.init()
        artifact_path = self.write_solution()
        code, output = self.record_solution(artifact_path)
        self.assertEqual(code, 0, output)
        result = json.loads((self.run_dir / "stage-results" / "06-solution-design.json").read_text(encoding="utf-8"))
        self.assertEqual(result["contract_version"], "2")
        self.assertEqual(result["artifacts"], [{"type": "solution", "path": artifact_path}])
        self.assertTrue(result["evidence"])
        worklist = (self.run_dir / "worklist.yml").read_text(encoding="utf-8")
        self.assertIn("id: W1", worklist)
        self.assertIn("status: pending", worklist)

    def test_record_stage_rejects_invalid_evidence_matrix(self):
        self.init()
        before = self.snapshot_files()
        out = io.StringIO()
        self.assertEqual(self.controller.main([
            "record-stage", "--run-id", self.run_id, "--stage", "requirement_intake",
            "--status", "PASS", "--project", str(self.root),
        ], stdout=out), 1)
        self.assertIn("至少一个有效证据文件", out.getvalue())
        self.assertEqual(before, self.snapshot_files())

        evidence = self.evidence_path()
        out = io.StringIO()
        self.assertEqual(self.controller.main([
            "record-stage", "--run-id", self.run_id, "--stage", "requirement_intake",
            "--status", "ACCEPTED_RISK", "--evidence", evidence,
            "--project", str(self.root),
        ], stdout=out), 1)
        self.assertIn("不接受阶段级 ACCEPTED_RISK", out.getvalue())
        self.assertEqual(before, self.snapshot_files())

        code, output = self.record_solution("missing.json")
        self.assertEqual(code, 1)
        self.assertIn("不存在", output)
        self.assertEqual(before, self.snapshot_files())

        artifact_directory = (self.run_dir / "artifacts").relative_to(self.root).as_posix()
        code, output = self.record_solution(artifact_directory)
        self.assertEqual(code, 1)
        self.assertIn("普通文件", output)
        self.assertEqual(before, self.snapshot_files())

        mutations = (
            ("artifact_version", "9", "artifact_version"),
            ("artifact_type", "test_plan", "artifact_type"),
            ("run_id", "another-run", "run_id"),
            ("stage", "solution_review", "阶段"),
        )
        for field, value, message in mutations:
            with self.subTest(field=field):
                artifact = self.solution_artifact()
                artifact[field] = value
                path = self.write_solution(artifact)
                code, output = self.record_solution(path)
                self.assertEqual(code, 1)
                self.assertIn(message, output)
                self.assertEqual(before, self.snapshot_files())

    def test_required_rule_failure_and_unconfirmed_acceptance_are_rejected(self):
        self.init(mode="STANDARD", risk_tags=["api_contract"])
        evidence = self.evidence_path()
        for status, reason, message in (
            ("CHANGES_REQUIRED", "兼容方案不完整", "未通过"),
            ("ACCEPTED_RISK", "接受兼容风险", "缺少用户确认"),
        ):
            with self.subTest(status=status):
                artifact = self.solution_artifact(evidence=evidence)
                artifact["rule_results"] = [
                    self.rule_result("ARCH-BOUNDARY-002", evidence),
                    {
                        "rule_id": "ARCH-COMPAT-003",
                        "status": status,
                        "evidence": [evidence],
                        "reason": reason,
                    },
                ]
                path = self.write_solution(artifact)
                before = self.snapshot_files()
                code, output = self.record_solution(path)
                self.assertEqual(code, 1)
                self.assertIn(message, output)
                self.assertEqual(before, self.snapshot_files())

    def test_record_stage_failure_is_atomic(self):
        self.init()
        path = self.write_solution()
        artifact = json.loads((self.root / path).read_text(encoding="utf-8"))
        artifact["quality_attributes"]["security"]["evidence"] = ["missing-security.log"]
        self.write_json(path, artifact)
        before = self.snapshot_files()
        code, _ = self.record_solution(path)
        self.assertEqual(code, 1)
        self.assertEqual(before, self.snapshot_files())

    def test_atomic_writer_restores_replaced_files_after_storage_error(self):
        from loopx_controller_io import atomic_write_texts

        targets = [self.root / f"target-{index}.txt" for index in range(1, 5)]
        original_replace = Path.replace
        for fail_index in (2, 3, 4):
            with self.subTest(fail_index=fail_index):
                for index, target in enumerate(targets, start=1):
                    target.write_text(f"old-{index}", encoding="utf-8")
                calls = 0

                def fail_selected(source, target):
                    nonlocal calls
                    calls += 1
                    if calls == fail_index:
                        raise OSError(f"模拟第 {fail_index} 个目标写入失败")
                    return original_replace(source, target)

                with mock.patch.object(Path, "replace", new=fail_selected):
                    with self.assertRaisesRegex(OSError, f"第 {fail_index} 个目标"):
                        atomic_write_texts({
                            target: f"new-{index}"
                            for index, target in enumerate(targets, start=1)
                        })

                for index, target in enumerate(targets, start=1):
                    self.assertEqual(target.read_text(encoding="utf-8"), f"old-{index}")
                self.assertEqual(list(self.root.glob(".*.tmp")), [])
                self.assertEqual(list(self.root.glob(".*.bak")), [])

    def test_record_stage_restores_all_targets_after_storage_error(self):
        self.init()
        artifact_path = self.write_solution()
        before = self.snapshot_files()
        original_replace = Path.replace
        calls = 0

        def fail_second(source, target):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("disk full")
            return original_replace(source, target)

        out = io.StringIO()
        with mock.patch.object(Path, "replace", new=fail_second):
            code = self.controller.main([
                "record-stage", "--run-id", self.run_id, "--stage", "solution_design",
                "--status", "PASS", "--artifact", f"solution={artifact_path}",
                "--item", "W1", "--project", str(self.root),
            ], stdout=out)

        self.assertEqual(code, 1)
        self.assertIn("阶段记录写入失败", out.getvalue())
        self.assertIn("disk full", out.getvalue())
        self.assertEqual(before, self.snapshot_files())
        self.assertEqual(list(self.run_dir.rglob("*.tmp")), [])
        self.assertEqual(list(self.run_dir.rglob("*.bak")), [])

    def test_mode_selection_updates_snapshot_and_fails_without_partial_writes(self):
        self.init(mode="LIGHT", risk_tags=["core_state_transition"])
        state_path = self.run_dir / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state.setdefault("stages", {})["spec_review"] = "PASS"
        state["current_stage"] = "mode_selection"
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

        out = io.StringIO()
        self.assertEqual(self.controller.main([
            "mode", self.run_id, "--select", "FULL", "--project", str(self.root),
        ], stdout=out), 0, out.getvalue())
        selected = json.loads(state_path.read_text(encoding="utf-8"))
        snapshot_path = self.root / selected["policy_snapshot"]
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        self.assertEqual(selected["mode"], "FULL")
        self.assertEqual(snapshot["mode"], "FULL")
        self.assertEqual(selected["policy_snapshot_sha256"], snapshot["digest"])
        self.assertIn("ARCH-BOUNDARY-002", {rule["id"] for rule in snapshot["rules"]})
        self.assertIn("mode: FULL", (self.run_dir / "worklist.yml").read_text(encoding="utf-8"))

        selected["current_stage"] = "solution_design"
        state_path.write_text(json.dumps(selected, ensure_ascii=False), encoding="utf-8")
        snapshot_before = snapshot_path.read_bytes()
        out = io.StringIO()
        self.assertEqual(self.controller.main([
            "mode", self.run_id, "--select", "STANDARD", "--project", str(self.root),
        ], stdout=out), 1)
        self.assertIn("只能在 mode_selection 阶段", out.getvalue())
        self.assertEqual(snapshot_before, snapshot_path.read_bytes())

        failed_run = f"{self.run_id}-failed"
        self.run_id = failed_run
        self.init(mode="LIGHT", risk_tags=["core_state_transition"])
        failed_state_path = self.run_dir / "state.json"
        failed_state = json.loads(failed_state_path.read_text(encoding="utf-8"))
        failed_state.setdefault("stages", {})["spec_review"] = "PASS"
        failed_state["current_stage"] = "mode_selection"
        failed_state_path.write_text(json.dumps(failed_state, ensure_ascii=False), encoding="utf-8")
        snapshot_path = self.root / failed_state["policy_snapshot"]
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        snapshot["mode"] = "FULL"
        snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
        before = self.snapshot_files()
        out = io.StringIO()
        self.assertEqual(self.controller.main([
            "mode", self.run_id, "--select", "FULL", "--project", str(self.root),
        ], stdout=out), 1)
        self.assertIn("摘要校验失败", out.getvalue())
        self.assertEqual(before, self.snapshot_files())
        self.assertFalse((self.run_dir / "artifacts" / "mode-decision.json").exists())
        self.assertFalse((self.run_dir / "stage-results" / "05-mode-selection.json").exists())

    def test_rule_acceptance_requires_matching_quality_confirmation(self):
        self.init(mode="STANDARD", risk_tags=["reliability"])
        evidence = self.evidence_path()
        confirmation = self.write_text(
            f"docs/loopx/runs/{self.run_id}/artifacts/risk-confirmation.txt",
            "用户确认接受 OBS-EVIDENCE-001 的剩余风险。\n",
        )
        document = self.document_path("quality.md")
        artifact = self.quality_artifact(evidence, document)
        artifact["rule_results"] = [{
            "rule_id": "OBS-EVIDENCE-001",
            "status": "ACCEPTED_RISK",
            "evidence": [evidence],
            "reason": "本地无法覆盖真实 CI 可观测性",
        }]
        state_path = self.run_dir / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["mode_decision"]["accepted_risk"] = {
            "selected_lower_than_recommended": True,
            "reason": "整体等级降级确认不能替代逐规则确认",
        }
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        path = self.write_json(
            f"docs/loopx/runs/{self.run_id}/artifacts/quality-result.json",
            artifact,
        )
        out = io.StringIO()
        args = [
            "record-stage", "--run-id", self.run_id, "--stage", "quality_audit",
            "--status", "PASS", "--artifact", f"quality_result={path}",
            "--project", str(self.root),
        ]
        self.assertEqual(self.controller.main(args, stdout=out), 1)
        self.assertIn("缺少逐规则风险接受确认", out.getvalue())

        artifact["accepted_risks"] = [{
            "rule_id": "OBS-EVIDENCE-001",
            "reason": "真实 CI 可观测性由用户接受为剩余风险",
            "confirmation_evidence": confirmation,
        }]
        self.write_json(path, artifact)
        out = io.StringIO()
        self.assertEqual(self.controller.main(args, stdout=out), 0, out.getvalue())

    def test_strict_validate_v2_artifacts(self):
        self.init()
        artifact_path = self.write_solution()
        code, output = self.record_solution(artifact_path)
        self.assertEqual(code, 0, output)

        def strict_result():
            out = io.StringIO()
            code = self.controller.main([
                "validate", self.run_id, "--strict", "--project", str(self.root)
            ], stdout=out)
            return code, out.getvalue()

        self.assertEqual(strict_result()[0], 0)
        evidence = self.run_dir / "artifacts" / "check.log"
        evidence.unlink()
        code, output = strict_result()
        self.assertEqual(code, 1)
        self.assertIn("v2 证据复核失败", output)
        evidence.write_text("证据\n", encoding="utf-8")

        artifact = self.root / artifact_path
        original_artifact = artifact.read_text(encoding="utf-8")
        for field, value, expected in (
            ("artifact_version", "9", "artifact_version"),
            ("stage", "solution_review", "阶段"),
        ):
            with self.subTest(field=field):
                mutated = json.loads(original_artifact)
                mutated[field] = value
                artifact.write_text(json.dumps(mutated, ensure_ascii=False), encoding="utf-8")
                code, output = strict_result()
                self.assertEqual(code, 1)
                self.assertIn(expected, output)
                artifact.write_text(original_artifact, encoding="utf-8")

        mutated = json.loads(original_artifact)
        mutated["rule_results"][0]["rule_id"] = "UNKNOWN-RULE"
        artifact.write_text(json.dumps(mutated, ensure_ascii=False), encoding="utf-8")
        code, output = strict_result()
        self.assertEqual(code, 1)
        self.assertIn("未选择的规则", output)
        artifact.write_text(original_artifact, encoding="utf-8")

        state = json.loads((self.run_dir / "state.json").read_text(encoding="utf-8"))
        snapshot_path = self.root / state["policy_snapshot"]
        original_snapshot = snapshot_path.read_text(encoding="utf-8")
        snapshot = json.loads(original_snapshot)
        snapshot["mode"] = "FULL"
        snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
        code, output = strict_result()
        self.assertEqual(code, 1)
        self.assertIn("摘要校验失败", output)
        snapshot_path.write_text(original_snapshot, encoding="utf-8")
        self.assertEqual(strict_result()[0], 0)

    def test_retry_and_duplicate_submission(self):
        self.init()
        missing = self.solution_artifact()
        missing["quality_attributes"]["security"]["evidence"] = ["not-created.log"]
        path = self.write_solution(missing)
        self.assertEqual(self.record_solution(path)[0], 1)
        self.write_text("not-created.log")
        self.assertEqual(self.record_solution(path)[0], 0)
        events = (self.run_dir / "events.jsonl").read_text(encoding="utf-8")
        self.assertEqual(self.record_solution(path)[0], 0)
        self.assertEqual(events, (self.run_dir / "events.jsonl").read_text(encoding="utf-8"))

    def test_v2_confirmation_requires_project_file(self):
        self.init()
        evidence = self.evidence_path()
        out = io.StringIO()
        self.assertEqual(self.controller.main([
            "record-stage", "--run-id", self.run_id, "--stage", "solution_review",
            "--status", "PASS", "--evidence", evidence,
            "--project", str(self.root),
        ], stdout=out), 0, out.getvalue())
        state_path = self.run_dir / "state.json"
        before = state_path.read_bytes()
        out = io.StringIO()
        self.assertEqual(self.controller.main([
            "confirm-stage", "--run-id", self.run_id, "--stage", "solution_review",
            "--evidence", "用户已确认", "--project", str(self.root),
        ], stdout=out), 1)
        self.assertIn("不存在", out.getvalue())
        self.assertEqual(before, state_path.read_bytes())

        confirmation = self.write_text(
            f"docs/loopx/runs/{self.run_id}/artifacts/solution-confirmation.txt",
            "用户确认方案。\n",
        )
        out = io.StringIO()
        self.assertEqual(self.controller.main([
            "confirm-stage", "--run-id", self.run_id, "--stage", "solution_review",
            "--evidence", confirmation, "--project", str(self.root),
        ], stdout=out), 0, out.getvalue())


class LoopxControllerV2E2ETest(V2Fixture):
    def test_init_structured_design_confirmation_and_strict_validation(self):
        self.init(mode="FULL", risk_tags=["core_state_transition"])
        evidence = self.evidence_path()
        solution = self.solution_artifact(evidence=evidence)
        solution["rule_results"] = [
            {"rule_id": rule_id, "status": "PASS", "evidence": [evidence], "reason": ""}
            for rule_id in (
                "ARCH-BOUNDARY-002",
                "ARCH-COMPAT-003",
                "REL-RECOVERY-001",
                "ARCH-SIMPLE-001",
            )
        ]
        artifact_path = self.write_solution(solution)
        code, output = self.record_solution(artifact_path)
        self.assertEqual(code, 0, output)

        review_solution = json.loads(json.dumps(solution))
        review_solution["stage"] = "solution_review"
        review_path = self.write_solution(review_solution, "solution-review.json")

        out = io.StringIO()
        self.assertEqual(self.controller.main([
            "record-stage", "--run-id", self.run_id, "--stage", "solution_review",
            "--status", "PASS", "--artifact", f"solution={review_path}",
            "--item", "W1", "--project", str(self.root),
        ], stdout=out), 0, out.getvalue())
        confirmation = self.write_text(
            f"docs/loopx/runs/{self.run_id}/artifacts/e2e-confirmation.txt",
            "用户确认结构化方案。\n",
        )
        out = io.StringIO()
        self.assertEqual(self.controller.main([
            "confirm-stage", "--run-id", self.run_id, "--stage", "solution_review",
            "--evidence", confirmation, "--project", str(self.root),
        ], stdout=out), 0, out.getvalue())

        out = io.StringIO()
        self.assertEqual(self.controller.main([
            "validate", self.run_id, "--strict", "--project", str(self.root),
        ], stdout=out), 0, out.getvalue())
        state = json.loads((self.run_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["contract_version"], "2")
        self.assertEqual(state["stages"]["solution_review"], "PASS")
        self.assertIn("id: W1", (self.run_dir / "worklist.yml").read_text(encoding="utf-8"))

    def test_full_v2_seventeen_stage_close(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True, text=True)
        self.write_text(".github/workflows/ci.yml", "name: LoopX CI\n")
        self.init(mode="FULL", risk_tags=["core_state_transition"])
        evidence = self.evidence_path()

        def record(stage, *, artifact=None, item=None, stage_evidence=None):
            args = [
                "record-stage", "--run-id", self.run_id, "--stage", stage,
                "--status", "PASS", "--evidence", stage_evidence or evidence,
            ]
            if artifact:
                args.extend(["--artifact", artifact])
            if item:
                args.extend(["--item", item])
            self.controller_command(*args)

        def next_stage():
            self.controller_command("next", self.run_id)

        record("requirement_intake")
        next_stage()

        self.controller_command("interview", self.run_id)
        interview_path = self.run_dir / "artifacts" / "interview.md"
        interview = interview_path.read_text(encoding="utf-8")
        for marker in ("待用户回答", "待采访确认", "待确认", "未回答", "TBD", "TODO"):
            interview = interview.replace(marker, "已明确")
        interview_path.write_text(interview, encoding="utf-8")
        record("requirement_interview", stage_evidence=interview_path.relative_to(self.root).as_posix())
        interview_confirmation = self.write_text(
            f"docs/loopx/runs/{self.run_id}/artifacts/interview-confirmation.txt",
            "用户确认需求采访。\n",
        )
        self.controller_command(
            "confirm-stage", "--run-id", self.run_id, "--stage", "requirement_interview",
            "--evidence", interview_confirmation,
        )
        next_stage()

        self.controller_command("spec", self.run_id)
        spec_relative = f"docs/loopx/runs/{self.run_id}/artifacts/spec.md"
        self.write_text(spec_relative, """# 需求规格

## 摘要
验证 FULL v2 完整流程。

## 期望行为
全部阶段由控制器推进并可严格复核。

## 验收标准
AC-001：运行完成并成功收口。

## 范围内
控制器、本地文件产物和临时 Git 仓库。

## 范围外
远端发布和外部系统调用。

## 边界情况
证据缺失、确认缺失和工作项未完成会阻塞。

## 测试策略
执行结构化产物、健康检查和严格检查。

## 执行等级决策
使用 FULL 等级并命中核心状态风险。
""")
        record("spec_draft", stage_evidence=spec_relative)
        next_stage()
        record("spec_review", stage_evidence=spec_relative)
        next_stage()

        self.controller_command("mode", self.run_id, "--select", "FULL")
        next_stage()

        solution = self.solution_artifact(evidence=evidence)
        solution["rule_results"] = [
            self.rule_result(rule_id, evidence)
            for rule_id in (
                "ARCH-BOUNDARY-002",
                "ARCH-COMPAT-003",
                "REL-RECOVERY-001",
                "ARCH-SIMPLE-001",
            )
        ]
        solution_path = self.write_solution(solution)
        record("solution_design", artifact=f"solution={solution_path}", item="W1")
        next_stage()
        review_solution = json.loads(json.dumps(solution))
        review_solution["stage"] = "solution_review"
        review_solution_path = self.write_solution(review_solution, "solution-review.json")
        record("solution_review", artifact=f"solution={review_solution_path}", item="W1")
        solution_confirmation = self.write_text(
            f"docs/loopx/runs/{self.run_id}/artifacts/solution-confirmation.txt",
            "用户确认方案审核结论。\n",
        )
        self.controller_command(
            "confirm-stage", "--run-id", self.run_id, "--stage", "solution_review",
            "--evidence", solution_confirmation,
        )
        next_stage()

        state = json.loads((self.run_dir / "state.json").read_text(encoding="utf-8"))
        snapshot = json.loads((self.root / state["policy_snapshot"]).read_text(encoding="utf-8"))
        required_rule_ids = [rule["id"] for rule in snapshot["rules"] if rule["level"] == "required"]
        test_document = self.document_path("test-plan.md")
        test_plan = self.build_test_plan_artifact(evidence, test_document, required_rule_ids)
        test_plan_path = self.write_json(
            f"docs/loopx/runs/{self.run_id}/artifacts/test-plan.json",
            test_plan,
        )
        record("test_design", artifact=f"test_plan={test_plan_path}", item="W1")
        next_stage()
        review_test_plan = json.loads(json.dumps(test_plan))
        review_test_plan["stage"] = "test_review"
        review_test_plan_path = self.write_json(
            f"docs/loopx/runs/{self.run_id}/artifacts/test-plan-review.json",
            review_test_plan,
        )
        record("test_review", artifact=f"test_plan={review_test_plan_path}", item="W1")
        next_stage()

        development_document = self.document_path("development.md")
        development = self.development_artifact(evidence, development_document)
        development_path = self.write_json(
            f"docs/loopx/runs/{self.run_id}/artifacts/development-evidence.json",
            development,
        )
        record(
            "development",
            artifact=f"development_evidence={development_path}",
            item="W1",
        )
        next_stage()

        quality_document = self.document_path("quality.md")
        quality = self.quality_artifact(evidence, quality_document)
        quality_path = self.write_json(
            f"docs/loopx/runs/{self.run_id}/artifacts/quality-result.json",
            quality,
        )
        record("quality_audit", artifact=f"quality_result={quality_path}", item="W1")
        next_stage()
        record("code_review", item="W1")
        next_stage()

        cleanup_path = self.write_json(
            f"docs/loopx/runs/{self.run_id}/artifacts/test-cleanup.json",
            {"cleanup_verified": True},
        )
        record("test_execution", item="W1", stage_evidence=cleanup_path)
        next_stage()

        health_output = self.controller_command("health", self.run_id)
        self.assertIn("健康检查结果：PASS", health_output)
        health_result = f"docs/loopx/runs/{self.run_id}/artifacts/health-result.json"
        record("health_gate", stage_evidence=health_result)
        next_stage()
        record("release_readiness")
        next_stage()

        self.controller_command("git-gate", self.run_id)
        self.controller_command(
            "compound", self.run_id, "--decision", "skipped",
            "--reason", "本次变更为控制器契约验证，没有新增可复用项目经验。",
        )
        compound_artifact = f"docs/loopx/runs/{self.run_id}/artifacts/compound-capture.md"
        record("final_report", stage_evidence=compound_artifact)

        self.controller_command("validate", self.run_id, "--strict")
        self.controller_command("close", self.run_id)
        state = json.loads((self.run_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["status"], "PASS")
        self.assertEqual(state["current_stage"], "final_report")
        self.assertEqual(set(state["stages"]), set(self.controller.STAGE_SEQUENCE))
        self.assertTrue(all(status == "PASS" for status in state["stages"].values()))
        self.assertTrue((self.run_dir / "artifacts" / "close-evidence.json").is_file())


class WorklistTest(V2Fixture):
    def test_solution_work_items_sync(self):
        from loopx_controller_evidence import runtime_work_items

        items = self.solution_artifact()["work_items"]
        items.append({
            "id": "W2",
            "title": "验证控制器",
            "risk_tags": [],
            "owner_agent": "test-runner",
            "read_scope": ["tests"],
            "write_scope": ["tests"],
            "dependencies": ["W1"],
            "validation": ["python3 -m unittest"],
        })
        result = runtime_work_items(items)
        self.assertEqual(result[0]["status"], "pending")
        self.assertEqual(result[1]["dependencies"], ["W1"])
        duplicate = json.loads(json.dumps(items))
        duplicate[1]["id"] = "W1"
        with self.assertRaises(ValueError):
            runtime_work_items(duplicate)
        cycle = json.loads(json.dumps(items))
        cycle[0]["dependencies"] = ["W2"]
        with self.assertRaises(ValueError):
            runtime_work_items(cycle)

    def test_all_commands_validate_item_reference(self):
        self.init()
        evidence = self.evidence_path()
        before = self.snapshot_files()
        out = io.StringIO()
        code = self.controller.main([
            "record-stage", "--run-id", self.run_id, "--stage", "requirement_intake",
            "--status", "BLOCKED", "--evidence", evidence, "--item", "UNKNOWN",
            "--project", str(self.root),
        ], stdout=out)
        self.assertEqual(code, 1)
        self.assertIn("工作项引用不存在", out.getvalue())
        self.assertEqual(before, self.snapshot_files())
        for command in (
            ["fail-review", "--from", "solution_review", "--return-to", "solution_design", "--item", "UNKNOWN", "--reason", "缺陷"],
            ["review-feedback", "--return-to", "solution_design", "--item", "UNKNOWN", "--reason", "缺陷"],
            ["close-repair", "--item", "UNKNOWN", "--artifact", evidence, "--revision", "2", "--change", "修正"],
        ):
            out = io.StringIO()
            args = [*command, "--run-id", self.run_id, "--project", str(self.root)]
            self.assertEqual(self.controller.main(args, stdout=out), 1)
            self.assertIn("工作项引用不存在", out.getvalue())

    def test_development_pass_resolves_affected_work_item(self):
        self.init()
        evidence = self.evidence_path()
        solution_path = self.write_solution(self.solution_artifact(evidence=evidence))
        self.assertEqual(self.record_solution(solution_path)[0], 0)
        self.controller_command(
            "fail-review", "--run-id", self.run_id, "--from", "code_review",
            "--return-to", "development", "--item", "W1", "--reason", "需要补充实现证据",
        )
        document = self.document_path("development.md")
        artifact = self.development_artifact(evidence, document)
        artifact_path = self.write_json(
            f"docs/loopx/runs/{self.run_id}/artifacts/development-evidence.json",
            artifact,
        )
        self.controller_command(
            "record-stage", "--run-id", self.run_id, "--stage", "development",
            "--status", "PASS", "--artifact", f"development_evidence={artifact_path}",
            "--item", "W1",
        )
        from loopx_controller_yaml import parse_yaml_subset

        worklist = parse_yaml_subset((self.run_dir / "worklist.yml").read_text(encoding="utf-8"))
        item = worklist["items"][0]
        self.assertEqual(item["status"], "PASS")
        self.assertTrue(item["evidence"])
        self.assertEqual(item["failed_by"], "")
        self.assertEqual(item["return_to"], "")
        self.assertEqual(item["required_changes"], [])

    def test_identical_stage_retry_restores_state_after_review_return(self):
        self.init(mode="FULL", risk_tags=["core_state_transition"])
        evidence = self.evidence_path()
        artifact = self.solution_artifact(evidence=evidence)
        artifact["rule_results"] = [
            self.rule_result(rule_id, evidence)
            for rule_id in ("ARCH-BOUNDARY-002", "ARCH-COMPAT-003", "REL-RECOVERY-001", "ARCH-SIMPLE-001")
        ]
        solution_path = self.write_solution(artifact)
        self.assertEqual(self.record_solution(solution_path)[0], 0)
        # 审核返回会保留旧阶段结果文件并清除需要重做阶段的状态；这里直接构造该持久化边界。
        state_path = self.run_dir / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["stages"].pop("solution_design")
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

        code, output = self.record_solution(solution_path)

        self.assertEqual(code, 0, output)
        state = json.loads((self.run_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["stages"]["solution_design"], "PASS")


class LoopxLegacyCompatibilityTest(V2Fixture):
    def test_v1_end_to_end(self):
        self.init()
        state_path = self.run_dir / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        for key in ("contract_version", "catalog_version", "policy_snapshot", "policy_snapshot_sha256"):
            state.pop(key, None)
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        out = io.StringIO()
        self.assertEqual(self.controller.main([
            "record-stage", "--run-id", self.run_id, "--stage", "requirement_intake",
            "--status", "PASS", "--evidence", "legacy free-form evidence",
            "--project", str(self.root),
        ], stdout=out), 0, out.getvalue())
        result = json.loads((self.run_dir / "stage-results" / "01-requirement-intake.json").read_text(encoding="utf-8"))
        self.assertNotIn("contract_version", result)
        self.assertEqual(result["evidence"], ["legacy free-form evidence"])


if __name__ == "__main__":
    unittest.main()
