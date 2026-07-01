#!/usr/bin/env python3
"""Strict validation for LoopX run state.

这里集中检查“是否允许继续/收口”，命令层只能调用 validate_run，
不要在其他模块复制这些规则。
"""

from pathlib import Path

from loopx_controller_artifacts import (
    empty_spec_sections,
    interview_has_unanswered_placeholders,
    missing_spec_sections,
)
from loopx_controller_compound import validate_compound_capture
from loopx_controller_contracts import (
    CONFIRMATION_GATE_STAGES,
    FULL_REQUIRED_PASS_STAGES,
    PASSING_STATUSES,
    STAGES,
    STAGE_SEQUENCE,
    STAGE_STATUSES,
)
from loopx_controller_flow import stage_result_path
from loopx_controller_io import (
    get_run_dir,
    load_schema,
    read_json,
    validate_schema,
)
from loopx_controller_state import mode_rank
from loopx_controller_yaml import YamlSubsetError, parse_yaml_subset


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
        # final_report 是收口入口，必须同时有发布准备、Git 摘要和复利沉淀决策。
        if state.get("stages", {}).get("release_readiness") not in PASSING_STATUSES:
            errors.append("release_readiness must be PASS before final_report PASS")
        git_gate = state.get("git_gate", {})
        if git_gate.get("status") != "PASS":
            errors.append("state.git_gate.status must be PASS before final_report PASS")
        if not git_gate.get("diff_summary"):
            errors.append("state.git_gate.diff_summary is required for final_report PASS")
        errors.extend(validate_compound_capture(project, state.get("compound_capture", {}), load_schema("compound-learning"), validate_schema))

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

    worklist_rel = state.get("worklist") or f"docs/loopx/runs/{run_id}/worklist.yml"
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
