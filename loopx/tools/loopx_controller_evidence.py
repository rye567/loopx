#!/usr/bin/env python3
"""LoopX v2 阶段记录准备与严格复检。

 本模块负责“任何持久化前”的完整校验（``prepare_v2_stage_record``）和
 严格检查时的复检（``validate_recorded_v2_stage``）；
 共享常量与文件解析在 ``_evidence_shared``，语义校验在
 ``_evidence_semantics``，工作项校验在 ``_evidence_workitems``。
 对外公共 API 由文件末尾的 re-export 保持不变。
"""

from __future__ import annotations

import json

from loopx_controller_io import load_schema, loopx_root, validate_schema
from loopx_controller_policy import (
    load_policy_snapshot,
    required_artifacts_for_stage,
    rules_for_stage,
)
from loopx_controller_evidence_shared import (
    ARTIFACT_SCHEMAS,
    ARTIFACT_VERSION,
    RULE_RESULT_STATUSES,
    resolve_project_file,
)
from loopx_controller_evidence_semantics import SEMANTIC_VALIDATORS
from loopx_controller_evidence_workitems import (
    WORK_ITEM_INPUT_FIELDS,
    runtime_work_items,
    validate_work_item_references,
)


def _read_json_artifact(path, label):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label}不是有效 JSON：{exc}") from exc
    except OSError as exc:
        raise ValueError(f"无法读取{label}：{exc}") from exc


def _load_artifact_schema(artifact_type):
    name = ARTIFACT_SCHEMAS[artifact_type]
    path = loopx_root() / "schemas" / f"{name}.schema.json"
    if not path.is_file():
        raise ValueError(f"缺少产物结构定义：{path.name}")
    return load_schema(name)


def _artifact_rule_results(artifact):
    value = artifact.get("rule_results") or []
    return value if isinstance(value, list) else []


def _embedded_evidence_values(value):
    """收集结构化产物内明确命名为证据引用的字段。"""

    collected = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"evidence", "verification_refs"}:
                if isinstance(child, list):
                    collected.extend(item for item in child if isinstance(item, str))
                continue
            if key == "confirmation_evidence" and isinstance(child, str):
                collected.append(child)
                continue
            collected.extend(_embedded_evidence_values(child))
    elif isinstance(value, list):
        for item in value:
            collected.extend(_embedded_evidence_values(item))
    return collected


def _canonical_rule_results(project, results):
    canonical = []
    for index, result in enumerate(results):
        if not isinstance(result, dict):
            raise ValueError(f"rule_results[{index}] 必须是对象")
        rule_id = result.get("rule_id") or result.get("id")
        status = result.get("status")
        if not isinstance(rule_id, str) or not rule_id:
            raise ValueError(f"rule_results[{index}].rule_id 必须是非空字符串")
        if status not in RULE_RESULT_STATUSES:
            raise ValueError(f"规则 {rule_id} 的状态不合法：{status}")
        reason = str(result.get("reason") or "")
        if status != "PASS" and len(reason.strip()) < 3:
            raise ValueError(f"规则 {rule_id} 未通过时必须提供具体理由")
        evidence = []
        for raw in result.get("evidence") or []:
            relative, _ = resolve_project_file(project, raw, f"规则 {rule_id} 的证据")
            evidence.append(relative)
        canonical.append({
            "rule_id": rule_id,
            "status": status,
            "evidence": evidence,
            "reason": reason,
        })
    ids = [item["rule_id"] for item in canonical]
    if len(ids) != len(set(ids)):
        raise ValueError("rule_results 包含重复规则 ID")
    return canonical


def _accepted_risk_is_valid(result, accepted_risk_ids):
    if len(result.get("reason") or "") < 3:
        return False
    return result["rule_id"] in accepted_risk_ids


