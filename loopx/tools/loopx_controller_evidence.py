#!/usr/bin/env python3
"""LoopX v2 阶段产物、证据路径、规则结果和工作项校验。"""

from __future__ import annotations

import json
from pathlib import Path

from loopx_controller_io import load_schema, loopx_root, project_path, validate_schema
from loopx_controller_store import runtime_relative_path
from loopx_controller_policy import (
    CONTRACT_VERSION,
    load_policy_snapshot,
    required_artifacts_for_stage,
    rules_for_stage,
)


ARTIFACT_SCHEMAS = {
    "solution": "solution",
    "test_plan": "test-plan",
    "development_evidence": "development-evidence",
    "quality_result": "quality-result",
    "performance_result": "performance-result",
    "security_result": "security-result",
}
ARTIFACT_VERSION = "1"
RULE_RESULT_STATUSES = {
    "PASS",
    "CHANGES_REQUIRED",
    "ACCEPTED_RISK",
    "CI_REQUIRED",
    "SKIPPED",
    "BLOCKED",
}
WORK_ITEM_INPUT_FIELDS = {
    "id",
    "title",
    "owner_agent",
    "risk_tags",
    "read_scope",
    "write_scope",
    "dependencies",
    "validation",
}
WORK_ITEM_LIST_FIELDS = {"risk_tags", "read_scope", "write_scope", "dependencies", "validation"}


def resolve_project_file(project, raw_path, label="文件"):
    """解析项目内普通文件并返回基于真实路径的相对路径。"""

    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError(f"{label}路径不能为空")
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise ValueError(f"{label}必须使用项目内相对路径：{raw_path}")
    root = Path(project).resolve(strict=True)
    try:
        resolved = project_path(root, candidate).resolve(strict=True)
    except FileNotFoundError as exc:
        raise ValueError(f"{label}不存在：{raw_path}") from exc
    runtime_relative = runtime_relative_path(root, resolved)
    if runtime_relative is not None:
        relative = Path(runtime_relative)
    else:
        try:
            relative = resolved.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"{label}解析后超出项目根目录：{raw_path}") from exc
    if not resolved.is_file():
        raise ValueError(f"{label}必须是普通文件：{raw_path}")
    return relative.as_posix(), resolved


def parse_artifact_arguments(values):
    artifacts = {}
    for value in values or []:
        if not isinstance(value, str) or "=" not in value:
            raise ValueError("--artifact 必须使用“类型=项目内相对路径”格式")
        artifact_type, raw_path = (part.strip() for part in value.split("=", 1))
        if artifact_type not in ARTIFACT_SCHEMAS:
            raise ValueError(f"未知产物类型：{artifact_type}")
        if not raw_path:
            raise ValueError(f"产物 {artifact_type} 的路径不能为空")
        if artifact_type in artifacts:
            raise ValueError(f"产物类型重复：{artifact_type}")
        artifacts[artifact_type] = raw_path
    return artifacts


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


def _not_applicable(value):
    if not isinstance(value, dict):
        return False
    status = str(value.get("status") or value.get("applicability") or "").upper().replace("-", "_")
    return status in {"N/A", "NA", "NOT_APPLICABLE", "SKIPPED"} or value.get("applicable") is False


def _reason(value):
    if not isinstance(value, dict):
        return ""
    return str(value.get("reason") or value.get("not_applicable_reason") or value.get("rationale") or "").strip()


def _quality_attributes(artifact):
    value = artifact.get("quality_attributes") or artifact.get("qualities") or {}
    return value if isinstance(value, dict) else {}


def _find_attribute(attributes, *names):
    for name in names:
        if name in attributes:
            return attributes[name]
    return None


def _require_nonempty(value, path, errors):
    if value is None or value == "" or value == [] or value == {}:
        errors.append(f"{path} 不能为空")


