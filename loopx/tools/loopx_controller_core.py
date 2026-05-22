#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from loopx_controller_artifacts import (
    empty_spec_sections,
    interview_has_unanswered_placeholders,
    interview_questions,
    missing_spec_sections,
    render_interview_artifact,
    render_spec_artifact,
)
from loopx_controller_contracts import (
    CONFIRMATION_GATE_STAGES,
    DEFAULT_STAGE_OWNERS,
    FULL_REQUIRED_PASS_STAGES,
    PASSING_STATUSES,
    STAGES,
    STAGE_DISPLAY_NAMES,
    STAGE_RESULT_FILES,
    STAGE_SEQUENCE,
    STAGE_STATUSES,
)
from loopx_controller_io import (
    append_event,
    get_run_dir,
    load_schema,
    load_state,
    load_worklist,
    loopx_root,
    project_path,
    read_json,
    run_root,
    save_state,
    validate_schema,
    write_json,
)
from loopx_controller_yaml import YamlSubsetError, dump_worklist, parse_yaml_subset

def slugify(text):
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return slug[:48] or "loopx-run"


def default_run_id(requirement):
    return f"{datetime.now().strftime('%Y-%m-%d')}-{slugify(requirement)}"


def yaml_string(value):
    return json.dumps(str(value), ensure_ascii=False)


def render_worklist(run_id, requirement, mode):
    stage_lines = []
    for index, stage in enumerate(STAGE_SEQUENCE):
        stage_lines.extend([
            f"  - id: {yaml_string(f'{index:02d}')}",
            f"    stage: {stage}",
            f"    name: {STAGE_DISPLAY_NAMES[stage]}",
            "    status: PENDING",
            "    required: true",
            "    evidence: \"\"",
        ])
    return f"""run:
  id: {yaml_string(run_id)}
  requirement: {yaml_string(requirement)}
  mode: {mode}
  status: ACTIVE
  current_stage: environment_check
  next_action: requirement_intake

spec:
  status: NOT_CREATED
  path: {yaml_string(f".loopx/runs/{run_id}/artifacts/spec.md")}
  approved: false

interview:
  status: NOT_STARTED
  unanswered_questions: 0
  path: {yaml_string(f".loopx/runs/{run_id}/artifacts/interview.md")}

stages:
{chr(10).join(stage_lines)}

items: []
"""


def stage_index(stage):
    return STAGE_SEQUENCE.index(stage)


def stages_before(stage):
    return STAGE_SEQUENCE[:stage_index(stage)]


def first_changes_required(stages):
    for stage in STAGE_SEQUENCE:
        if stages.get(stage) in {"CHANGES_REQUIRED", "BLOCKED"}:
            return stage
    return None


def confirmation_next_action(stage):
    return f"confirm-stage --stage {stage}"


def pending_confirmation_message(stage):
    return f"{stage} is waiting for user confirmation; run {confirmation_next_action(stage)}"


def is_waiting_confirmation(stage, status):
    return stage in CONFIRMATION_GATE_STAGES and status == "NEED_HUMAN"


def stored_stage_status(stage, status):
    if stage in CONFIRMATION_GATE_STAGES and status == "PASS":
        return "NEED_HUMAN"
    return status


def stage_result_next_action(stage, status, stored_status, return_to, next_action):
    if stored_status == "NEED_HUMAN":
        return confirmation_next_action(stage)
    if next_action:
        return next_action
    if status == "CHANGES_REQUIRED":
        return return_to
    return default_next_stage(stage)


def build_stage_result(state, stage, agent_result, stored_status, return_to, next_action, evidence, affected_work_items, blocked_reason):
    snapshot_state = dict(state)
    snapshot_state["stages"] = dict(state.get("stages", {}))
    snapshot_state["stages"][stage] = stored_status
    return {
        "stage": stage,
        "status": stored_status,
        "agent_result": agent_result,
        "mode": state.get("mode", ""),
        "summary": "",
        "return_to": return_to,
        "next_action": next_action,
        "affected_work_items": affected_work_items or [],
        "evidence": evidence,
        "tracking_snapshot": build_tracking_snapshot(snapshot_state),
        "gate": {
            "result": stored_status,
            "blocking_issues": [blocked_reason] if blocked_reason else [],
            "non_blocking_issues": [],
        },
        "user_confirmation_required": stored_status in {"CHANGES_REQUIRED", "BLOCKED", "NEED_HUMAN"},
        "blocked_reason": blocked_reason,
    }


def risk_config():
    return parse_yaml_subset((loopx_root() / "risk.yml").read_text(encoding="utf-8"))


def resolve_mode(mode, risk_tags):
    if mode != "auto":
        return mode
    config = risk_config()
    critical = set(config.get("critical_triggers", []))
    score_rules = config.get("score_rules", {})
    thresholds = config.get("thresholds", {})
    if critical.intersection(risk_tags):
        return "FULL"
    score = sum(int(score_rules.get(tag, 0)) for tag in risk_tags)
    if score >= int(thresholds.get("full_min", 6)):
        return "FULL"
    if score <= int(thresholds.get("light_max", 1)):
        return "LIGHT"
    return "STANDARD"


def mode_rank(mode):
    return {"LIGHT": 1, "STANDARD": 2, "FULL": 3}.get(mode, 0)


def interview_state(run_id, mode):
    return {
        "required": True,
        "mode": mode,
        "status": "NOT_STARTED",
        "artifact": f".loopx/runs/{run_id}/artifacts/interview.md",
        "unanswered_questions": 0,
        "can_skip": False,
    }


def spec_state(run_id):
    return {
        "required": True,
        "status": "NOT_CREATED",
        "artifact": f".loopx/runs/{run_id}/artifacts/spec.md",
        "approved": False,
        "gate_result": "PENDING",
    }


def mode_decision_state(mode, risk_tags, selected_by):
    confirmed = selected_by != "auto"
    return {
        "recommended": mode,
        "selected": mode if confirmed else "",
        "selection_status": "CONFIRMED" if confirmed else "NEED_HUMAN",
        "selected_by": selected_by,
        "reason": risk_tags,
        "accepted_risk": {
            "selected_lower_than_recommended": False,
            "reason": "",
        },
    }


def transition_policy_state():
    return {
        "require_interview_before_spec": True,
        "require_spec_before_design": True,
        "require_mode_before_design": True,
        "require_design_review_before_development": True,
        "require_git_gate_before_final_report": True,
    }