def _validate_rule_results(stage, status, rules, results, accepted_risk_ids):
    if status != "PASS":
        return
    by_id = {item["rule_id"]: item for item in results}
    for rule in rules:
        if rule.get("level") != "required":
            continue
        rule_id = rule["id"]
        result = by_id.get(rule_id)
        if not result:
            raise ValueError(f"阶段 {stage} 缺少必需规则结果：{rule_id}")
        if result["status"] == "ACCEPTED_RISK":
            if not _accepted_risk_is_valid(result, accepted_risk_ids):
                raise ValueError(f"规则 {rule_id} 的风险接受缺少用户确认或具体理由")
        elif result["status"] != "PASS":
            unavailable = rule.get("unavailable")
            raise ValueError(f"规则 {rule_id} 未通过（{result['status']}）；不可用策略为 {unavailable}")
        if not result.get("evidence"):
            raise ValueError(f"规则 {rule_id} 通过时必须提供有效证据文件")


def prepare_v2_stage_record(project, state, stage, status, evidence, artifacts, affected_work_items, worklist):
    """在任何持久化前完成 v2 阶段输入检查并返回规范化数据。"""

    if status == "ACCEPTED_RISK":
        raise ValueError("v2 运行不接受阶段级 ACCEPTED_RISK；请在 quality_result 中逐规则记录并提供确认凭据")
    snapshot = load_policy_snapshot(project, state)
    artifact_inputs = artifacts or {}
    required_types = set(required_artifacts_for_stage(snapshot, stage))
    stage_rules = rules_for_stage(snapshot, stage)
    for rule in stage_rules:
        if rule.get("level") == "required":
            required_types.update(rule.get("evidence_types") or [])
    if status == "PASS":
        missing = sorted(required_types - set(artifact_inputs))
        if missing:
            raise ValueError(f"阶段 {stage} 通过前缺少必需产物：{', '.join(missing)}")

    artifact_entries = []
    loaded = {}
    all_rule_results = []
    all_evidence = []
    for artifact_type, raw_path in artifact_inputs.items():
        if artifact_type not in ARTIFACT_SCHEMAS:
            raise ValueError(f"未知产物类型：{artifact_type}")
        relative, path = resolve_project_file(project, raw_path, f"{artifact_type} 产物")
        artifact = _read_json_artifact(path, f"{artifact_type} 产物")
        schema_errors = validate_schema(artifact, _load_artifact_schema(artifact_type), artifact_type)
        if schema_errors:
            raise ValueError(f"{artifact_type} 产物结构校验失败：\n- " + "\n- ".join(schema_errors))
        if artifact.get("artifact_type") != artifact_type:
            raise ValueError(f"{artifact_type} 产物的 artifact_type 不一致")
        if str(artifact.get("artifact_version")) != ARTIFACT_VERSION:
            raise ValueError(f"{artifact_type} 产物版本必须是 {ARTIFACT_VERSION}")
        if artifact.get("run_id") != state.get("run_id"):
            raise ValueError(f"{artifact_type} 产物的 run_id 与当前运行不一致")
        if artifact.get("stage") != stage:
            raise ValueError(f"{artifact_type} 产物声明的阶段与当前阶段不一致：{artifact.get('stage')} != {stage}")
        document_relative, _ = resolve_project_file(project, artifact.get("document"), f"{artifact_type} 文档")
        semantic = SEMANTIC_VALIDATORS.get(artifact_type)
        if semantic:
            if artifact_type in {"solution", "security_result"}:
                semantic_errors = semantic(artifact, state.get("risk_tags") or [])
            elif artifact_type == "test_plan":
                required_rules = [
                    rule["id"] for rule in (snapshot.get("rules") or [])
                    if rule.get("level") == "required"
                ]
                semantic_errors = semantic(artifact, required_rules)
            elif artifact_type == "quality_result":
                semantic_errors = semantic(artifact, status)
            else:
                semantic_errors = semantic(artifact)
            if semantic_errors:
                raise ValueError(f"{artifact_type} 产物语义校验失败：\n- " + "\n- ".join(semantic_errors))
        loaded[artifact_type] = artifact
        artifact_entries.append({"type": artifact_type, "path": relative})
        all_evidence.extend((document_relative, relative))
        for raw in _embedded_evidence_values(artifact):
            embedded_relative, _ = resolve_project_file(project, raw, f"{artifact_type} 内嵌证据")
            all_evidence.append(embedded_relative)
        all_rule_results.extend(_artifact_rule_results(artifact))

    canonical_results = _canonical_rule_results(project, all_rule_results)
    snapshot_rule_ids = {rule["id"] for rule in (snapshot.get("rules") or [])}
    unknown_results = sorted({result["rule_id"] for result in canonical_results} - snapshot_rule_ids)
    if unknown_results:
        raise ValueError(f"产物包含当前运行未选择的规则结果：{', '.join(unknown_results)}")
    stage_rule_ids = {rule["id"] for rule in stage_rules}
    canonical_results = [result for result in canonical_results if result["rule_id"] in stage_rule_ids]
    accepted_risk_ids = {
        item.get("rule_id")
        for artifact in loaded.values()
        for item in (artifact.get("accepted_risks") or [])
        if isinstance(item, dict) and item.get("rule_id")
    }
    _validate_rule_results(stage, status, stage_rules, canonical_results, accepted_risk_ids)
    for result in canonical_results:
        all_evidence.extend(result["evidence"])
    for raw in evidence or []:
        relative, _ = resolve_project_file(project, raw, "补充证据")
        all_evidence.append(relative)
    all_evidence = list(dict.fromkeys(all_evidence))
    if status == "PASS" and not all_evidence:
        raise ValueError(f"阶段 {stage} 通过时必须提供至少一个有效证据文件")

    solution_items = None
    extra_ids = set()
    if stage == "solution_design" and status == "PASS":
        solution = loaded.get("solution")
        if not solution:
            raise ValueError("方案设计通过前必须提供 solution 产物")
        solution_items = runtime_work_items(solution.get("work_items"))
        extra_ids = {item["id"] for item in solution_items}
    validate_work_item_references(worklist, affected_work_items, extra_ids=extra_ids)
    return {
        "artifacts": artifact_entries,
        "rule_results": canonical_results,
        "evidence": all_evidence,
        "solution_items": solution_items,
    }