def validate_solution_semantics(artifact, risk_tags=None):
    errors = []
    attributes = _quality_attributes(artifact)
    dimensions = {
        "simplicity": ("simplicity", "simple_design"),
        "module_boundaries": ("module_boundaries", "boundaries", "architecture_boundaries"),
        "security": ("security",),
        "performance": ("performance",),
        "extensibility": ("extensibility",),
        "compatibility": ("compatibility",),
        "reliability": ("reliability",),
        "observability": ("observability",),
    }
    for display, aliases in dimensions.items():
        value = _find_attribute(attributes, *aliases)
        if value is None:
            errors.append(f"solution.quality_attributes 缺少 {display}")
            continue
        if not isinstance(value, dict):
            errors.append(f"solution.quality_attributes.{display} 必须是对象")
            continue
        required_fields = {"status", "approach", "reason", "evidence"}
        unknown = set(value) - required_fields
        missing = required_fields - set(value)
        if unknown:
            errors.append(f"solution.quality_attributes.{display} 包含未知字段：{', '.join(sorted(unknown))}")
        if missing:
            errors.append(f"solution.quality_attributes.{display} 缺少字段：{', '.join(sorted(missing))}")
        if value.get("status") not in {"APPLICABLE", "NOT_APPLICABLE"}:
            errors.append(f"solution.quality_attributes.{display}.status 不合法")
        if not isinstance(value.get("approach"), str):
            errors.append(f"solution.quality_attributes.{display}.approach 必须是字符串")
        if not isinstance(value.get("reason"), str):
            errors.append(f"solution.quality_attributes.{display}.reason 必须是字符串")
        evidence = value.get("evidence")
        if not isinstance(evidence, list) or any(not isinstance(item, str) or not item for item in evidence):
            errors.append(f"solution.quality_attributes.{display}.evidence 必须是字符串数组")
        if value.get("status") == "APPLICABLE":
            _require_nonempty(value.get("approach"), f"solution.quality_attributes.{display}.approach", errors)
            _require_nonempty(evidence, f"solution.quality_attributes.{display}.evidence", errors)
        if _not_applicable(value) and len(_reason(value)) < 3:
            errors.append(f"solution.quality_attributes.{display} 标记不适用时必须提供具体理由")

    tags = set(risk_tags or [])
    rollback = artifact.get("rollback")
    if not isinstance(rollback, dict):
        errors.append("solution.rollback 必须是对象")
    else:
        has_strategy = bool(rollback.get("strategy") or rollback.get("steps") or rollback.get("validation"))
        if has_strategy:
            for field in ("strategy", "steps", "validation"):
                _require_nonempty(rollback.get(field), f"solution.rollback.{field}", errors)
        elif len(_reason(rollback)) < 3:
            errors.append("solution.rollback 不适用时必须提供具体理由")

    if "performance" in tags:
        targets = artifact.get("performance_targets") or []
        if not isinstance(targets, list) or not targets:
            errors.append("命中 performance 风险时必须提供 performance_targets")
        else:
            required = (
                "metric",
                "unit",
                "target",
                "target_source",
                "load",
                "environment",
                "baseline",
                "allowed_variation",
                "evidence",
            )
            for index, target in enumerate(targets):
                if not isinstance(target, dict):
                    errors.append(f"solution.performance_targets[{index}] 必须是对象")
                    continue
                for field in required:
                    _require_nonempty(target.get(field), f"solution.performance_targets[{index}].{field}", errors)
    return errors


def _mapping_ids(value, id_keys):
    if isinstance(value, dict):
        return {str(key) for key in value}
    result = set()
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                result.add(item)
            elif isinstance(item, dict):
                for key in id_keys:
                    if item.get(key):
                        result.add(str(item[key]))
                        break
    return result