def tracking_state(run_id):
    return {
        "show_on_every_update": True,
        "worklist": f".loopx/runs/{run_id}/worklist.yml",
    }


def update_worklist_state(project, state, stage=None, stage_status=None):
    try:
        worklist_path, worklist = load_worklist(project, state)
    except (FileNotFoundError, YamlSubsetError):
        return
    worklist.setdefault("run", {})["current_stage"] = state.get("current_stage")
    worklist["run"]["next_action"] = state.get("next_action", "")
    if "spec" in state:
        worklist["spec"] = {
            "status": state["spec"].get("status", ""),
            "path": state["spec"].get("artifact", ""),
            "approved": state["spec"].get("approved", False),
        }
    if "interview" in state:
        worklist["interview"] = {
            "status": state["interview"].get("status", ""),
            "unanswered_questions": state["interview"].get("unanswered_questions", 0),
            "path": state["interview"].get("artifact", ""),
        }
    if stage and "stages" in worklist:
        for item in worklist.get("stages") or []:
            if item.get("stage") == stage:
                item["status"] = stage_status or item.get("status", "PENDING")
                artifact = ""
                if stage == "requirement_interview":
                    artifact = state.get("interview", {}).get("artifact", "")
                if stage in {"spec_draft", "spec_review"}:
                    artifact = state.get("spec", {}).get("artifact", "")
                if not artifact and stage in STAGE_RESULT_FILES:
                    artifact = f".loopx/runs/{state.get('run_id')}/stage-results/{STAGE_RESULT_FILES[stage]}"
                item["evidence"] = artifact or item.get("evidence", "")
    worklist_path.write_text(dump_worklist(worklist), encoding="utf-8")


def build_tracking_snapshot(state):
    current = state.get("current_stage", "")
    completed = state.get("stages", {})
    snapshot = []
    for index, stage in enumerate(STAGE_SEQUENCE):
        snapshot.append({
            "id": f"{index:02d}",
            "stage": stage,
            "name": STAGE_DISPLAY_NAMES[stage],
            "status": completed.get(stage, "IN_PROGRESS" if stage == current else "PENDING"),
        })
    return snapshot


def format_tracking(state):
    lines = [
        "LoopX 追踪",
        "",
        f"运行: {state.get('run_id')}",
        f"模式: {state.get('mode')}",
        f"当前阶段: {STAGE_DISPLAY_NAMES.get(state.get('current_stage'), state.get('current_stage'))}",
        f"需求规格: {state.get('spec', {}).get('status', 'UNKNOWN')}",
        "Git 门禁: PENDING",
        "",
        "阶段:",
    ]
    current = state.get("current_stage")
    statuses = state.get("stages", {})
    for index, stage in enumerate(STAGE_SEQUENCE):
        status = statuses.get(stage)
        marker = "[>]" if stage == current else "[x]" if status in PASSING_STATUSES else "[ ]"
        lines.append(f"{marker} {index:02d} {STAGE_DISPLAY_NAMES[stage]}")
    return "\n".join(lines) + "\n"


def default_next_stage(stage):
    index = stage_index(stage)
    if index + 1 >= len(STAGE_SEQUENCE):
        return "final_report"
    return STAGE_SEQUENCE[index + 1]


def stage_result_path(directory, stage):
    return directory / "stage-results" / STAGE_RESULT_FILES[stage]


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
            "stage_result": f".loopx/runs/{run_id}/stage-results/{STAGE_RESULT_FILES[stage]}",
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
        "evidence_matrix": evidence_matrix,
        "ci_coverage": {
            "status": "LOCAL_ONLY",
            "summary": "CI/remote verification not executed by local close",
        },
        "uncovered": [
            "CI/remote verification not covered by local close",
        ],
    }


def repair_ticket_root(project, run_id, state=None):
    state = state or load_state(project, run_id)
    path = Path(state.get("repair_tickets") or f".loopx/runs/{run_id}/repair-tickets")
    if not path.is_absolute():
        path = project / path
    return path


def repair_ticket_path(project, run_id, item_id, state=None):
    return repair_ticket_root(project, run_id, state) / f"{item_id}.json"


def read_repair_ticket(project, run_id, item_id, state=None):
    return read_json(repair_ticket_path(project, run_id, item_id, state))


def write_repair_ticket(project, run_id, item_id, ticket, state=None):
    root = repair_ticket_root(project, run_id, state)
    root.mkdir(parents=True, exist_ok=True)
    write_json(root / f"{item_id}.json", ticket)


def iter_repair_tickets(project, run_id, state=None):
    root = repair_ticket_root(project, run_id, state)
    if not root.exists():
        return []
    tickets = []
    for path in sorted(root.glob("*.json")):
        try:
            tickets.append(read_json(path))
        except ValueError:
            continue
    return tickets


def open_repair_tickets_for_stage(project, run_id, stage, state=None):
    return [
        ticket for ticket in iter_repair_tickets(project, run_id, state)
        if ticket.get("status") == "OPEN" and ticket.get("return_to") == stage
    ]


def validate_requirement_interview_pass(project, run_id, state):
    interview = state.setdefault("interview", interview_state(run_id, state.get("mode", "")))
    artifact = project_path(project, interview.get("artifact"))
    if not artifact.exists():
        raise ValueError(f"requirement_interview cannot PASS before interview artifact exists: {interview.get('artifact')}")
    try:
        text = artifact.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"requirement_interview artifact cannot be read: {exc}") from exc
    if interview_has_unanswered_placeholders(text):
        raise ValueError("requirement_interview cannot PASS before interview questions are answered")
    interview["unanswered_questions"] = 0
    interview["blocking_questions"] = []


def apply_stage_metadata(state, run_id, stage, status, stored_status=None):
    effective_status = stored_status or status
    if stage == "requirement_interview":
        state.setdefault("interview", interview_state(run_id, state.get("mode", "")))["status"] = effective_status
    if stage == "spec_review":
        spec = state.setdefault("spec", spec_state(run_id))
        spec["gate_result"] = effective_status
        spec["approved"] = effective_status in PASSING_STATUSES
        if effective_status in PASSING_STATUSES:
            spec["status"] = "APPROVED"
    if stage == "mode_selection":
        mode_decision = state.setdefault("mode_decision", mode_decision_state(state.get("mode", ""), state.get("risk_tags", []), "auto"))
        if effective_status in PASSING_STATUSES:
            mode_decision["selection_status"] = "CONFIRMED"


