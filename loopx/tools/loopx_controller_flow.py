#!/usr/bin/env python3
"""Stage progression rules for the LoopX controller.

所有阶段推进、确认和写入保护都从这里走；命令函数只负责调用，
不要在命令层绕开这些放行条件。
"""

from datetime import datetime

from loopx_controller_artifacts import interview_has_unanswered_placeholders
from loopx_controller_contracts import (
    CONFIRMATION_GATE_STAGES,
    DEFAULT_STAGE_OWNERS,
    PASSING_STATUSES,
    STAGES,
    STAGE_RESULT_FILES,
    STAGE_SEQUENCE,
)
from loopx_controller_io import (
    append_event,
    get_run_dir,
    load_state,
    project_path,
    read_json,
    save_state,
    write_json,
)
from loopx_controller_state import (
    build_tracking_snapshot,
    interview_state,
    mode_decision_state,
    spec_state,
    update_worklist_state,
)
from loopx_controller_tickets import iter_repair_tickets


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


def default_next_stage(stage):
    index = stage_index(stage)
    if index + 1 >= len(STAGE_SEQUENCE):
        return "final_report"
    return STAGE_SEQUENCE[index + 1]


def stage_result_path(directory, stage):
    return directory / "stage-results" / STAGE_RESULT_FILES[stage]


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
    # 回退会清理后续阶段，防止旧 PASS 继续影响新的方案或实现。
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
