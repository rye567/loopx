#!/usr/bin/env python3
"""Release and close commands for LoopX runs.

收口命令只负责汇总证据；是否可以收口必须先通过 validate_run 的统一检查。
"""

import subprocess
from pathlib import Path

from loopx_controller_contracts import STAGE_RESULT_FILES, STAGE_SEQUENCE
from loopx_controller_flow import stage_result_path
from loopx_controller_io import (
    append_event,
    get_run_dir,
    load_state,
    load_worklist,
    read_json,
    save_state,
    write_json,
)
from loopx_controller_state import resolve_run_id
from loopx_controller_validation import validate_run
from loopx_controller_yaml import YamlSubsetError, dump_worklist


def collect_git_status(project):
    try:
        probe = subprocess.run(
            ["git", "-C", str(project), "rev-parse", "--is-inside-work-tree"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "NEED_HUMAN", "", str(exc)
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        return "NEED_HUMAN", "", "not a git work tree"
    try:
        status = subprocess.run(
            ["git", "-C", str(project), "status", "--short"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "NEED_HUMAN", "", str(exc)
    if status.returncode != 0:
        return "NEED_HUMAN", "", (status.stderr or "git status failed").strip()
    summary = status.stdout.strip()
    if not summary:
        return "NEED_HUMAN", "", "no changed files"
    return "PASS", summary, ""


def build_close_evidence(project, run_id, state):
    directory = get_run_dir(project, run_id)
    evidence_matrix = {}
    for stage in STAGE_SEQUENCE:
        result_path = stage_result_path(directory, stage)
        entry = {
            "status": state.get("stages", {}).get(stage, "PENDING"),
            "stage_result": f"docs/loopx/runs/{run_id}/stage-results/{STAGE_RESULT_FILES[stage]}",
            "evidence": [],
        }
        if result_path.exists():
            try:
                result = read_json(result_path)
                entry["evidence"] = result.get("evidence", [])
            except ValueError:
                entry["evidence"] = []
        evidence_matrix[stage] = entry
    return {
        "run_id": run_id,
        "status": "PASS",
        "mode": state.get("mode"),
        "git_gate": state.get("git_gate", {}),
        "compound_capture": state.get("compound_capture", {}),
        "evidence_matrix": evidence_matrix,
        "ci_coverage": {
            "status": "LOCAL_ONLY",
            "summary": "CI/remote verification not executed by local close",
        },
        "uncovered": [
            "CI/remote verification not covered by local close",
        ],
    }


def cmd_close(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        state = load_state(project, run_id)
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    if state.get("stages", {}).get("final_report") != "PASS":
        print(f"FAIL close {run_id}", file=stdout)
        print("- final_report must be PASS before close", file=stdout)
        return 1
    # close 不自行放行，先复用严格检查，避免收口路径和 validate 路径分叉。
    errors = validate_run(project, run_id, strict=True)
    if errors:
        print(f"FAIL close {run_id}", file=stdout)
        print("- strict check failed", file=stdout)
        for error in errors:
            print(f"- {error}", file=stdout)
        return 1
    state["status"] = "PASS"
    state["current_stage"] = "final_report"
    state["next_action"] = "closed"
    evidence_path = get_run_dir(project, run_id) / "artifacts" / "close-evidence.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(evidence_path, build_close_evidence(project, run_id, state))
    save_state(project, run_id, state)
    try:
        worklist_path, worklist = load_worklist(project, state)
        worklist.setdefault("run", {})["status"] = "PASS"
        worklist["run"]["current_stage"] = "final_report"
        worklist["run"]["next_action"] = "closed"
        worklist_path.write_text(dump_worklist(worklist), encoding="utf-8")
    except (FileNotFoundError, YamlSubsetError):
        pass
    append_event(get_run_dir(project, run_id), {"type": "run_closed", "run_id": run_id})
    print(f"PASS close {run_id}", file=stdout)
    print("status: PASS", file=stdout)
    return 0


def cmd_git_gate(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        state = load_state(project, run_id)
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    status, summary, reason = collect_git_status(project)
    state["git_gate"] = {
        "status": status,
        "diff_summary": summary,
        "reason": reason,
    }
    save_state(project, run_id, state)
    append_event(get_run_dir(project, run_id), {
        "type": "git_gate",
        "status": status,
        "reason": reason,
    })
    if status == "PASS":
        print(f"PASS git gate {run_id}", file=stdout)
        print(summary, file=stdout)
        return 0
    print(f"NEED_HUMAN git gate {run_id}", file=stdout)
    print(f"- {reason}", file=stdout)
    return 1