def apply_stage_progression(state, stage, status, stored_status, return_to, next_action):
    state["active_agent"] = state.get("stage_owners", DEFAULT_STAGE_OWNERS).get(stage, stage)
    if stored_status == "NEED_HUMAN":
        state["next_action"] = next_action
    if status != "CHANGES_REQUIRED":
        return
    target = return_to or stage
    state["current_stage"] = target
    state["active_agent"] = state.get("stage_owners", DEFAULT_STAGE_OWNERS).get(target, target)
    state["next_action"] = f"repair_{target}"
    for later_stage in STAGE_SEQUENCE[stage_index(target) + 1:]:
        if later_stage != stage:
            state["stages"].pop(later_stage, None)


def record_stage_result(project, run_id, stage, status, evidence, return_to="", next_action=None, affected_work_items=None, blocked_reason=""):
    directory = get_run_dir(project, run_id)
    state = load_state(project, run_id)
    if stage == "requirement_interview" and status == "PASS":
        validate_requirement_interview_pass(project, run_id, state)
    agent_result = status
    stored_status = stored_stage_status(stage, status)
    computed_next_action = stage_result_next_action(stage, status, stored_status, return_to, next_action)
    result = build_stage_result(
        state,
        stage,
        agent_result,
        stored_status,
        return_to,
        computed_next_action,
        evidence,
        affected_work_items,
        blocked_reason,
    )
    write_json(stage_result_path(directory, stage), result)
    state.setdefault("stages", {})[stage] = stored_status
    apply_stage_metadata(state, run_id, stage, status, stored_status)
    apply_stage_progression(state, stage, status, stored_status, return_to, computed_next_action)
    save_state(project, run_id, state)
    append_event(directory, {
        "type": "stage_recorded",
        "stage": stage,
        "status": stored_status,
        "agent_result": agent_result,
        "return_to": return_to,
    })
    return result


def latest_run_id(project):
    root = run_root(project)
    if not root.exists():
        return None
    runs = [path for path in root.iterdir() if path.is_dir()]
    if not runs:
        return None
    return max(runs, key=lambda path: path.stat().st_mtime).name


def resolve_run_id(project, run_id):
    if run_id:
        return run_id
    resolved = latest_run_id(project)
    if not resolved:
        raise ValueError("no LoopX runs found")
    return resolved


