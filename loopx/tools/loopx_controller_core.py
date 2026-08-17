#!/usr/bin/env python3
"""LoopX controller command coordinator.

核心文件只保留 CLI 协调逻辑；状态构造、阶段流转、严格检查、返工和收口
分别放到专用模块，避免一个文件同时承载所有规则。
"""

import argparse
import copy
import io
import json
import re
import sys
from pathlib import Path, PurePosixPath

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
    record_prepared_v2_stage_result,
    record_stage_result,
    stage_can_be_skipped,
    stage_result_path,
)
from loopx_controller_io import (
    append_event,
    get_run_dir,
    json_text,
    load_state,
    project_path,
    read_json,
    save_state,
    write_json,
)
from loopx_controller_policy import (
    CONTRACT_VERSION,
    build_policy_snapshot,
    is_v2_run,
    load_policy_snapshot,
    policy_snapshot_relative_path,
    reselect_policy_snapshot,
)
from loopx_controller_evidence import parse_artifact_arguments
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
from loopx_controller_store import ExternalRunSession, StoreError, uses_project_backend
from loopx_controller_validation import strict_validation_errors, validate_run


def _translate_argument_error(message):
    replacements = (
        (r"the following arguments are required: ", "缺少必需参数："),
        (r"unrecognized arguments: ", "无法识别的参数："),
        (r"invalid choice: ", "选项值不合法："),
        (r"invalid int value: ", "整数值不合法："),
        (r"argument ([^:]+): ", r"参数 \1："),
        (r"\(choose from ", "（可选值："),
        (r"expected one argument", "需要一个值"),
        (r"expected at least one argument", "至少需要一个值"),
    )
    translated = message
    for pattern, replacement in replacements:
        translated = re.sub(pattern, replacement, translated)
    if "（可选值：" in translated and translated.endswith(")"):
        translated = translated[:-1] + "）"
    return translated


class ChineseArgumentParser(argparse.ArgumentParser):
    """保留兼容命令和参数名，仅把 argparse 的用户提示本地化。"""

    @staticmethod
    def _localize(text):
        return (
            text.replace("usage:", "用法：")
            .replace("positional arguments:", "位置参数：")
            .replace("options:", "选项：")
            .replace("show this help message and exit", "显示帮助并退出")
        )

    def format_help(self):
        return self._localize(super().format_help())

    def format_usage(self):
        return self._localize(super().format_usage())

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: 参数错误：{_translate_argument_error(message)}\n")


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


