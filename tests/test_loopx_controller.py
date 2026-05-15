import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER_PATH = ROOT / "loopx" / "tools" / "loopx_controller.py"


def load_controller_module():
    spec = importlib.util.spec_from_file_location("loopx_controller", CONTROLLER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LoopxControllerTest(unittest.TestCase):
    def setUp(self):
        self.controller = load_controller_module()
        self.tmp = Path(tempfile.mkdtemp(prefix="loopx-controller-test-"))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_init_creates_run_state_worklist_and_events(self):
        out = io.StringIO()
        code = self.controller.main([
            "init",
            "Add state driven LoopX controller",
            "--run-id",
            "2026-05-15-controller",
            "--project",
            str(self.tmp),
        ], stdout=out)

        self.assertEqual(code, 0)
        run_dir = self.tmp / ".loopx" / "runs" / "2026-05-15-controller"
        state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))

        self.assertEqual(state["run_id"], "2026-05-15-controller")
        self.assertEqual(state["mode"], "LIGHT")
        self.assertEqual(state["risk_tags"], [])
        self.assertEqual(state["current_stage"], "environment_check")
        self.assertEqual(state["worklist"], ".loopx/runs/2026-05-15-controller/worklist.yml")
        self.assertTrue((run_dir / "worklist.yml").exists())
        self.assertTrue((run_dir / "events.jsonl").exists())
        self.assertIn("created run 2026-05-15-controller", out.getvalue())

    def test_init_auto_mode_uses_risk_tags_to_select_full(self):
        out = io.StringIO()
        code = self.controller.main([
            "init",
            "Change tenant scoped API state",
            "--run-id",
            "risk-run",
            "--mode",
            "auto",
            "--risk-tags",
            "tenant_scope",
            "core_state_transition",
            "api_contract",
            "--project",
            str(self.tmp),
        ], stdout=out)

        self.assertEqual(code, 0)
        state = json.loads((self.tmp / ".loopx" / "runs" / "risk-run" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["mode"], "FULL")
        self.assertEqual(state["risk_tags"], ["tenant_scope", "core_state_transition", "api_contract"])
        self.assertIn("mode: FULL", out.getvalue())

    def test_validate_rejects_worklist_items_missing_required_fields(self):
        run_dir = self.tmp / ".loopx" / "runs" / "bad-run"
        run_dir.mkdir(parents=True)
        (run_dir / "state.json").write_text(json.dumps({
            "run_id": "bad-run",
            "requirement": "Bad worklist",
            "mode": "STANDARD",
            "status": "ACTIVE",
            "current_stage": "environment_check",
            "confirmation_policy": "verification_gated",
            "max_auto_repair": 2,
            "worklist": ".loopx/runs/bad-run/worklist.yml",
            "events": ".loopx/runs/bad-run/events.jsonl",
            "stages": {},
        }), encoding="utf-8")
        (run_dir / "worklist.yml").write_text("""run:
  id: bad-run
  requirement: Bad worklist
  mode: STANDARD
  status: ACTIVE
  current_stage: environment_check
items:
  - id: W001
    title: Missing owner agent
    status: TODO
""", encoding="utf-8")

        out = io.StringIO()
        code = self.controller.main([
            "validate",
            "bad-run",
            "--project",
            str(self.tmp),
        ], stdout=out)

        self.assertEqual(code, 1)
        self.assertIn("items[0].owner_agent is required", out.getvalue())

    def test_status_uses_latest_run_when_run_id_is_omitted(self):
        self.controller.main([
            "init",
            "Check status",
            "--run-id",
            "status-run",
            "--project",
            str(self.tmp),
        ], stdout=io.StringIO())

        out = io.StringIO()
        code = self.controller.main(["status", "--project", str(self.tmp)], stdout=out)

        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("run_id: status-run", text)
        self.assertIn("current_stage: environment_check", text)

    def test_validate_rejects_stage_result_missing_required_fields(self):
        self.controller.main([
            "init",
            "Check stage result schema",
            "--run-id",
            "stage-result-run",
            "--project",
            str(self.tmp),
        ], stdout=io.StringIO())
        result_path = self.tmp / ".loopx" / "runs" / "stage-result-run" / "stage-results" / "01-assignment.json"
        result_path.write_text(json.dumps({
            "stage": "assignment",
            "status": "PASS",
            "return_to": "",
            "next_action": "solution_design",
            "affected_work_items": [],
            "user_confirmation_required": False,
            "blocked_reason": "",
        }), encoding="utf-8")

        out = io.StringIO()
        code = self.controller.main([
            "validate",
            "stage-result-run",
            "--project",
            str(self.tmp),
        ], stdout=out)

        self.assertEqual(code, 1)
        self.assertIn("01-assignment.json.evidence is required", out.getvalue())

    def test_record_stage_writes_machine_readable_result_and_state(self):
        self.controller.main([
            "init",
            "Record stage",
            "--run-id",
            "record-run",
            "--project",
            str(self.tmp),
        ], stdout=io.StringIO())

        out = io.StringIO()
        code = self.controller.main([
            "record-stage",
            "--run-id",
            "record-run",
            "--stage",
            "solution_design",
            "--status",
            "PASS",
            "--evidence",
            "docs/solution.md",
            "--project",
            str(self.tmp),
        ], stdout=out)

        self.assertEqual(code, 0)
        run_dir = self.tmp / ".loopx" / "runs" / "record-run"
        state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
        result = json.loads((run_dir / "stage-results" / "03-solution-design.json").read_text(encoding="utf-8"))
        self.assertEqual(state["stages"]["solution_design"], "PASS")
        self.assertEqual(result["stage"], "solution_design")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["evidence"], ["docs/solution.md"])
        self.assertIn("PASS solution_design", out.getvalue())

    def test_advance_blocks_when_prior_stage_is_not_pass(self):
        self.controller.main([
            "init",
            "Advance gate",
            "--run-id",
            "advance-run",
            "--project",
            str(self.tmp),
        ], stdout=io.StringIO())

        out = io.StringIO()
        code = self.controller.main([
            "advance",
            "--run-id",
            "advance-run",
            "--to",
            "development",
            "--project",
            str(self.tmp),
        ], stdout=out)

        self.assertEqual(code, 1)
        self.assertIn("FAIL advance blocked", out.getvalue())
        self.assertIn("solution_review must be PASS before development", out.getvalue())

    def test_can_write_business_requires_development_and_solution_review_pass(self):
        self.controller.main([
            "init",
            "Business gate",
            "--run-id",
            "write-run",
            "--project",
            str(self.tmp),
        ], stdout=io.StringIO())

        out = io.StringIO()
        code = self.controller.main([
            "can-write",
            "--run-id",
            "write-run",
            "--kind",
            "business",
            "--project",
            str(self.tmp),
        ], stdout=out)

        self.assertEqual(code, 1)
        self.assertIn("FAIL business writes locked", out.getvalue())
        self.assertIn("current_stage must be development", out.getvalue())

        run_dir = self.tmp / ".loopx" / "runs" / "write-run"
        state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
        state["current_stage"] = "development"
        state["stages"]["solution_review"] = "PASS"
        (run_dir / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

        out = io.StringIO()
        code = self.controller.main([
            "can-write",
            "--run-id",
            "write-run",
            "--kind",
            "business",
            "--project",
            str(self.tmp),
        ], stdout=out)

        self.assertEqual(code, 0)
        self.assertIn("PASS business writes unlocked", out.getvalue())

    def test_review_feedback_marks_changes_required_and_returns_to_stage(self):
        self.controller.main([
            "init",
            "Feedback gate",
            "--run-id",
            "feedback-run",
            "--project",
            str(self.tmp),
        ], stdout=io.StringIO())
        run_dir = self.tmp / ".loopx" / "runs" / "feedback-run"
        state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
        state["current_stage"] = "development"
        state["stages"] = {
            "solution_design": "PASS",
            "solution_review": "PASS",
            "development": "PASS",
        }
        (run_dir / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        (run_dir / "worklist.yml").write_text("""run:
  id: feedback-run
  requirement: Feedback gate
  mode: STANDARD
  status: ACTIVE
  current_stage: development
items:
  - id: W1
    title: Exception package
    status: TODO
    risk_tags: []
    owner_agent: solution-designer
    read_scope: []
    write_scope: []
    dependencies: []
    validation: []
    evidence: []
    failed_by: ""
    return_to: ""
    required_changes: []
""", encoding="utf-8")

        out = io.StringIO()
        code = self.controller.main([
            "review-feedback",
            "--run-id",
            "feedback-run",
            "--item",
            "W1",
            "--return-to",
            "solution_design",
            "--reason",
            "exception package wrong",
            "--project",
            str(self.tmp),
        ], stdout=out)

        self.assertEqual(code, 0)
        state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
        review = json.loads((run_dir / "stage-results" / "04-solution-review.json").read_text(encoding="utf-8"))
        worklist = (run_dir / "worklist.yml").read_text(encoding="utf-8")
        self.assertEqual(state["current_stage"], "solution_design")
        self.assertEqual(state["stages"]["solution_review"], "CHANGES_REQUIRED")
        self.assertNotIn("development", state["stages"])
        self.assertEqual(review["status"], "CHANGES_REQUIRED")
        self.assertEqual(review["return_to"], "solution_design")
        self.assertIn("exception package wrong", review["evidence"])
        self.assertIn("status: CHANGES_REQUIRED", worklist)
        self.assertIn("return_to: solution_design", worklist)


if __name__ == "__main__":
    unittest.main()