def strict_validation_errors(project, run_id, state, worklist):
    errors = []
    for key in ("interview", "spec", "mode_decision", "tracking", "transition_policy", "git_gate"):
        if key not in state or state[key] is None:
            errors.append(f"state.{key} is required for strict validation")
    if errors:
        return errors
    for state_key, schema_name in (
        ("interview", "interview"),
        ("spec", "spec"),
        ("mode_decision", "mode"),
        ("tracking", "tracking"),
    ):
        errors.extend(validate_schema(state[state_key], load_schema(schema_name), f"state.{state_key}"))

    mode_decision = state.get("mode_decision", {})
    if not mode_decision.get("recommended"):
        errors.append("state.mode_decision.recommended is required for strict validation")
    if not mode_decision.get("selected"):
        errors.append("state.mode_decision.selected is required for strict validation")
    if mode_decision.get("selection_status") != "CONFIRMED":
        errors.append("state.mode_decision.selection_status must be CONFIRMED for strict validation")
    if mode_rank(mode_decision.get("recommended")) > mode_rank(mode_decision.get("selected")):
        accepted = mode_decision.get("accepted_risk", {})
        if not accepted.get("selected_lower_than_recommended") or not accepted.get("reason"):
            errors.append("state.mode_decision.accepted_risk.reason is required when selected mode is lower than recommended")
    if state.get("mode") == "FULL" or mode_decision.get("selected") == "FULL":
        for stage in ("solution_review", "test_review", "health_gate", "release_readiness"):
            if state.get("stages", {}).get(stage) == "SKIPPED":
                errors.append(f"FULL mode cannot skip {stage}")
    if state.get("stages", {}).get("final_report") == "PASS":
        if state.get("stages", {}).get("release_readiness") not in PASSING_STATUSES:
            errors.append("release_readiness must be PASS before final_report PASS")
        git_gate = state.get("git_gate", {})
        if git_gate.get("status") != "PASS":
            errors.append("state.git_gate.status must be PASS before final_report PASS")
        if not git_gate.get("diff_summary"):
            errors.append("state.git_gate.diff_summary is required for final_report PASS")

    worklist_stages = worklist.get("stages") or []
    worklist_by_stage = {stage.get("stage"): stage for stage in worklist_stages if isinstance(stage, dict)}
    seen = set(worklist_by_stage)
    for stage in STAGE_SEQUENCE:
        if stage not in seen:
            errors.append(f"worklist.stages must include {stage}")
    if worklist.get("run", {}).get("current_stage") != state.get("current_stage"):
        errors.append("worklist.run.current_stage must match state.current_stage")
    for stage, status in state.get("stages", {}).items():
        worklist_stage = worklist_by_stage.get(stage)
        if worklist_stage and worklist_stage.get("status") != status:
            errors.append(f"worklist.stages[{stage}].status must match state.stages.{stage}")

    directory = get_run_dir(project, run_id)
    for stage, status in state.get("stages", {}).items():
        if status not in PASSING_STATUSES:
            continue
        result_path = stage_result_path(directory, stage)
        if not result_path.exists():
            errors.append(f"{stage} is {status} but {result_path.name} is missing")
            continue
        try:
            result = read_json(result_path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not result.get("tracking_snapshot"):
            errors.append(f"{result_path.name}.tracking_snapshot is required for strict validation")
        else:
            snapshot_stages = {item.get("stage") for item in result.get("tracking_snapshot", []) if isinstance(item, dict)}
            if snapshot_stages != set(STAGE_SEQUENCE):
                errors.append(f"{result_path.name}.tracking_snapshot must include all LoopX stages")
        if stage in CONFIRMATION_GATE_STAGES and status == "PASS":
            if (
                not result.get("confirmed_by")
                or not result.get("confirmed_at")
                or not result.get("confirmation_evidence")
            ):
                errors.append(f"{stage} PASS requires confirmation metadata")

    for stage, key in (("requirement_interview", "interview"), ("spec_review", "spec")):
        if state.get("stages", {}).get(stage) in PASSING_STATUSES:
            artifact = Path(state.get(key, {}).get("artifact", ""))
            if not artifact.is_absolute():
                artifact = project / artifact
            if not artifact.exists():
                errors.append(f"state.{key}.artifact does not exist for PASS {stage}")
                continue
            if stage == "requirement_interview" and state.get("interview", {}).get("unanswered_questions", 0) != 0:
                errors.append("state.interview.unanswered_questions must be 0 for PASS requirement_interview")
            if stage == "requirement_interview":
                try:
                    text = artifact.read_text(encoding="utf-8")
                except OSError as exc:
                    errors.append(f"state.interview.artifact cannot be read: {exc}")
                    continue
                if interview_has_unanswered_placeholders(text):
                    errors.append("interview.md still contains unanswered placeholders")
            if stage == "spec_review":
                try:
                    text = artifact.read_text(encoding="utf-8")
                except OSError as exc:
                    errors.append(f"state.spec.artifact cannot be read: {exc}")
                    continue
                for section in missing_spec_sections(text):
                    errors.append(f"spec.md missing required section: {section}")
                for section in empty_spec_sections(text):
                    errors.append(f"spec.md required section is empty: {section}")
    if state.get("stages", {}).get("final_report") == "PASS" and (state.get("mode") == "FULL" or mode_decision.get("selected") == "FULL"):
        for stage in FULL_REQUIRED_PASS_STAGES:
            if state.get("stages", {}).get(stage) not in PASSING_STATUSES:
                errors.append(f"FULL mode requires {stage} PASS before final_report PASS")
    return errors


def validate_run(project, run_id, strict=False):
    errors = []
    directory = get_run_dir(project, run_id)
    state_path = directory / "state.json"
    try:
        state = read_json(state_path)
    except ValueError as exc:
        return [str(exc)]

    errors.extend(validate_schema(state, load_schema("state")))
    if state.get("run_id") != run_id:
        errors.append("state.run_id must match selected run")
    if state.get("current_stage") and state["current_stage"] not in STAGES:
        errors.append("current_stage is not a known LoopX stage")
    for stage, status in state.get("stages", {}).items():
        if stage not in STAGES:
            errors.append(f"stages.{stage} is not a known LoopX stage")
        if status not in STAGE_STATUSES:
            errors.append(f"stages.{stage} has invalid status {status}")

    worklist_rel = state.get("worklist") or f".loopx/runs/{run_id}/worklist.yml"
    worklist_path = Path(worklist_rel)
    if not worklist_path.is_absolute():
        worklist_path = project / worklist_path
    worklist = None
    try:
        worklist = parse_yaml_subset(worklist_path.read_text(encoding="utf-8"))
        errors.extend(validate_schema(worklist, load_schema("worklist")))
    except FileNotFoundError:
        errors.append(f"{worklist_path} does not exist")
    except YamlSubsetError as exc:
        errors.append(f"{worklist_path} is not valid LoopX YAML: {exc}")

    stage_result_root = directory / "stage-results"
    if stage_result_root.exists():
        for result_path in sorted(stage_result_root.glob("*.json")):
            try:
                result = read_json(result_path)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            errors.extend(validate_schema(result, load_schema("stage-result"), result_path.name))
    if strict and worklist is not None:
        errors.extend(strict_validation_errors(project, run_id, state, worklist))
    return errors


def auto_pass_environment_check(project, run_id):
    directory = get_run_dir(project, run_id)
    state = load_state(project, run_id)
    next_action = "requirement_intake"
    result = build_stage_result(
        state,
        "environment_check",
        "PASS",
        "PASS",
        "",
        next_action,
        [
            "LoopX controller initialized run state",
            "Project root resolved",
            "Python controller runtime available",
        ],
        [],
        "",
    )
    write_json(stage_result_path(directory, "environment_check"), result)
    state.setdefault("stages", {})["environment_check"] = "PASS"
    state["current_stage"] = "requirement_intake"
    state["active_agent"] = state.get("stage_owners", DEFAULT_STAGE_OWNERS)["requirement_intake"]
    state["next_action"] = next_action
    save_state(project, run_id, state)
    update_worklist_state(project, state, "environment_check", "PASS")
    append_event(directory, {
        "type": "stage_auto_passed",
        "stage": "environment_check",
        "next_action": next_action,
    })
    return result


def cmd_init(args, stdout):
    project = Path(args.project).resolve()
    run_id = args.run_id or default_run_id(args.requirement)
    risk_tags = args.risk_tags or []
    mode = resolve_mode(args.mode, risk_tags)
    directory = get_run_dir(project, run_id)
    if directory.exists():
        print(f"run already exists: {run_id}", file=stdout)
        return 1
    directory.mkdir(parents=True)
    (directory / "artifacts").mkdir()
    (directory / "stage-results").mkdir()
    (directory / "repair-tickets").mkdir()

    state = {
        "run_id": run_id,
        "requirement": args.requirement,
        "mode": mode,
        "status": "ACTIVE",
        "current_stage": "environment_check",
        "next_action": "requirement_intake",
        "active_agent": DEFAULT_STAGE_OWNERS["environment_check"],
        "stage_owners": DEFAULT_STAGE_OWNERS,
        "risk_tags": risk_tags,
        "confirmation_policy": "verification_gated",
        "max_auto_repair": 2,
        "worklist": f".loopx/runs/{run_id}/worklist.yml",
        "events": f".loopx/runs/{run_id}/events.jsonl",
        "repair_tickets": f".loopx/runs/{run_id}/repair-tickets",
        "loop_attempts": {},
        "stages": {},
        "interview": interview_state(run_id, mode),
        "spec": spec_state(run_id),
        "mode_decision": mode_decision_state(mode, risk_tags, "auto" if args.mode == "auto" else "user"),
        "tracking": tracking_state(run_id),
        "transition_policy": transition_policy_state(),
        "git_gate": {
            "status": "PENDING",
            "diff_summary": "",
        },
    }
    write_json(directory / "state.json", state)
    (directory / "worklist.yml").write_text(render_worklist(run_id, args.requirement, mode), encoding="utf-8")
    event = {"type": "run_created", "run_id": run_id, "current_stage": "environment_check"}
    (directory / "events.jsonl").write_text(json.dumps(event, ensure_ascii=False) + "\n", encoding="utf-8")
    auto_pass_environment_check(project, run_id)
    print(f"created run {run_id}", file=stdout)
    print(f"mode: {mode}", file=stdout)
    print(f"recommended mode: {mode}", file=stdout)
    print("environment_check: PASS", file=stdout)
    if args.mode == "auto":
        print("mode selection: NEED_HUMAN", file=stdout)
    print(f"state: {state['worklist'].rsplit('/', 1)[0]}/state.json", file=stdout)
    return 0


def cmd_status(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        state = read_json(get_run_dir(project, run_id) / "state.json")
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    if args.tracking:
        print(format_tracking(state), end="", file=stdout)
        return 0
    print(f"run_id: {state.get('run_id')}", file=stdout)
    print(f"mode: {state.get('mode')}", file=stdout)
    print(f"status: {state.get('status')}", file=stdout)
    print(f"current_stage: {state.get('current_stage')}", file=stdout)
    print(f"next_action: {state.get('next_action', 'validate')}", file=stdout)
    return 0


def cmd_validate(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    errors = validate_run(project, run_id, strict=args.strict)
    if errors:
        print(f"FAIL {run_id}", file=stdout)
        for error in errors:
            print(f"- {error}", file=stdout)
        return 1
    print(f"PASS {run_id}", file=stdout)
    return 0


def cmd_gate(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    errors = validate_run(project, run_id, strict=True)
    if errors:
        print(f"FAIL gate {run_id}", file=stdout)
        print("strict validation: FAIL", file=stdout)
        for error in errors:
            print(f"- {error}", file=stdout)
        return 1
    print(f"PASS gate {run_id}", file=stdout)
    print("strict validation: PASS", file=stdout)
    return 0


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
    errors = validate_run(project, run_id, strict=True)
    if errors:
        print(f"FAIL close {run_id}", file=stdout)
        print("- strict gate failed", file=stdout)
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


def cmd_interview(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        state = load_state(project, run_id)
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    artifact = project_path(project, state.setdefault("interview", interview_state(run_id, state.get("mode", ""))).get("artifact"))
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(render_interview_artifact(state), encoding="utf-8")
    questions = interview_questions(state)
    state["current_stage"] = "requirement_interview"
    state["active_agent"] = state.get("stage_owners", DEFAULT_STAGE_OWNERS)["requirement_interview"]
    state["next_action"] = "answer interview questions"
    state["interview"]["status"] = "IN_PROGRESS"
    state["interview"]["unanswered_questions"] = len(questions)
    state["interview"]["blocking_questions"] = [item["question"] for item in questions]
    save_state(project, run_id, state)
    update_worklist_state(project, state, "requirement_interview", "IN_PROGRESS")
    append_event(get_run_dir(project, run_id), {"type": "artifact_generated", "stage": "requirement_interview", "artifact": state["interview"]["artifact"]})
    print(f"generated interview: {state['interview']['artifact']}", file=stdout)
    print("请回答以下需求采访问题：", file=stdout)
    for index, item in enumerate(questions, start=1):
        print(f"Q{index}: {item['question']}", file=stdout)
        print(f"  为什么需要: {item['reason']}", file=stdout)
    print("回答后请更新 interview.md，再记录 requirement_interview PASS；控制器会先进入 NEED_HUMAN 等待确认。", file=stdout)
    print("current_stage: requirement_interview", file=stdout)
    return 0


def cmd_spec(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        state = load_state(project, run_id)
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    interview_status = state.get("stages", {}).get("requirement_interview")
    if is_waiting_confirmation("requirement_interview", interview_status):
        print("FAIL spec blocked", file=stdout)
        print(f"- {pending_confirmation_message('requirement_interview')}", file=stdout)
        return 1
    if interview_status not in PASSING_STATUSES:
        print("FAIL spec blocked", file=stdout)
        print("- requirement_interview must be PASS before spec_draft", file=stdout)
        return 1
    interview_artifact = project_path(project, state.setdefault("interview", interview_state(run_id, state.get("mode", ""))).get("artifact"))
    if not interview_artifact.exists():
        print("FAIL spec blocked", file=stdout)
        print(f"- interview artifact is missing: {state['interview']['artifact']}", file=stdout)
        return 1
    interview_text = interview_artifact.read_text(encoding="utf-8")
    if state.get("interview", {}).get("unanswered_questions", 0) != 0 or interview_has_unanswered_placeholders(interview_text):
        print("FAIL spec blocked", file=stdout)
        print("- interview questions must be answered before spec_draft", file=stdout)
        return 1
    spec = state.setdefault("spec", spec_state(run_id))
    artifact = project_path(project, spec.get("artifact"))
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(render_spec_artifact(state), encoding="utf-8")
    state["current_stage"] = "spec_draft"
    state["active_agent"] = state.get("stage_owners", DEFAULT_STAGE_OWNERS)["spec_draft"]
    state["next_action"] = "record-stage --stage spec_draft --status PASS"
    spec["status"] = "DRAFT"
    spec["approved"] = False
    spec["gate_result"] = "PENDING"
    save_state(project, run_id, state)
    update_worklist_state(project, state, "spec_draft", "IN_PROGRESS")
    append_event(get_run_dir(project, run_id), {"type": "artifact_generated", "stage": "spec_draft", "artifact": spec["artifact"]})
    print(f"generated spec: {spec['artifact']}", file=stdout)
    print("current_stage: spec_draft", file=stdout)
    return 0


def cmd_mode(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        state = load_state(project, run_id)
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    if state.get("stages", {}).get("spec_review") not in PASSING_STATUSES:
        print("FAIL mode blocked", file=stdout)
        print("- spec_review must be PASS before mode_selection", file=stdout)
        return 1
    selected = args.select
    decision = state.setdefault("mode_decision", mode_decision_state(state.get("mode", selected), state.get("risk_tags", []), "auto"))
    recommended = decision.get("recommended") or state.get("mode")
    downgraded = mode_rank(recommended) > mode_rank(selected)
    if downgraded and not args.accepted_risk:
        print("FAIL mode blocked", file=stdout)
        print("- accepted risk reason is required when selected mode is lower than recommended", file=stdout)
        return 1
    state["mode"] = selected
    state["current_stage"] = "mode_selection"
    state["active_agent"] = state.get("stage_owners", DEFAULT_STAGE_OWNERS)["mode_selection"]
    state["next_action"] = "solution_design"
    decision["selected"] = selected
    decision["selection_status"] = "CONFIRMED"
    decision["selected_by"] = "user"
    decision.setdefault("accepted_risk", {})
    decision["accepted_risk"]["selected_lower_than_recommended"] = downgraded
    decision["accepted_risk"]["reason"] = args.accepted_risk or ""
    save_state(project, run_id, state)
    status = "ACCEPTED_RISK" if downgraded else "PASS"
    evidence = [args.accepted_risk] if args.accepted_risk else ["mode_decision"]
    record_stage_result(project, run_id, "mode_selection", status, evidence, next_action="solution_design")
    state = load_state(project, run_id)
    update_worklist_state(project, state, "mode_selection", status)
    print(f"mode selected: {selected}", file=stdout)
    print(f"recommended mode: {recommended}", file=stdout)
    print(f"stage_status: {status}", file=stdout)
    return 0


def cmd_next(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        state = load_state(project, run_id)
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    current = state.get("current_stage")
    if current not in STAGES:
        print(f"FAIL current_stage is not known: {current}", file=stdout)
        return 1
    target = default_next_stage(current)
    blockers = advance_blockers(project, run_id, state, target)
    if blockers:
        print("FAIL next blocked", file=stdout)
        for blocker in blockers:
            print(f"- {blocker}", file=stdout)
        return 1
    state["current_stage"] = target
    state["active_agent"] = state.get("stage_owners", DEFAULT_STAGE_OWNERS).get(target, target)
    state["next_action"] = default_next_stage(target)
    save_state(project, run_id, state)
    update_worklist_state(project, state, target, "IN_PROGRESS")
    append_event(get_run_dir(project, run_id), {"type": "advanced", "to": target})
    print(f"PASS advanced to {target}", file=stdout)
    return 0


def cmd_record_stage(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        result = record_stage_result(
            project,
            run_id,
            args.stage,
            args.status,
            args.evidence,
            return_to=args.return_to or "",
            next_action=args.next_action,
            affected_work_items=args.item or [],
            blocked_reason=args.blocked_reason or "",
        )
        state = load_state(project, run_id)
        update_worklist_state(project, state, args.stage, result["status"])
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    print(f"{result['status']} {result['stage']}", file=stdout)
    print(f"next_action: {result['next_action']}", file=stdout)
    return 0


def advance_blockers(project, run_id, state, target_stage):
    blockers = []
    stages = state.get("stages", {})
    for ticket in iter_repair_tickets(project, run_id, state):
        return_to = ticket.get("return_to")
        if ticket.get("status") == "OPEN" and return_to in STAGES and stage_index(return_to) < stage_index(target_stage):
            blockers.append(f"repair ticket {ticket.get('item')} must be CLOSED before {target_stage}")
    changed = first_changes_required(stages)
    if changed:
        blockers.append(f"{changed} is {stages[changed]}; return before advancing")
    for stage in stages_before(target_stage):
        if is_waiting_confirmation(stage, stages.get(stage)):
            blockers.append(pending_confirmation_message(stage))
            continue
        if stages.get(stage) not in PASSING_STATUSES:
            blockers.append(f"{stage} must be PASS before {target_stage}")
    if target_stage == "spec_draft" and stages.get("requirement_interview") not in PASSING_STATUSES:
        blockers.append("requirement_interview must be PASS before spec_draft")
    if target_stage == "solution_design":
        for stage in ("requirement_interview", "spec_review", "mode_selection"):
            if stages.get(stage) not in PASSING_STATUSES:
                message = f"{stage} must be PASS before solution_design"
                if message not in blockers:
                    blockers.append(message)
    if (
        target_stage == "development"
        and not is_waiting_confirmation("solution_review", stages.get("solution_review"))
        and stages.get("solution_review") not in PASSING_STATUSES
    ):
        blockers.append("solution_review must be PASS before development")
    return blockers


def cmd_advance(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        state = load_state(project, run_id)
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    blockers = advance_blockers(project, run_id, state, args.to)
    if blockers:
        print("FAIL advance blocked", file=stdout)
        for blocker in blockers:
            print(f"- {blocker}", file=stdout)
        return 1
    state["current_stage"] = args.to
    state["active_agent"] = state.get("stage_owners", DEFAULT_STAGE_OWNERS).get(args.to, args.to)
    state["next_action"] = default_next_stage(args.to)
    save_state(project, run_id, state)
    append_event(get_run_dir(project, run_id), {"type": "advanced", "to": args.to})
    print(f"PASS advanced to {args.to}", file=stdout)
    return 0


def business_write_blockers(state):
    blockers = []
    if state.get("current_stage") != "development":
        blockers.append("current_stage must be development")
    stages = state.get("stages", {})
    for stage in ("solution_review", "test_review"):
        if is_waiting_confirmation(stage, stages.get(stage)):
            blockers.append(pending_confirmation_message(stage))
        elif stages.get(stage) not in PASSING_STATUSES:
            blockers.append(f"{stage} must be PASS before business writes")
    changed = first_changes_required(stages)
    if changed:
        blockers.append(f"{changed} is {state['stages'][changed]}")
    return blockers


def cmd_can_write(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        state = load_state(project, run_id)
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    if args.kind == "loopx":
        print("PASS loopx writes allowed", file=stdout)
        return 0
    blockers = business_write_blockers(state)
    if blockers:
        print("FAIL business writes locked", file=stdout)
        for blocker in blockers:
            print(f"- {blocker}", file=stdout)
        return 1
    print("PASS business writes unlocked", file=stdout)
    return 0


def build_confirmation(evidence, confirmed_by):
    return {
        "confirmed_by": confirmed_by,
        "confirmed_at": datetime.now().isoformat(timespec="seconds"),
        "confirmation_evidence": evidence,
    }


def apply_confirmation_result(result, state, stage, confirmation):
    result["status"] = "PASS"
    result["next_action"] = CONFIRMATION_GATE_STAGES[stage]
    result["user_confirmation_required"] = False
    result["confirmed_by"] = confirmation["confirmed_by"]
    result["confirmed_at"] = confirmation["confirmed_at"]
    result["confirmation_evidence"] = confirmation["confirmation_evidence"]
    result["tracking_snapshot"] = build_tracking_snapshot(state)
    result.setdefault("gate", {})["result"] = "PASS"


def confirm_stage(project, run_id, stage, evidence, confirmed_by):
    if stage not in CONFIRMATION_GATE_STAGES:
        raise ValueError(f"{stage} is not a user confirmation gate")
    directory = get_run_dir(project, run_id)
    state = load_state(project, run_id)
    current_status = state.get("stages", {}).get(stage)
    if current_status != "NEED_HUMAN":
        raise ValueError(f"{stage} must be NEED_HUMAN before confirmation")
    result_path = stage_result_path(directory, stage)
    result = read_json(result_path)
    if result.get("status") != "NEED_HUMAN":
        raise ValueError(f"{result_path.name} must be NEED_HUMAN before confirmation")
    confirmation = build_confirmation(evidence, confirmed_by)
    state.setdefault("stages", {})[stage] = "PASS"
    state.setdefault("confirmations", {})[stage] = confirmation
    if stage == "requirement_interview":
        state.setdefault("interview", interview_state(run_id, state.get("mode", "")))["status"] = "PASS"
    state["next_action"] = CONFIRMATION_GATE_STAGES[stage]
    apply_confirmation_result(result, state, stage, confirmation)
    write_json(result_path, result)

    save_state(project, run_id, state)
    update_worklist_state(project, state, stage, "PASS")
    append_event(directory, {
        "type": "stage_confirmed",
        "stage": stage,
        "confirmed_by": confirmed_by,
        "evidence": evidence,
    })
    return confirmation


def cmd_confirm_stage(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        confirmation = confirm_stage(project, run_id, args.stage, args.evidence, args.confirmed_by)
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    print(f"PASS confirmed {args.stage}", file=stdout)
    print(f"confirmed_by: {confirmation['confirmed_by']}", file=stdout)
    print(f"confirmed_at: {confirmation['confirmed_at']}", file=stdout)
    print(f"next_action: {CONFIRMATION_GATE_STAGES[args.stage]}", file=stdout)
    return 0


def update_worklist_feedback(project, state, item_id, return_to, reason):
    try:
        worklist_path, worklist = load_worklist(project, state)
    except (FileNotFoundError, YamlSubsetError):
        return
    for item in worklist.get("items") or []:
        if item.get("id") == item_id:
            item["status"] = "CHANGES_REQUIRED"
            item["failed_by"] = "user_feedback"
            item["return_to"] = return_to
            changes = item.get("required_changes") or []
            if reason not in changes:
                changes.append(reason)
            item["required_changes"] = changes
    worklist["run"]["current_stage"] = return_to
    worklist_path.write_text(dump_worklist(worklist), encoding="utf-8")


def fail_review(project, run_id, from_stage, return_to, item_id, reasons):
    state = load_state(project, run_id)
    owner = state.get("stage_owners", DEFAULT_STAGE_OWNERS).get(return_to, return_to)
    attempts = state.setdefault("loop_attempts", {})
    attempt = int(attempts.get(item_id, 0)) + 1
    attempts[item_id] = attempt
    ticket = {
        "type": "review_failed",
        "item": item_id,
        "from_stage": from_stage,
        "return_to": return_to,
        "assigned_to": owner,
        "attempt": attempt,
        "status": "OPEN",
        "required_changes": reasons,
        "artifact": "",
        "revision": 0,
        "changes_from_review": [],
    }
    state["current_stage"] = return_to
    state["next_action"] = f"repair_{return_to}"
    state["active_agent"] = owner
    state.setdefault("stages", {})[from_stage] = "CHANGES_REQUIRED"
    for later_stage in STAGE_SEQUENCE[stage_index(return_to) + 1:]:
        if later_stage != from_stage:
            state["stages"].pop(later_stage, None)
    save_state(project, run_id, state)
    write_repair_ticket(project, run_id, item_id, ticket, state)
    for reason in reasons:
        update_worklist_feedback(project, state, item_id, return_to, reason)
    record_stage_result(
        project,
        run_id,
        from_stage,
        "CHANGES_REQUIRED",
        reasons,
        return_to=return_to,
        next_action=f"repair_{return_to}",
        affected_work_items=[item_id],
    )
    return ticket


def cmd_fail_review(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        ticket = fail_review(project, run_id, args.from_stage, args.return_to, args.item, args.reason)
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    print(f"CHANGES_REQUIRED {args.from_stage}", file=stdout)
    print(f"repair_ticket: {ticket['item']}", file=stdout)
    print(f"return_to: {ticket['return_to']}", file=stdout)
    print(f"assigned_to: {ticket['assigned_to']}", file=stdout)
    print(f"attempt: {ticket['attempt']}", file=stdout)
    return 0


def cmd_review_feedback(args, stdout):
    args.from_stage = "solution_review"
    args.reason = [args.reason]
    return cmd_fail_review(args, stdout)


def cmd_claim_stage(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        state = load_state(project, run_id)
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    if state.get("current_stage") != args.stage:
        print(f"FAIL current_stage is {state.get('current_stage')}", file=stdout)
        return 1
    owner = state.get("stage_owners", DEFAULT_STAGE_OWNERS).get(args.stage, args.stage)
    state["active_agent"] = owner
    save_state(project, run_id, state)
    print(f"PASS claimed {args.stage}", file=stdout)
    print(f"assigned_to: {owner}", file=stdout)
    for ticket in open_repair_tickets_for_stage(project, run_id, args.stage, state):
        print(f"repair_ticket: {ticket.get('item')}", file=stdout)
        print(f"attempt: {ticket.get('attempt')}", file=stdout)
        for change in ticket.get("required_changes", []):
            print(f"required_change: {change}", file=stdout)
    return 0


def cmd_close_repair(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        state = load_state(project, run_id)
        ticket = read_repair_ticket(project, run_id, args.item, state)
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    if args.revision < 2:
        print("FAIL repair revision must be >= 2", file=stdout)
        return 1
    ticket["status"] = "CLOSED"
    ticket["artifact"] = args.artifact
    ticket["revision"] = args.revision
    ticket["changes_from_review"] = args.change
    write_repair_ticket(project, run_id, args.item, ticket, state)
    from_stage = ticket.get("from_stage")
    if from_stage:
        state.setdefault("stages", {}).pop(from_stage, None)
    save_state(project, run_id, state)
    print(f"PASS repair closed {args.item}", file=stdout)
    print(f"artifact: {args.artifact}", file=stdout)
    print(f"revision: {args.revision}", file=stdout)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="LoopX 状态控制器。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="Create a local LoopX run state.")
    init.add_argument("requirement")
    init.add_argument("--run-id")
    init.add_argument("--mode", choices=["auto", "LIGHT", "STANDARD", "FULL"], default="auto")
    init.add_argument("--risk-tags", nargs="*", default=[])
    init.add_argument("--project", default=".")
    init.set_defaults(func=cmd_init)

    status = subparsers.add_parser("status", help="Show a LoopX run status.")
    status.add_argument("run_id", nargs="?")
    status.add_argument("--tracking", action="store_true")
    status.add_argument("--project", default=".")
    status.set_defaults(func=cmd_status)

    interview = subparsers.add_parser("interview", help="Generate the requirement interview artifact.")
    interview.add_argument("run_id", nargs="?")
    interview.add_argument("--project", default=".")
    interview.set_defaults(func=cmd_interview)

    spec = subparsers.add_parser("spec", help="Generate the requirement spec artifact after interview approval.")
    spec.add_argument("run_id", nargs="?")
    spec.add_argument("--project", default=".")
    spec.set_defaults(func=cmd_spec)

    mode = subparsers.add_parser("mode", help="Record the selected LoopX execution mode.")
    mode.add_argument("run_id", nargs="?")
    mode.add_argument("--select", required=True, choices=["LIGHT", "STANDARD", "FULL"])
    mode.add_argument("--accepted-risk")
    mode.add_argument("--project", default=".")
    mode.set_defaults(func=cmd_mode)

    next_stage = subparsers.add_parser("next", help="Advance to the default next stage when gates pass.")
    next_stage.add_argument("run_id", nargs="?")
    next_stage.add_argument("--project", default=".")
    next_stage.set_defaults(func=cmd_next)

    validate = subparsers.add_parser("validate", help="Validate LoopX run state and worklist.")
    validate.add_argument("run_id", nargs="?")
    validate.add_argument("--strict", action="store_true")
    validate.add_argument("--project", default=".")
    validate.set_defaults(func=cmd_validate)

    gate = subparsers.add_parser("gate", help="Run the strict LoopX process gate.")
    gate.add_argument("run_id", nargs="?")
    gate.add_argument("--project", default=".")
    gate.set_defaults(func=cmd_gate)

    close_run = subparsers.add_parser("close", help="Close a LoopX run after the final report and strict gate pass.")
    close_run.add_argument("run_id", nargs="?")
    close_run.add_argument("--project", default=".")
    close_run.set_defaults(func=cmd_close)

    git_gate = subparsers.add_parser("git-gate", help="Record Git changed-file evidence for the final report gate.")
    git_gate.add_argument("run_id", nargs="?")
    git_gate.add_argument("--project", default=".")
    git_gate.set_defaults(func=cmd_git_gate)

    record = subparsers.add_parser("record-stage", help="Record a machine-readable LoopX stage result.")
    record.add_argument("--run-id")
    record.add_argument("--stage", required=True, choices=STAGE_SEQUENCE)
    record.add_argument("--status", required=True, choices=sorted(STAGE_STATUSES))
    record.add_argument("--evidence", action="append", default=[])
    record.add_argument("--return-to", choices=STAGE_SEQUENCE)
    record.add_argument("--next-action")
    record.add_argument("--item", action="append")
    record.add_argument("--blocked-reason")
    record.add_argument("--project", default=".")
    record.set_defaults(func=cmd_record_stage)

    confirm = subparsers.add_parser("confirm-stage", help="Confirm a user-gated LoopX stage after agent review.")
    confirm.add_argument("--run-id")
    confirm.add_argument("--stage", required=True, choices=sorted(CONFIRMATION_GATE_STAGES))
    confirm.add_argument("--evidence", action="append", required=True)
    confirm.add_argument("--confirmed-by", default="user")
    confirm.add_argument("--project", default=".")
    confirm.set_defaults(func=cmd_confirm_stage)

    advance = subparsers.add_parser("advance", help="Advance only when previous LoopX gates pass.")
    advance.add_argument("--run-id")
    advance.add_argument("--to", required=True, choices=STAGE_SEQUENCE)
    advance.add_argument("--project", default=".")
    advance.set_defaults(func=cmd_advance)

    can_write = subparsers.add_parser("can-write", help="Check whether writes are unlocked.")
    can_write.add_argument("--run-id")
    can_write.add_argument("--kind", choices=["business", "loopx"], default="business")
    can_write.add_argument("--project", default=".")
    can_write.set_defaults(func=cmd_can_write)

    fail_review_parser = subparsers.add_parser("fail-review", help="Create a review-driven repair ticket and return to the owner stage.")
    fail_review_parser.add_argument("--run-id")
    fail_review_parser.add_argument("--from", dest="from_stage", required=True, choices=STAGE_SEQUENCE)
    fail_review_parser.add_argument("--return-to", required=True, choices=STAGE_SEQUENCE)
    fail_review_parser.add_argument("--item", required=True)
    fail_review_parser.add_argument("--reason", action="append", required=True)
    fail_review_parser.add_argument("--project", default=".")
    fail_review_parser.set_defaults(func=cmd_fail_review)

    claim = subparsers.add_parser("claim-stage", help="Claim the current stage and show open repair tickets for its owner role.")
    claim.add_argument("stage", choices=STAGE_SEQUENCE)
    claim.add_argument("--run-id")
    claim.add_argument("--project", default=".")
    claim.set_defaults(func=cmd_claim_stage)

    close = subparsers.add_parser("close-repair", help="Close a repair ticket after updating the original artifact revision.")
    close.add_argument("--run-id")
    close.add_argument("--item", required=True)
    close.add_argument("--artifact", required=True)
    close.add_argument("--revision", required=True, type=int)
    close.add_argument("--change", action="append", required=True)
    close.add_argument("--project", default=".")
    close.set_defaults(func=cmd_close_repair)

    feedback = subparsers.add_parser("review-feedback", help="Record user review feedback and return to a prior stage.")
    feedback.add_argument("--run-id")
    feedback.add_argument("--item", required=True)
    feedback.add_argument("--return-to", required=True, choices=STAGE_SEQUENCE)
    feedback.add_argument("--reason", required=True)
    feedback.add_argument("--project", default=".")
    feedback.set_defaults(func=cmd_review_feedback)
    return parser


def main(argv=None, stdout=None):
    stdout = stdout or sys.stdout
    args = build_parser().parse_args(argv)
    return args.func(args, stdout)


if __name__ == "__main__":
    sys.exit(main())
