#!/usr/bin/env python3
"""LoopX 需求输入阶段命令（init / interview / spec）。

 这组命令只负责需求侧产物的生成与初始化，依赖底层 io/state/flow/artifacts
 模块，不反向依赖 controller 核心，避免形成环。
"""

import json
from pathlib import Path

from loopx_controller_artifacts import (
    interview_has_unanswered_placeholders,
    interview_questions,
    render_interview_artifact,
    render_spec_artifact,
)
from loopx_controller_contracts import (
    DEFAULT_STAGE_OWNERS,
    PASSING_STATUSES,
)
from loopx_controller_flow import (
    build_stage_result,
    is_waiting_confirmation,
    pending_confirmation_message,
    stage_result_path,
)
from loopx_controller_io import (
    append_event,
    get_run_dir,
    load_state,
    project_path,
    save_state,
    write_json,
)
from loopx_controller_policy import (
    CONTRACT_VERSION,
    build_policy_snapshot,
    is_v2_run,
    policy_snapshot_relative_path,
)
from loopx_controller_state import (
    default_run_id,
    interview_state,
    mode_decision_state,
    render_worklist,
    resolve_mode,
    resolve_run_id,
    spec_state,
    tracking_state,
    update_worklist_state,
)


def auto_pass_environment_check(project, run_id):
    directory = get_run_dir(project, run_id)
    state = load_state(project, run_id)
    next_action = "requirement_intake"
    evidence = [
        "LoopX controller initialized run state",
        "Project root resolved",
        "Python controller runtime available",
    ]
    if is_v2_run(state):
        relative = f"docs/loopx/runs/{run_id}/artifacts/environment-check.txt"
        artifact = project_path(project, relative)
        artifact.write_text("LoopX 控制器、项目根目录和 Python 运行时已就绪。\n", encoding="utf-8")
        evidence = [relative]
    result = build_stage_result(
        state,
        "environment_check",
        "PASS",
        "PASS",
        "",
        next_action,
        evidence,
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
    mode = resolve_mode(args.mode, risk_tags, project)
    directory = get_run_dir(project, run_id)
    if directory.exists():
        print(f"运行已存在：{run_id}", file=stdout)
        return 1
    try:
        policy_snapshot = build_policy_snapshot(project, mode, risk_tags)
    except ValueError as exc:
        print(f"无法初始化运行：{exc}", file=stdout)
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
        "contract_version": CONTRACT_VERSION,
        "catalog_version": policy_snapshot["catalog_version"],
        "policy_snapshot": policy_snapshot_relative_path(run_id),
        "policy_snapshot_sha256": policy_snapshot["digest"],
    }
    write_json(directory / "artifacts" / "policy-snapshot.json", policy_snapshot)
    write_json(directory / "state.json", state)
    (directory / "worklist.yml").write_text(render_worklist(run_id, args.requirement, mode), encoding="utf-8")
    event = {"type": "run_created", "run_id": run_id, "current_stage": "environment_check"}
    (directory / "events.jsonl").write_text(json.dumps(event, ensure_ascii=False) + "\n", encoding="utf-8")
    auto_pass_environment_check(project, run_id)
    print(f"PASS 已创建运行：{run_id}", file=stdout)
    print(f"执行等级：{mode}", file=stdout)
    print(f"建议执行等级：{mode}", file=stdout)
    print("环境检查（environment_check）：PASS", file=stdout)
    if args.mode == "auto":
        print("执行等级选择：需要用户确认（NEED_HUMAN）", file=stdout)
    print(f"状态文件：{state['worklist'].rsplit('/', 1)[0]}/state.json", file=stdout)
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
    print(f"已生成需求采访：{state['interview']['artifact']}", file=stdout)
    print("请回答以下需求采访问题：", file=stdout)
    for index, item in enumerate(questions, start=1):
        print(f"问题 {index}：{item['question']}", file=stdout)
        print(f"  为什么需要：{item['reason']}", file=stdout)
    print("回答后请更新 interview.md，再记录 requirement_interview 为 PASS；控制器随后等待用户确认（NEED_HUMAN）。", file=stdout)
    print("当前阶段：requirement_interview", file=stdout)
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
        print("FAIL 需求规格生成被阻止", file=stdout)
        print(f"- {pending_confirmation_message('requirement_interview')}", file=stdout)
        return 1
    if interview_status not in PASSING_STATUSES:
        print("FAIL 需求规格生成被阻止", file=stdout)
        print("- 进入 spec_draft 前，requirement_interview 必须为 PASS", file=stdout)
        return 1
    interview_artifact = project_path(project, state.setdefault("interview", interview_state(run_id)).get("artifact"))
    if not interview_artifact.exists():
        print("FAIL 需求规格生成被阻止", file=stdout)
        print(f"- 缺少需求采访产物：{state['interview']['artifact']}", file=stdout)
        return 1
    interview_text = interview_artifact.read_text(encoding="utf-8")
    if state.get("interview", {}).get("unanswered_questions", 0) != 0 or interview_has_unanswered_placeholders(interview_text):
        print("FAIL 需求规格生成被阻止", file=stdout)
        print("- 进入 spec_draft 前必须回答全部需求采访问题", file=stdout)
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
    print(f"已生成需求规格：{spec['artifact']}", file=stdout)
    print("当前阶段：spec_draft", file=stdout)
    return 0