def validate_test_plan_semantics(artifact, required_rule_ids=None):
    errors = []
    requirement_ids = {str(item) for item in artifact.get("requirement_ids") or []}
    acceptance = artifact.get("mappings") or artifact.get("acceptance_criteria") or artifact.get("acceptance_mappings")
    covered_acceptance = _mapping_ids(acceptance, ("requirement_id", "acceptance_id", "id"))
    if requirement_ids and not requirement_ids.issubset(covered_acceptance):
        missing = sorted(requirement_ids - covered_acceptance)
        errors.append(f"test_plan 未覆盖验收/需求标识：{', '.join(missing)}")

    rule_mapping = artifact.get("mappings") or artifact.get("rule_mappings") or artifact.get("rule_coverage")
    covered_rules = set()
    if isinstance(rule_mapping, list):
        for mapping in rule_mapping:
            if isinstance(mapping, dict):
                covered_rules.update(str(item) for item in mapping.get("rule_ids") or [])
    required_rule_ids = set(required_rule_ids or [])
    if required_rule_ids and not required_rule_ids.issubset(covered_rules):
        errors.append(f"test_plan 未覆盖必需规则：{', '.join(sorted(required_rule_ids - covered_rules))}")

    cases = artifact.get("cases") or artifact.get("test_cases") or []
    if not isinstance(cases, list) or not cases:
        errors.append("test_plan.test_cases 至少需要一个测试用例")
        return errors
    case_ids = [case.get("id") for case in cases if isinstance(case, dict) and case.get("id")]
    if len(case_ids) != len(set(case_ids)):
        errors.append("test_plan.test_cases 包含重复 ID")
    cases_by_id = {
        case["id"]: case for case in cases
        if isinstance(case, dict) and isinstance(case.get("id"), str) and case.get("id")
    }
    for index, mapping in enumerate(artifact.get("mappings") or []):
        if not isinstance(mapping, dict):
            continue
        requirement_id = mapping.get("requirement_id")
        for test_case_id in mapping.get("test_case_ids") or []:
            case = cases_by_id.get(test_case_id)
            if case is None:
                errors.append(f"test_plan.mappings[{index}] 引用了未知测试用例：{test_case_id}")
            elif requirement_id not in (case.get("covers") or []):
                errors.append(f"测试用例 {test_case_id} 未声明覆盖 {requirement_id}")
    lifecycle = {
        "data_setup": ("data_setup", "setup"),
        "execution": ("execution",),
        "assertions": ("assertions",),
        "cleanup": ("cleanup",),
    }
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"test_plan.test_cases[{index}] 必须是对象")
            continue
        for name, aliases in lifecycle.items():
            value = next((case.get(key) for key in aliases if key in case), None)
            if value in (None, "", [], {}):
                errors.append(f"test_plan.test_cases[{index}].{name} 不能为空")
        execution = case.get("execution") or {}
        if not execution.get("entrypoint") or not execution.get("steps"):
            errors.append(f"test_plan.test_cases[{index}].execution 必须包含入口和步骤")
        cleanup = case.get("cleanup") or {}
        if not cleanup.get("steps") or not cleanup.get("verification"):
            errors.append(f"test_plan.test_cases[{index}].cleanup 必须包含清理动作和清理验证")
    return errors


def validate_security_semantics(artifact, risk_tags=None):
    security_tags = {"auth", "permission", "tenant_scope", "config_or_secret", "dependency", "external_side_effect"}
    tags = security_tags.intersection(set(risk_tags or []))
    if not tags:
        return []
    controls = artifact.get("controls") or artifact.get("control_results") or []
    if not isinstance(controls, list) or not controls:
        return ["security_result.controls 缺少适用安全控制结果"]
    errors = []
    required_controls = {"input", "sensitive_data", "dependency"}
    mapping = {
        "auth": "identity",
        "permission": "permission",
        "tenant_scope": "tenant_scope",
        "config_or_secret": "sensitive_data",
        "dependency": "dependency",
        "external_side_effect": "external_side_effect",
    }
    required_controls.update(mapping[tag] for tag in tags)
    actual_controls = {
        item.get("control") for item in controls if isinstance(item, dict) and item.get("control")
    }
    missing = sorted(required_controls - actual_controls)
    if missing:
        errors.append(f"security_result 缺少适用控制：{', '.join(missing)}")
    for index, control in enumerate(controls):
        if not isinstance(control, dict):
            errors.append(f"security_result.controls[{index}] 必须是对象")
            continue
        status = str(control.get("status") or "")
        if status not in {"PASS", "CHANGES_REQUIRED", "CI_REQUIRED", "BLOCKED", "SKIPPED", "ACCEPTED_RISK"}:
            errors.append(f"security_result.controls[{index}].status 不合法")
        if status == "PASS" and not (control.get("evidence") or []):
            errors.append(f"security_result.controls[{index}] 通过时必须提供证据")
        remaining = str(control.get("remaining_risk") or _reason(control)).strip()
        if status in {"CHANGES_REQUIRED", "CI_REQUIRED", "BLOCKED", "SKIPPED", "ACCEPTED_RISK"} and len(remaining) < 3:
            errors.append(f"security_result.controls[{index}] 未完成时必须提供具体理由")
    return errors


def validate_performance_semantics(artifact):
    metrics = artifact.get("metrics") or []
    if not isinstance(metrics, list) or not metrics:
        return ["performance_result.metrics 至少需要一个指标"]
    errors = []
    required = (
        "metric",
        "unit",
        "target",
        "target_source",
        "load",
        "environment",
        "baseline",
        "actual",
        "allowed_variation",
        "status",
        "evidence",
    )
    for index, metric in enumerate(metrics):
        if not isinstance(metric, dict):
            errors.append(f"performance_result.metrics[{index}] 必须是对象")
            continue
        for key in required:
            _require_nonempty(metric.get(key), f"performance_result.metrics[{index}].{key}", errors)
    return errors