def validate_recorded_v2_stage(project, state, stage, result, worklist):
    """严格检查时复用记录阶段的完整校验。"""

    artifact_map = {}
    for entry in result.get("artifacts") or []:
        if not isinstance(entry, dict) or not entry.get("type") or not entry.get("path"):
            raise ValueError(f"阶段 {stage} 的 artifacts 结构无效")
        artifact_map[entry["type"]] = entry["path"]
    prepared = prepare_v2_stage_record(
        project,
        state,
        stage,
        result.get("agent_result") or result.get("status"),
        result.get("evidence") or [],
        artifact_map,
        result.get("affected_work_items") or [],
        worklist,
    )
    if prepared["artifacts"] != result.get("artifacts"):
        raise ValueError(f"阶段 {stage} 的产物路径不是规范化项目内路径")
    if prepared["rule_results"] != result.get("rule_results"):
        raise ValueError(f"阶段 {stage} 的规则结果与产物不一致")
    if prepared["evidence"] != result.get("evidence"):
        raise ValueError(f"阶段 {stage} 的证据集合与产物不一致")
    if prepared["solution_items"] is not None:
        expected = {
            item["id"]: {key: item[key] for key in WORK_ITEM_INPUT_FIELDS}
            for item in prepared["solution_items"]
        }
        actual = {
            item.get("id"): {key: item.get(key) for key in WORK_ITEM_INPUT_FIELDS}
            for item in (worklist.get("items") or []) if isinstance(item, dict) and item.get("id")
        }
        if actual != expected:
            raise ValueError("worklist 工作项与已记录方案不一致")
    for raw in result.get("confirmation_evidence") or []:
        resolve_project_file(project, raw, f"阶段 {stage} 的用户确认凭据")
    return prepared


# ---- 公共 API re-export：保持 loopx_controller_evidence.* 旧引用不变 ----
from loopx_controller_evidence_shared import (  # noqa: E402,F401
    parse_artifact_arguments,
)
from loopx_controller_evidence_semantics import (  # noqa: E402,F401
    validate_performance_semantics,
    validate_quality_semantics,
    validate_security_semantics,
    validate_solution_semantics,
    validate_test_plan_semantics,
)
from loopx_controller_evidence_workitems import (  # noqa: E402,F401
    known_work_item_ids,
    validate_work_items,
)
