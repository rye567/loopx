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
        self.assertEqual(state["mode"], "STANDARD")
        self.assertEqual(state["current_stage"], "environment_check")
        self.assertEqual(state["worklist"], ".loopx/runs/2026-05-15-controller/worklist.yml")
        self.assertTrue((run_dir / "worklist.yml").exists())
        self.assertTrue((run_dir / "events.jsonl").exists())
        self.assertIn("created run 2026-05-15-controller", out.getvalue())

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


if __name__ == "__main__":
    unittest.main()