def validate_quality_semantics(artifact, stage_status=""):
    errors = []
    if stage_status == "PASS" and artifact.get("unresolved_items"):
        errors.append("quality_result 仍有未解决项，阶段不能通过")
    outside = (artifact.get("diff_scope") or {}).get("outside") or []
    if stage_status == "PASS" and outside:
        errors.append("quality_result 存在超出工作项写入范围的变更")
    accepted = artifact.get("accepted_risks") or []
    accepted_ids = [item.get("rule_id") for item in accepted if isinstance(item, dict)]
    if len(accepted_ids) != len(set(accepted_ids)):
        errors.append("quality_result.accepted_risks 包含重复规则 ID")
    accepted_results = {
        item.get("rule_id") for item in (artifact.get("rule_results") or [])
        if isinstance(item, dict) and item.get("status") == "ACCEPTED_RISK"
    }
    undeclared = sorted(accepted_results - set(accepted_ids))
    unused = sorted(set(accepted_ids) - accepted_results)
    if undeclared:
        errors.append(f"quality_result 缺少逐规则风险接受确认：{', '.join(undeclared)}")
    if unused:
        errors.append(f"quality_result.accepted_risks 没有对应的风险接受结果：{', '.join(unused)}")
    for index, item in enumerate(accepted):
        if isinstance(item, dict) and len(str(item.get("reason") or "").strip()) < 3:
            errors.append(f"quality_result.accepted_risks[{index}].reason 必须是具体理由")
    return errors


SEMANTIC_VALIDATORS = {
    "solution": validate_solution_semantics,
    "test_plan": validate_test_plan_semantics,
    "security_result": validate_security_semantics,
    "performance_result": validate_performance_semantics,
    "quality_result": validate_quality_semantics,
}


def validate_work_items(items):
    errors = []
    if not isinstance(items, list):
        return ["solution.work_items 必须是数组"]
    by_id = {}
    for index, item in enumerate(items):
        path = f"solution.work_items[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{path} 必须是对象")
            continue
        unknown = set(item) - WORK_ITEM_INPUT_FIELDS
        if unknown:
            errors.append(f"{path} 包含不允许的运行态或未知字段：{', '.join(sorted(unknown))}")
        for field in WORK_ITEM_INPUT_FIELDS:
            if field not in item:
                errors.append(f"{path}.{field} 缺失")
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id.strip():
            errors.append(f"{path}.id 必须是非空字符串")
        elif item_id in by_id:
            errors.append(f"{path}.id 重复：{item_id}")
        else:
            by_id[item_id] = item
        for field in WORK_ITEM_LIST_FIELDS:
            value = item.get(field)
            if not isinstance(value, list) or any(not isinstance(entry, str) or not entry for entry in value):
                errors.append(f"{path}.{field} 必须是字符串数组")
        for field in ("title", "owner_agent"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                errors.append(f"{path}.{field} 必须是非空字符串")
    known = set(by_id)
    for item_id, item in by_id.items():
        for dependency in item.get("dependencies") or []:
            if dependency not in known:
                errors.append(f"工作项 {item_id} 引用了未知依赖：{dependency}")
            if dependency == item_id:
                errors.append(f"工作项 {item_id} 不能依赖自身")

    visiting = set()
    visited = set()

    def visit(item_id):
        if item_id in visiting:
            errors.append(f"工作项依赖存在环：{item_id}")
            return
        if item_id in visited or item_id not in by_id:
            return
        visiting.add(item_id)
        for dependency in by_id[item_id].get("dependencies") or []:
            visit(dependency)
        visiting.remove(item_id)
        visited.add(item_id)

    for item_id in by_id:
        visit(item_id)
    return errors


def runtime_work_items(items):
    errors = validate_work_items(items)
    if errors:
        raise ValueError("方案工作项校验失败：\n- " + "\n- ".join(errors))
    return [
        {
            **item,
            "status": "pending",
            "evidence": [],
            "failed_by": "",
            "return_to": "",
            "required_changes": [],
        }
        for item in items
    ]


def known_work_item_ids(worklist):
    return {item.get("id") for item in (worklist.get("items") or []) if isinstance(item, dict) and item.get("id")}


def validate_work_item_references(worklist, item_ids, extra_ids=None):
    known = known_work_item_ids(worklist).union(extra_ids or set())
    unknown = sorted({item_id for item_id in (item_ids or []) if item_id not in known})
    if unknown:
        raise ValueError(f"工作项引用不存在：{', '.join(unknown)}")


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