def cmd_status(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        state = read_json(get_run_dir(project, run_id) / "state.json")
    except (OSError, RuntimeError, ValueError) as exc:
        print(str(exc), file=stdout)
        return 1
    if args.tracking:
        print(format_tracking(state), end="", file=stdout)
        return 0
    print(f"运行 ID：{state.get('run_id')}", file=stdout)
    print(f"执行等级：{state.get('mode')}", file=stdout)
    print(f"运行状态：{state.get('status')}", file=stdout)
    print(f"当前阶段：{state.get('current_stage')}", file=stdout)
    print(f"下一步：{state.get('next_action', 'validate')}", file=stdout)
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
        print(f"FAIL 运行检查未通过：{run_id}", file=stdout)
        for error in errors:
            print(f"- {error}", file=stdout)
        return 1
    print(f"PASS 运行检查通过：{run_id}", file=stdout)
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
        print(f"FAIL 流程检查未通过：{run_id}", file=stdout)
        print("严格检查：FAIL", file=stdout)
        for error in errors:
            print(f"- {error}", file=stdout)
        return 1
    print(f"PASS 流程检查通过：{run_id}", file=stdout)
    print("严格检查：PASS", file=stdout)
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
        print("FAIL 执行等级选择被阻止", file=stdout)
        print("- 进入 mode_selection 前，spec_review 必须为 PASS", file=stdout)
        return 1
    if is_v2_run(state) and state.get("current_stage") != "mode_selection":
        print("FAIL 执行等级选择被阻止", file=stdout)
        print(f"- v2 只能在 mode_selection 阶段选择执行等级；当前阶段为 {state.get('current_stage')}", file=stdout)
        return 1
    selected = args.select
    new_state = copy.deepcopy(state)
    decision = new_state.setdefault("mode_decision", mode_decision_state(state.get("mode", selected), state.get("risk_tags", []), "auto"))
    recommended = decision.get("recommended") or state.get("mode")
    downgraded = mode_rank(recommended) > mode_rank(selected)
    if downgraded and not args.accepted_risk:
        print("FAIL 执行等级选择被阻止", file=stdout)
        print("- 选择低于建议的执行等级时，必须说明接受风险的理由", file=stdout)
        return 1
    new_state["mode"] = selected
    new_state["current_stage"] = "mode_selection"
    new_state["active_agent"] = new_state.get("stage_owners", DEFAULT_STAGE_OWNERS)["mode_selection"]
    new_state["next_action"] = "solution_design"
    decision["selected"] = selected
    decision["selection_status"] = "CONFIRMED"
    decision["selected_by"] = "user"
    decision.setdefault("accepted_risk", {})
    decision["accepted_risk"]["selected_lower_than_recommended"] = downgraded
    decision["accepted_risk"]["reason"] = args.accepted_risk or ""
    status = "ACCEPTED_RISK" if downgraded else "PASS"
    if is_v2_run(state):
        evidence_path = f"docs/loopx/runs/{run_id}/artifacts/mode-decision.json"
        try:
            snapshot = reselect_policy_snapshot(load_policy_snapshot(project, state), selected)
            new_state["policy_snapshot_sha256"] = snapshot["digest"]
            prepared = {
                "artifacts": [],
                "rule_results": [],
                "evidence": [evidence_path],
                "solution_items": None,
            }
            record_prepared_v2_stage_result(
                project,
                run_id,
                new_state,
                "mode_selection",
                status,
                prepared,
                next_action="solution_design",
                extra_files={
                    project_path(project, new_state["policy_snapshot"]): json_text(snapshot),
                    project_path(project, evidence_path): json_text(decision),
                },
            )
        except (OSError, RuntimeError, ValueError) as exc:
            print("FAIL 执行等级选择被阻止", file=stdout)
            print(f"- {exc}", file=stdout)
            return 1
    else:
        save_state(project, run_id, new_state)
        evidence = [args.accepted_risk] if args.accepted_risk else ["mode_decision"]
        record_stage_result(project, run_id, "mode_selection", status, evidence, next_action="solution_design")
        new_state = load_state(project, run_id)
        update_worklist_state(project, new_state, "mode_selection", status)
    print(f"已选择执行等级：{selected}", file=stdout)
    print(f"建议执行等级：{recommended}", file=stdout)
    print(f"阶段状态：{status}", file=stdout)
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
        print(f"FAIL 当前阶段不是已知阶段：{current}", file=stdout)
        return 1
    return advance_to_stage(project, run_id, state, default_next_stage(current), stdout, fail_banner="FAIL 下一阶段推进被阻止")


def advance_to_stage(project, run_id, state, target, stdout, fail_banner="FAIL 阶段推进被阻止"):
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
    print(f"PASS 已进入阶段：{target}", file=stdout)
    return 0


def cmd_record_stage(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        state = load_state(project, run_id)
        artifacts = parse_artifact_arguments(args.artifact) if is_v2_run(state) else {}
        if not is_v2_run(state) and args.artifact:
            raise ValueError("v1 历史运行不接受 --artifact；请继续使用原有 --evidence")
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
            artifacts=artifacts,
        )
        state = load_state(project, run_id)
        if not is_v2_run(state):
            update_worklist_state(project, state, args.stage, result["status"])
    except OSError as exc:
        print(f"阶段记录写入失败：{exc}", file=stdout)
        return 1
    except RuntimeError as exc:
        print(f"阶段记录恢复失败：{exc}", file=stdout)
        return 1
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    print(f"{result['status']} 已记录阶段：{result['stage']}", file=stdout)
    print(f"下一步：{result['next_action']}", file=stdout)
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
        print("PASS 允许写入 LoopX 运行文件", file=stdout)
        return 0
    blockers = business_write_blockers(state, project, run_id)
    if blockers:
        print("FAIL 业务文件写入仍被锁定", file=stdout)
        for blocker in blockers:
            print(f"- {blocker}", file=stdout)
        return 1
    print("PASS 允许写入业务文件", file=stdout)
    return 0


def cmd_confirm_stage(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        confirmation = confirm_stage(project, run_id, args.stage, args.evidence, args.confirmed_by)
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    print(f"PASS 已确认阶段：{args.stage}", file=stdout)
    print(f"确认人：{confirmation['confirmed_by']}", file=stdout)
    print(f"确认时间：{confirmation['confirmed_at']}", file=stdout)
    print(f"下一步：{CONFIRMATION_GATE_STAGES[args.stage]}", file=stdout)
    return 0


def cmd_health(args, stdout):
    # 健康执行器独立于 controller 核心，延迟导入允许 v1 工具继续单独使用。
    from loopx_health import execute_health

    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        report = execute_health(project, run_id, write_result=True)
    except ValueError as exc:
        print(f"健康检查无法执行：{exc}", file=stdout)
        return 1
    print(f"健康检查结果：{report.status}", file=stdout)
    print(f"报告：docs/loopx/runs/{run_id}/artifacts/health-result.json", file=stdout)
    for check in report.checks:
        print(f"- [{check.status}] {check.name}：{check.message}", file=stdout)
    return 0 if report.status in {"PASS", "PASS_WITH_WARNINGS", "LOCAL_INCOMPLETE_CI_REQUIRED", "CI_REQUIRED"} else 1


def import_artifact_files(project, run_id, stage, values, backups=None):
    """把显式输入文件复制到当前运行，避免结构化控制产物留在项目目录。"""

    imported = parse_artifact_arguments(values)
    result = []
    for artifact_type, raw_path in imported.items():
        source = Path(raw_path)
        source = source if source.is_absolute() else project / source
        if source.is_symlink():
            raise ValueError(f"导入产物不能是符号链接：{raw_path}")
        try:
            source = source.resolve(strict=True)
        except FileNotFoundError as exc:
            raise ValueError(f"导入产物不存在：{raw_path}") from exc
        if not source.is_file():
            raise ValueError(f"导入产物必须是普通文件：{raw_path}")
        relative = f"docs/loopx/runs/{run_id}/artifacts/imported/{stage}-{artifact_type}.json"
        target = project_path(project, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        if backups is not None:
            backups.append((target, target.read_bytes() if target.is_file() else None))
        target.write_bytes(source.read_bytes())
        result.append(f"{artifact_type}={relative}")
    return result


def restore_imported_artifacts(backups):
    for target, previous in reversed(backups):
        if previous is None:
            target.unlink(missing_ok=True)
            try:
                target.parent.rmdir()
            except OSError:
                pass
        else:
            target.write_bytes(previous)


def cmd_import_artifact(args, stdout):
    """把 agent 或用户准备的文件收纳到运行产物区，不开放状态文件写入。"""

    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        load_state(project, run_id)
        source_input = Path(args.source)
        source_candidate = source_input if source_input.is_absolute() else project / source_input
        if source_candidate.is_symlink():
            raise ValueError("导入源文件不能是符号链接")
        source = source_candidate.resolve(strict=True)
        if not source.is_file():
            raise ValueError("导入源必须是普通文件")
        raw_target = args.target.replace("\\", "/")
        relative = PurePosixPath(raw_target)
        if relative.is_absolute() or not relative.parts or relative.parts[0] != "artifacts":
            raise ValueError("导入目标必须位于 artifacts/ 下")
        if any(part in {"", ".", ".."} for part in relative.parts):
            raise ValueError("导入目标不能包含路径跳转")
        directory = get_run_dir(project, run_id).resolve(strict=True)
        target = directory.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.parent.resolve(strict=True).relative_to(directory)
        if target.is_symlink():
            raise ValueError("导入目标不能是符号链接")
        target.write_bytes(source.read_bytes())
        append_event(directory, {
            "type": "artifact_imported",
            "artifact": f"docs/loopx/runs/{run_id}/{relative.as_posix()}",
        })
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"FAIL 运行产物导入失败：{exc}", file=stdout)
        return 1
    print(f"PASS 已导入运行产物：docs/loopx/runs/{run_id}/{relative.as_posix()}", file=stdout)
    return 0


def build_parser():
    parser = ChineseArgumentParser(description="LoopX 状态控制器。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="创建本地 LoopX 运行。")
    init.add_argument("requirement")
    init.add_argument("--run-id")
    init.add_argument("--mode", choices=["auto", "LIGHT", "STANDARD", "FULL"], default="auto")
    init.add_argument("--risk-tags", nargs="*", default=[])
    init.add_argument("--project", default=".")
    init.set_defaults(func=cmd_init)

    status = subparsers.add_parser("status", help="查看 LoopX 运行状态。")
    status.add_argument("run_id", nargs="?")
    status.add_argument("--tracking", action="store_true")
    status.add_argument("--project", default=".")
    status.set_defaults(func=cmd_status)

    interview = subparsers.add_parser("interview", help="生成需求采访产物。")
    interview.add_argument("run_id", nargs="?")
    interview.add_argument("--project", default=".")
    interview.set_defaults(func=cmd_interview)

    spec = subparsers.add_parser("spec", help="在需求采访确认后生成需求规格。")
    spec.add_argument("run_id", nargs="?")
    spec.add_argument("--project", default=".")
    spec.set_defaults(func=cmd_spec)

    mode = subparsers.add_parser("mode", help="记录选定的 LoopX 执行等级。")
    mode.add_argument("run_id", nargs="?")
    mode.add_argument("--select", required=True, choices=["LIGHT", "STANDARD", "FULL"])
    mode.add_argument("--accepted-risk")
    mode.add_argument("--project", default=".")
    mode.set_defaults(func=cmd_mode)

    next_stage = subparsers.add_parser("next", help="检查通过后进入默认下一阶段。")
    next_stage.add_argument("run_id", nargs="?")
    next_stage.add_argument("--project", default=".")
    next_stage.set_defaults(func=cmd_next)

    validate = subparsers.add_parser("validate", help="检查 LoopX 运行状态和工作清单。")
    validate.add_argument("run_id", nargs="?")
    validate.add_argument("--strict", action="store_true")
    validate.add_argument("--project", default=".")
    validate.set_defaults(func=cmd_validate)

    gate = subparsers.add_parser("gate", help="执行严格的 LoopX 流程检查。")
    gate.add_argument("run_id", nargs="?")
    gate.add_argument("--project", default=".")
    gate.set_defaults(func=cmd_gate)

    health = subparsers.add_parser("health", help="执行配置驱动的健康检查并写入运行报告。")
    health.add_argument("run_id", nargs="?")
    health.add_argument("--project", default=".")
    health.set_defaults(func=cmd_health)

    import_artifact = subparsers.add_parser("import-artifact", help="把外部文件收纳到当前运行的 artifacts 目录。")
    import_artifact.add_argument("run_id", nargs="?")
    import_artifact.add_argument("--source", required=True)
    import_artifact.add_argument("--target", required=True)
    import_artifact.add_argument("--project", default=".")
    import_artifact.set_defaults(func=cmd_import_artifact)

    close_run = subparsers.add_parser("close", help="最终报告和严格检查通过后收口运行。")
    close_run.add_argument("run_id", nargs="?")
    close_run.add_argument("--project", default=".")
    close_run.set_defaults(func=cmd_close)

    git_gate = subparsers.add_parser("git-gate", help="记录供最终报告检查使用的 Git 变更证据。")
    git_gate.add_argument("run_id", nargs="?")
    git_gate.add_argument("--project", default=".")
    git_gate.set_defaults(func=cmd_git_gate)

    record = subparsers.add_parser("record-stage", help="记录机器可读的 LoopX 阶段结果。")
    record.add_argument("--run-id")
    record.add_argument("--stage", required=True, choices=STAGE_SEQUENCE)
    record.add_argument("--status", required=True, choices=sorted(STAGE_STATUSES))
    record.add_argument("--evidence", action="append", default=[])
    record.add_argument("--artifact", action="append", default=[], help="结构化产物，格式为“类型=项目内相对路径”，可重复。")
    record.add_argument("--artifact-file", action="append", default=[], help="导入结构化产物文件并收纳到运行状态，格式为“类型=文件路径”，可重复。")
    record.add_argument("--return-to", choices=STAGE_SEQUENCE)
    record.add_argument("--next-action")
    record.add_argument("--item", action="append")
    record.add_argument("--blocked-reason")
    record.add_argument("--project", default=".")
    record.set_defaults(func=cmd_record_stage)

    confirm = subparsers.add_parser("confirm-stage", help="记录用户对 LoopX 阶段的确认。")
    confirm.add_argument("--run-id")
    confirm.add_argument("--stage", required=True, choices=sorted(CONFIRMATION_GATE_STAGES))
    confirm.add_argument("--evidence", action="append", required=True)
    confirm.add_argument("--confirmed-by", default="user")
    confirm.add_argument("--project", default=".")
    confirm.set_defaults(func=cmd_confirm_stage)

    advance = subparsers.add_parser("advance", help="仅在前置检查通过后进入指定阶段。")
    advance.add_argument("--run-id")
    advance.add_argument("--to", required=True, choices=STAGE_SEQUENCE)
    advance.add_argument("--project", default=".")
    advance.set_defaults(func=cmd_advance)

    can_write = subparsers.add_parser("can-write", help="检查当前是否允许写入。")
    can_write.add_argument("--run-id")
    can_write.add_argument("--kind", choices=["business", "loopx"], default="business")
    can_write.add_argument("--project", default=".")
    can_write.set_defaults(func=cmd_can_write)

    fail_review_parser = subparsers.add_parser("fail-review", help="根据审核失败创建返工单并返回责任阶段。")
    fail_review_parser.add_argument("--run-id")
    fail_review_parser.add_argument("--from", dest="from_stage", required=True, choices=STAGE_SEQUENCE)
    fail_review_parser.add_argument("--return-to", required=True, choices=STAGE_SEQUENCE)
    fail_review_parser.add_argument("--item", required=True)
    fail_review_parser.add_argument("--reason", action="append", required=True)
    fail_review_parser.add_argument("--project", default=".")
    fail_review_parser.set_defaults(func=cmd_fail_review)

    claim = subparsers.add_parser("claim-stage", help="领取当前阶段并显示责任角色的待处理返工单。")
    claim.add_argument("stage", choices=STAGE_SEQUENCE)
    claim.add_argument("--run-id")
    claim.add_argument("--project", default=".")
    claim.set_defaults(func=cmd_claim_stage)

    close = subparsers.add_parser("close-repair", help="更新原产物版本后关闭返工单。")
    close.add_argument("--run-id")
    close.add_argument("--item", required=True)
    close.add_argument("--artifact", required=True)
    close.add_argument("--revision", required=True, type=int)
    close.add_argument("--change", action="append", required=True)
    close.add_argument("--project", default=".")
    close.set_defaults(func=cmd_close_repair)

    feedback = subparsers.add_parser("review-feedback", help="记录用户审核反馈并返回先前阶段。")
    feedback.add_argument("--run-id")
    feedback.add_argument("--item", required=True)
    feedback.add_argument("--return-to", required=True, choices=STAGE_SEQUENCE)
    feedback.add_argument("--reason", required=True)
    feedback.add_argument("--project", default=".")
    feedback.set_defaults(func=cmd_review_feedback)

    compound = subparsers.add_parser("compound", help="记录可复用经验或跳过沉淀的决定。")
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

    learning = subparsers.add_parser("validate-learning", help="检查 LoopX 复用经验 Markdown 文件。")
    learning.add_argument("path")
    learning.add_argument("--project", default=".")
    learning.set_defaults(func=cmd_validate_learning)
    return parser


def main(argv=None, stdout=None):
    stdout = stdout or sys.stdout
    args = build_parser().parse_args(argv)
    if args.command == "validate-learning":
        learning_parts = PurePosixPath(str(args.path).replace("\\", "/")).parts
        if len(learning_parts) < 4 or learning_parts[:3] != ("docs", "loopx", "runs"):
            return args.func(args, stdout)
        args.run_id = learning_parts[3]
    project = Path(args.project).resolve()
    if args.command == "init":
        run_id = args.run_id or default_run_id(args.requirement)
        args.run_id = run_id
    else:
        try:
            run_id = resolve_run_id(project, getattr(args, "run_id", None))
        except ValueError as exc:
            print(str(exc), file=stdout)
            return 1
        args.run_id = run_id
    try:
        project_backend = uses_project_backend(project, run_id)
    except (StoreError, OSError) as exc:
        print(f"状态存储错误：{exc}", file=stdout)
        return 1
    if project_backend:
        imported_backups = []
        if args.command == "record-stage" and args.artifact_file:
            try:
                args.artifact.extend(import_artifact_files(
                    project, run_id, args.stage, args.artifact_file, imported_backups,
                ))
            except (OSError, ValueError) as exc:
                restore_imported_artifacts(imported_backups)
                print(f"无法导入结构化产物：{exc}", file=stdout)
                return 1
        result = args.func(args, stdout)
        if args.command == "record-stage" and result != 0:
            restore_imported_artifacts(imported_backups)
        return result

    buffered = io.StringIO()
    try:
        with ExternalRunSession(project, run_id, create=args.command == "init") as session:
            imported_backups = []
            if args.command == "record-stage" and args.artifact_file:
                try:
                    args.artifact.extend(import_artifact_files(
                        project, run_id, args.stage, args.artifact_file, imported_backups,
                    ))
                except (OSError, ValueError) as exc:
                    raise StoreError(f"无法导入结构化产物：{exc}") from exc
            result = args.func(args, buffered)
            if args.command == "record-stage" and result != 0:
                restore_imported_artifacts(imported_backups)
            if args.command != "import-artifact" or result == 0:
                session.commit()
    except (StoreError, OSError) as exc:
        print(f"状态存储错误：{exc}", file=stdout)
        return 1
    print(buffered.getvalue(), end="", file=stdout)
    return result


if __name__ == "__main__":
    sys.exit(main())
