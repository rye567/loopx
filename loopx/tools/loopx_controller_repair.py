#!/usr/bin/env python3
"""Review feedback and repair commands for LoopX.

返工流程负责把失败反馈带回原 owner 阶段；它不直接跳过阶段检查，
修复完成后仍要通过 flow/validation 的统一规则。
"""

from pathlib import Path

from loopx_controller_contracts import DEFAULT_STAGE_OWNERS, STAGE_SEQUENCE
from loopx_controller_flow import record_stage_result, stage_index
from loopx_controller_io import load_state, load_worklist, save_state
from loopx_controller_state import resolve_run_id, update_worklist_state
from loopx_controller_tickets import (
    open_repair_tickets_for_stage,
    read_repair_ticket,
    write_repair_ticket,
)
from loopx_controller_yaml import YamlSubsetError, dump_worklist


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
    # 按阶段递增返工次数；超过 max_auto_repair 后第 N 次仍失败则 BLOCKED，等待用户处理。
    # ticket.status 只表达票据生命周期（OPEN/CLOSED），阶段结果记录在 stage 状态里。
    attempts = state.setdefault("loop_attempts", {})
    attempt = int(attempts.get(from_stage, 0)) + 1
    attempts[from_stage] = attempt
    limit = int(state.get("max_auto_repair", 2))
    stage_status = "CHANGES_REQUIRED" if attempt <= limit else "BLOCKED"
    ticket = {
        "type": "review_failed",
        "item": item_id,
        "from_stage": from_stage,
        "return_to": return_to,
        "assigned_to": owner,
        "attempt": attempt,
        "status": "OPEN",
        "stage_status": stage_status,
        "required_changes": reasons,
        "artifact": "",
        "revision": 0,
        "changes_from_review": [],
    }
    state["current_stage"] = return_to
    state["next_action"] = f"repair_{return_to}"
    state["active_agent"] = owner
    state.setdefault("stages", {})[from_stage] = stage_status
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
        stage_status,
        reasons,
        return_to=return_to,
        next_action=f"repair_{return_to}",
        affected_work_items=[item_id],
        blocked_reason=f"auto repair exceeded max_auto_repair={limit}" if stage_status == "BLOCKED" else "",
    )
    # record_stage_result 已重新落库 state，这里再同步 worklist 的 stage 状态，避免 strict 校验漂移。
    state = load_state(project, run_id)
    update_worklist_state(project, state, from_stage, stage_status)
    return ticket


def cmd_fail_review(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        ticket = fail_review(project, run_id, args.from_stage, args.return_to, args.item, args.reason)
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    print(f"{ticket['stage_status']} {args.from_stage}", file=stdout)
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
        # 返工项关闭后重置该阶段的返工计数，允许重新计数自动返工上限。
        state.setdefault("loop_attempts", {}).pop(from_stage, None)
    save_state(project, run_id, state)
    print(f"PASS repair closed {args.item}", file=stdout)
    print(f"artifact: {args.artifact}", file=stdout)
    print(f"revision: {args.revision}", file=stdout)
    return 0
