#!/usr/bin/env python3
"""LoopX controller command coordinator.

核心文件只保留 CLI 协调逻辑；状态构造、阶段流转、严格检查、返工和收口
分别放到专用模块，避免一个文件同时承载所有规则。
"""

import argparse
import json
import sys
from pathlib import Path

from loopx_controller_artifacts import (
    interview_has_unanswered_placeholders,
    interview_questions,
    render_interview_artifact,
    render_spec_artifact,
)
from loopx_controller_compound import cmd_compound, cmd_validate_learning
from loopx_controller_contracts import (
    CONFIRMATION_GATE_STAGES,
    DEFAULT_STAGE_OWNERS,
    PASSING_STATUSES,
    STAGES,
    STAGE_SEQUENCE,
    STAGE_STATUSES,
)
from loopx_controller_flow import (
    advance_blockers,
    build_stage_result,
    business_write_blockers,
    confirm_stage,
    default_next_stage,
    is_waiting_confirmation,
    pending_confirmation_message,
    record_stage_result,
    stage_can_be_skipped,
    stage_result_path,
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
from loopx_controller_release import cmd_close, cmd_git_gate
from loopx_controller_repair import (
    cmd_claim_stage,
    cmd_close_repair,
    cmd_fail_review,
    cmd_review_feedback,
)
from loopx_controller_state import (
    build_tracking_snapshot,
    default_run_id,
    format_tracking,
    interview_state,
    mode_decision_state,
    mode_rank,
    render_worklist,
    resolve_mode,
    resolve_run_id,
    spec_state,
    tracking_state,
    update_worklist_state,
)
from loopx_controller_validation import strict_validation_errors, validate_run


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
    (directory / "artifacts" / "repair-tickets").mkdir()

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
        "max_auto_repair": 2,
        "worklist": f"docs/loopx/runs/{run_id}/worklist.yml",
        "events": f"docs/loopx/runs/{run_id}/events.jsonl",
        "repair_tickets": f"docs/loopx/runs/{run_id}/artifacts/repair-tickets",
        "loop_attempts": {},
        "stages": {},
        "interview": interview_state(run_id),
        "spec": spec_state(run_id),
        "mode_decision": mode_decision_state(mode, risk_tags, "auto" if args.mode == "auto" else "user"),
        "tracking": tracking_state(run_id),
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


def cmd_interview(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        state = load_state(project, run_id)
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    artifact = project_path(project, state.setdefault("interview", interview_state(run_id)).get("artifact"))
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
    interview_artifact = project_path(project, state.setdefault("interview", interview_state(run_id)).get("artifact"))
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
    spec_review_status = state.get("stages", {}).get("spec_review")
    if spec_review_status not in PASSING_STATUSES and not (
        spec_review_status == "SKIPPED" and stage_can_be_skipped("spec_review", state)
    ):
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
    return advance_to_stage(project, run_id, state, default_next_stage(current), stdout, fail_banner="FAIL next blocked")


def advance_to_stage(project, run_id, state, target, stdout, fail_banner="FAIL advance blocked"):
    blockers = advance_blockers(project, run_id, state, target)
    if blockers:
        print(fail_banner, file=stdout)
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


def cmd_advance(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        state = load_state(project, run_id)
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    return advance_to_stage(project, run_id, state, args.to, stdout)


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

    next_stage = subparsers.add_parser("next", help="Advance to the default next stage when checks pass.")
    next_stage.add_argument("run_id", nargs="?")
    next_stage.add_argument("--project", default=".")
    next_stage.set_defaults(func=cmd_next)

    validate = subparsers.add_parser("validate", help="Validate LoopX run state and worklist.")
    validate.add_argument("run_id", nargs="?")
    validate.add_argument("--strict", action="store_true")
    validate.add_argument("--project", default=".")
    validate.set_defaults(func=cmd_validate)

    gate = subparsers.add_parser("gate", help="Run the strict LoopX process check.")
    gate.add_argument("run_id", nargs="?")
    gate.add_argument("--project", default=".")
    gate.set_defaults(func=cmd_gate)

    close_run = subparsers.add_parser("close", help="Close a LoopX run after the final report and strict check pass.")
    close_run.add_argument("run_id", nargs="?")
    close_run.add_argument("--project", default=".")
    close_run.set_defaults(func=cmd_close)

    git_gate = subparsers.add_parser("git-gate", help="Record Git changed-file evidence for the final report check.")
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

    confirm = subparsers.add_parser("confirm-stage", help="Confirm a user-reviewed LoopX stage.")
    confirm.add_argument("--run-id")
    confirm.add_argument("--stage", required=True, choices=sorted(CONFIRMATION_GATE_STAGES))
    confirm.add_argument("--evidence", action="append", required=True)
    confirm.add_argument("--confirmed-by", default="user")
    confirm.add_argument("--project", default=".")
    confirm.set_defaults(func=cmd_confirm_stage)

    advance = subparsers.add_parser("advance", help="Advance only when previous LoopX checks pass.")
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

    compound = subparsers.add_parser("compound", help="Record reusable learning or skip decision for a LoopX run.")
    compound.add_argument("run_id", nargs="?")
    compound.add_argument("--decision", required=True, choices=["captured", "skipped"])
    compound.add_argument("--category", default="general")
    compound.add_argument("--title")
    compound.add_argument("--summary")
    compound.add_argument("--reason")
    compound.add_argument("--learning")
    compound.add_argument("--prevention")
    compound.add_argument("--risk-tags", nargs="*", default=None)
    compound.add_argument("--applies-to", action="append", default=[])
    compound.add_argument("--write-project-doc", action="store_true")
    compound.add_argument("--project", default=".")
    compound.set_defaults(func=cmd_compound)

    learning = subparsers.add_parser("validate-learning", help="Validate a LoopX compound learning markdown file.")
    learning.add_argument("path")
    learning.add_argument("--project", default=".")
    learning.set_defaults(func=cmd_validate_learning)
    return parser


def main(argv=None, stdout=None):
    stdout = stdout or sys.stdout
    args = build_parser().parse_args(argv)
    return args.func(args, stdout)


if __name__ == "__main__":
    sys.exit(main())
