#!/usr/bin/env python3
"""LoopX 配置驱动的健康检查执行器。

核心检查只依赖 Python 标准库。项目命令必须以参数数组声明，执行时不经过
shell，也不会尝试安装缺失工具。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from loopx_controller_contracts import (  # noqa: E402
    MODE_SKIPPABLE_STAGES,
    PASSING_STATUSES,
    STAGE_RESULT_FILES,
    STAGE_SEQUENCE,
)
from loopx_controller_policy import load_policy_snapshot  # noqa: E402
from loopx_controller_io import get_run_dir, project_path  # noqa: E402
from loopx_controller_store import active_run_dir, runtime_relative_path  # noqa: E402
from loopx_controller_yaml import YamlSubsetError, parse_yaml_subset  # noqa: E402


PASS = "PASS"
CI_REQUIRED = "CI_REQUIRED"
SKIPPED = "SKIPPED"
BLOCKED = "BLOCKED"
PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
LOCAL_INCOMPLETE_CI_REQUIRED = "LOCAL_INCOMPLETE_CI_REQUIRED"

DEFAULT_TIMEOUT_SECONDS = 300.0
MAX_TIMEOUT_SECONDS = 1_800.0
DEFAULT_OUTPUT_LIMIT = 16_384
MAX_OUTPUT_LIMIT = 65_536
V2_ONLY_CHECKS = {
    "required_rule_results",
    "accepted_risks_confirmed",
    "policy_snapshot_integrity",
}
RESOLVED_WORK_ITEM_STATUSES = {
    "PASS",
    "DONE",
    "COMPLETED",
    "RESOLVED",
    "ACCEPTED_RISK",
    "SKIPPED",
}


@dataclass
class HealthCheckResult:
    """一项检查的稳定输出格式。"""

    name: str
    status: str
    message: str
    evidence: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "evidence": self.evidence,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class HealthReport:
    """一次健康检查的汇总结果。"""

    run_id: str
    status: str
    checks: list[HealthCheckResult]
    ci_gap_declared: bool

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "checks": [item.to_dict() for item in self.checks],
            "ci_gap_declared": self.ci_gap_declared,
        }


@dataclass
class HealthContext:
    project: Path
    run_id: str
    run_dir: Path
    state: dict
    config: dict
    command_runner: Callable | None = None

    @property
    def is_v2(self) -> bool:
        return str(self.state.get("contract_version") or "1") == "2"

    def stage_results(self) -> list[tuple[Path, dict]]:
        results = []
        for path in sorted((self.run_dir / "stage-results").glob("*.json")):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(value, dict):
                results.append((path, value))
        return results


def _result(name: str, status: str, message: str, evidence=None, details=None) -> HealthCheckResult:
    return HealthCheckResult(name, status, message, list(evidence or []), dict(details or {}))


def load_health_config(path: Path) -> dict:
    """读取并检查 health.yml 的最小契约。"""

    try:
        value = parse_yaml_subset(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"健康检查配置不存在：{path}") from exc
    except (OSError, YamlSubsetError) as exc:
        raise ValueError(f"健康检查配置无法读取：{exc}") from exc
    health = value.get("health") if isinstance(value, dict) else None
    if not isinstance(health, dict):
        raise ValueError("健康检查配置缺少 health 对象")
    if health.get("allow_auto_install") is not False:
        raise ValueError("健康检查必须明确禁止自动安装工具")
    if not isinstance(health.get("core_checks"), list) or not health["core_checks"]:
        raise ValueError("health.core_checks 必须是非空数组")
    policies = health.get("missing_tool_policy") or {}
    expected_policies = {"optional": SKIPPED, "ci_backed": CI_REQUIRED, "required": BLOCKED}
    if any(policies.get(key, value) != value for key, value in expected_policies.items()):
        raise ValueError("缺失工具处理策略只能是 optional=SKIPPED、ci_backed=CI_REQUIRED、required=BLOCKED")
    allowed_overall = {PASS, PASS_WITH_WARNINGS, LOCAL_INCOMPLETE_CI_REQUIRED, BLOCKED}
    if any(value not in allowed_overall for value in (health.get("result_status") or {}).values()):
        raise ValueError("健康检查汇总状态配置包含未知值")
    return health


def aggregate_status(results: Iterable[HealthCheckResult | str], status_map: dict | None = None) -> str:
    """按最严重结果汇总，未识别状态按失败处理。"""

    statuses = [item.status if isinstance(item, HealthCheckResult) else str(item) for item in results]
    if any(status not in {PASS, CI_REQUIRED, SKIPPED, BLOCKED, PASS_WITH_WARNINGS,
                         LOCAL_INCOMPLETE_CI_REQUIRED} for status in statuses):
        standard = BLOCKED
    elif BLOCKED in statuses:
        standard = BLOCKED
    elif CI_REQUIRED in statuses or LOCAL_INCOMPLETE_CI_REQUIRED in statuses:
        standard = LOCAL_INCOMPLETE_CI_REQUIRED
    elif SKIPPED in statuses or PASS_WITH_WARNINGS in statuses:
        standard = PASS_WITH_WARNINGS
    else:
        standard = PASS
    mapping = status_map or {}
    key = {
        PASS: "pass",
        PASS_WITH_WARNINGS: "pass_with_warnings",
        LOCAL_INCOMPLETE_CI_REQUIRED: "local_incomplete",
        BLOCKED: "blocked",
    }[standard]
    return str(mapping.get(key) or standard)


def _safe_file(project: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        raise ValueError("必须使用项目内相对路径")
    root = project.resolve(strict=True)
    try:
        resolved = project_path(root, path).resolve(strict=True)
        if runtime_relative_path(root, resolved) is None:
            resolved.relative_to(root)
    except FileNotFoundError as exc:
        raise ValueError("文件不存在") from exc
    except ValueError as exc:
        raise ValueError("路径解析后超出项目根目录") from exc
    if not resolved.is_file():
        raise ValueError("路径不是普通文件")
    return resolved


def _run_directory(project: Path, run_id: str, strict: bool = True) -> Path:
    if not isinstance(run_id, str) or not run_id or Path(run_id).name != run_id:
        raise ValueError("运行 ID 不能包含路径片段")
    runs_root = project.resolve() / "docs" / "loopx" / "runs"
    try:
        directory = get_run_dir(project, run_id).resolve(strict=strict)
        if active_run_dir(project, run_id) is None:
            directory.relative_to(runs_root.resolve())
    except FileNotFoundError as exc:
        raise ValueError(f"运行不存在：{run_id}") from exc
    except ValueError as exc:
        raise ValueError("运行目录解析后超出项目范围") from exc
    if strict and not directory.is_dir():
        raise ValueError(f"运行目录不存在：{run_id}")
    return directory


def _worklist(ctx: HealthContext) -> dict:
    raw = ctx.state.get("worklist") or f"docs/loopx/runs/{ctx.run_id}/worklist.yml"
    path = _safe_file(ctx.project, raw)
    value = parse_yaml_subset(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("worklist 必须是对象")
    return value


def _check_stage_artifacts(ctx: HealthContext) -> HealthCheckResult:
    before_health = STAGE_SEQUENCE[:STAGE_SEQUENCE.index("health_gate")]
    skippable = MODE_SKIPPABLE_STAGES.get(ctx.state.get("mode", ""), frozenset())
    missing = []
    evidence = []
    statuses = ctx.state.get("stages") or {}
    for stage in before_health:
        status = statuses.get(stage)
        if status == SKIPPED and stage in skippable:
            continue
        if status not in PASSING_STATUSES:
            missing.append(f"{stage} 状态为 {status or 'PENDING'}")
            continue
        filename = STAGE_RESULT_FILES[stage]
        path = ctx.run_dir / "stage-results" / filename
        if not path.is_file():
            missing.append(f"{stage} 缺少 {filename}")
        else:
            try:
                result = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                missing.append(f"{filename} 无法读取：{exc}")
                continue
            if not isinstance(result, dict) or result.get("stage") != stage or result.get("status") not in PASSING_STATUSES:
                missing.append(f"{filename} 的阶段或状态与 state.json 不一致")
                continue
            evidence.append(str(path))
    if missing:
        return _result("stage_artifacts_complete", BLOCKED, "必需阶段尚未完成。", missing)
    return _result("stage_artifacts_complete", PASS, "必需阶段及结果文件完整。", evidence)


def _check_worklist(ctx: HealthContext) -> HealthCheckResult:
    try:
        items = _worklist(ctx).get("items") or []
    except (OSError, ValueError, YamlSubsetError) as exc:
        return _result("worklist_items_resolved", BLOCKED, f"无法检查 worklist：{exc}")
    unresolved = [
        f"{item.get('id', '<unknown>')}:{item.get('status', 'PENDING')}"
        for item in items
        if not isinstance(item, dict) or item.get("status") not in RESOLVED_WORK_ITEM_STATUSES
    ]
    if unresolved:
        return _result("worklist_items_resolved", BLOCKED, "worklist 存在未解决项。", unresolved)
    return _result("worklist_items_resolved", PASS, "worklist 没有未解决项。")


def _looks_like_path(value: str) -> bool:
    return "/" in value or "\\" in value or bool(Path(value).suffix)


def _iter_evidence(result: dict) -> Iterable[str]:
    for value in result.get("evidence") or []:
        if isinstance(value, str) and value:
            yield value
    artifacts = result.get("artifacts") or []
    values = artifacts.values() if isinstance(artifacts, dict) else artifacts
    for value in values:
        if isinstance(value, str) and value:
            yield value
        elif isinstance(value, dict):
            for key in ("path", "document", "evidence"):
                item = value.get(key)
                if isinstance(item, str) and item:
                    yield item
    for rule in result.get("rule_results") or []:
        if isinstance(rule, dict):
            for value in rule.get("evidence") or []:
                if isinstance(value, str) and value:
                    yield value


def _check_evidence(ctx: HealthContext) -> HealthCheckResult:
    invalid = []
    checked = []
    for path, result in ctx.stage_results():
        if result.get("status") not in PASSING_STATUSES:
            continue
        values = list(_iter_evidence(result))
        if ctx.is_v2 and not values:
            invalid.append(f"{path.name} 没有证据")
        for raw in values:
            if not ctx.is_v2 and not _looks_like_path(raw):
                continue
            try:
                checked.append(str(_safe_file(ctx.project, raw)))
            except ValueError as exc:
                invalid.append(f"{path.name}: {raw}: {exc}")
    if invalid:
        return _result("validation_evidence_exists", BLOCKED, "存在无效或缺失的证据文件。", invalid)
    return _result("validation_evidence_exists", PASS, "已引用的证据文件均可读取。", checked)


def _check_cleanup(ctx: HealthContext) -> HealthCheckResult:
    path = ctx.run_dir / "stage-results" / STAGE_RESULT_FILES["test_execution"]
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _result("cleanup_verified", BLOCKED, f"无法读取测试执行结果：{exc}")
    if not ctx.is_v2 and result.get("status") in PASSING_STATUSES:
        return _result("cleanup_verified", PASS, "旧运行以已通过的测试执行结果作为清理证明。", [str(path)])
    candidates = [(path, result)]
    for raw in _iter_evidence(result):
        if not raw.lower().endswith(".json"):
            continue
        try:
            evidence_path = _safe_file(ctx.project, raw)
            value = json.loads(evidence_path.read_text(encoding="utf-8"))
        except (ValueError, OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            candidates.append((evidence_path, value))
    for candidate_path, value in candidates:
        cleanup = value.get("cleanup") if isinstance(value.get("cleanup"), dict) else {}
        extensions = value.get("extensions") if isinstance(value.get("extensions"), dict) else {}
        extension_cleanup = extensions.get("cleanup") if isinstance(extensions.get("cleanup"), dict) else {}
        verified = (
            value.get("cleanup_verified") is True
            or cleanup.get("verified") is True
            or extensions.get("cleanup_verified") is True
            or extension_cleanup.get("verified") is True
        )
        not_applicable = any(
            item.get("not_applicable") is True and bool(str(item.get("reason") or "").strip())
            for item in (cleanup, extension_cleanup)
        )
        if verified or not_applicable:
            return _result(
                "cleanup_verified",
                PASS,
                "测试数据清理已验证或已说明不适用。",
                [str(candidate_path)],
            )
    return _result("cleanup_verified", BLOCKED, "v2 测试结果缺少清理验证或不适用理由。", [str(path)])


def _check_ci_gap(ctx: HealthContext) -> HealthCheckResult:
    workflows = sorted((ctx.project / ".github" / "workflows").glob("*.yml"))
    workflows += sorted((ctx.project / ".github" / "workflows").glob("*.yaml"))
    if workflows:
        return _result("ci_gap_declared", PASS, "已检测到 CI 配置。", [str(path) for path in workflows])
    return _result("ci_gap_declared", CI_REQUIRED, "本地未检测到 CI 配置，结果已声明为需要 CI 验证。")


def _rule_results(ctx: HealthContext) -> dict[str, dict]:
    results = {}
    for _, stage_result in ctx.stage_results():
        for value in stage_result.get("rule_results") or []:
            if isinstance(value, dict):
                rule_id = value.get("rule_id") or value.get("id")
                if isinstance(rule_id, str) and rule_id:
                    results[rule_id] = value
    return results


def _check_required_rules(ctx: HealthContext) -> HealthCheckResult:
    try:
        snapshot = load_policy_snapshot(ctx.project, ctx.state)
    except ValueError as exc:
        return _result("required_rule_results", BLOCKED, f"无法读取规则快照：{exc}")
    actual = _rule_results(ctx)
    completed_stages = set(STAGE_SEQUENCE[:STAGE_SEQUENCE.index("health_gate")])
    required = [
        rule for rule in snapshot.get("rules") or []
        if rule.get("level") == "required"
        and completed_stages.intersection(rule.get("stages") or [])
    ]
    missing = []
    unavailable = []
    for rule in required:
        value = actual.get(rule.get("id"))
        if not value:
            missing.append(str(rule.get("id") or "<unknown>"))
        elif not value.get("evidence"):
            missing.append(f"{rule.get('id')} 缺少证据")
        elif value.get("status") in PASSING_STATUSES:
            continue
        elif value.get("status") == rule.get("unavailable") and value.get("status") in {CI_REQUIRED, SKIPPED}:
            unavailable.append(value.get("status"))
        else:
            missing.append(f"{rule.get('id')} 状态为 {value.get('status') or 'UNKNOWN'}")
    if missing:
        return _result("required_rule_results", BLOCKED, "必需规则缺少有效结果。", missing)
    if CI_REQUIRED in unavailable:
        return _result("required_rule_results", CI_REQUIRED, "部分必需规则已声明由 CI 验证。", sorted(actual))
    if SKIPPED in unavailable:
        return _result("required_rule_results", SKIPPED, "部分必需规则按配置跳过。", sorted(actual))
    return _result("required_rule_results", PASS, "必需规则均有有效结果。", sorted(actual))


def _check_accepted_risks(ctx: HealthContext) -> HealthCheckResult:
    unconfirmed = []
    confirmed_rule_ids = set()
    for _, stage_result in ctx.stage_results():
        for entry in stage_result.get("artifacts") or []:
            if not isinstance(entry, dict) or entry.get("type") != "quality_result":
                continue
            try:
                artifact_path = _safe_file(ctx.project, entry.get("path") or "")
                artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            for item in artifact.get("accepted_risks") or []:
                if not isinstance(item, dict) or not item.get("rule_id") or not item.get("confirmation_evidence"):
                    continue
                try:
                    _safe_file(ctx.project, item["confirmation_evidence"])
                except ValueError:
                    continue
                confirmed_rule_ids.add(item["rule_id"])
    for rule_id, value in _rule_results(ctx).items():
        if value.get("status") != "ACCEPTED_RISK":
            continue
        if rule_id not in confirmed_rule_ids:
            unconfirmed.append(rule_id)
    decision = ctx.state.get("mode_decision") or {}
    accepted = decision.get("accepted_risk") or {}
    if accepted.get("selected_lower_than_recommended"):
        if not accepted.get("reason") or decision.get("selected_by") != "user":
            unconfirmed.append("mode_selection")
    if unconfirmed:
        return _result("accepted_risks_confirmed", BLOCKED, "存在未获用户确认的风险接受。", unconfirmed)
    return _result("accepted_risks_confirmed", PASS, "风险接受记录均已确认。")


def _check_snapshot(ctx: HealthContext) -> HealthCheckResult:
    try:
        load_policy_snapshot(ctx.project, ctx.state)
    except ValueError as exc:
        return _result("policy_snapshot_integrity", BLOCKED, f"规则快照检查失败：{exc}")
    return _result(
        "policy_snapshot_integrity",
        PASS,
        "规则快照摘要有效。",
        [str(ctx.state.get("policy_snapshot"))],
    )


CORE_CHECKS: dict[str, Callable[[HealthContext], HealthCheckResult]] = {
    "stage_artifacts_complete": _check_stage_artifacts,
    "worklist_items_resolved": _check_worklist,
    "validation_evidence_exists": _check_evidence,
    "cleanup_verified": _check_cleanup,
    "ci_gap_declared": _check_ci_gap,
    "required_rule_results": _check_required_rules,
    "accepted_risks_confirmed": _check_accepted_risks,
    "policy_snapshot_integrity": _check_snapshot,
}


_SECRET_PAIR = re.compile(
    r"(?i)([\"']?(?:password|passwd|secret|token|api[_-]?key|authorization)[\"']?\s*[:=]\s*)"
    r"([\"']?)([^\"'\s,;]+)([\"']?)"
)
_BEARER = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/-]+")


def redact_output(value, sensitive_values: Iterable[str] = (), limit: int = DEFAULT_OUTPUT_LIMIT) -> str:
    """脱敏并限制命令输出长度，避免凭据进入健康结果。"""

    if value is None:
        text = ""
    elif isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = str(value)
    for secret in sensitive_values:
        if isinstance(secret, str) and secret:
            text = text.replace(secret, "[REDACTED]")
    text = _SECRET_PAIR.sub(
        lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]{match.group(4)}",
        text,
    )
    text = _BEARER.sub("Bearer [REDACTED]", text)
    if len(text) > limit:
        text = text[:limit] + "\n[OUTPUT_TRUNCATED]"
    return text


def _command_kind(spec: dict) -> str:
    if spec.get("ci_only") is True:
        return "ci_backed"
    kind = spec.get("kind") or spec.get("requiredness") or spec.get("availability")
    if kind in {"optional", "ci_backed", "required"}:
        return kind
    if spec.get("ci_backed") is True:
        return "ci_backed"
    if spec.get("required") is False:
        return "optional"
    return "required"


def _unavailable_status(kind: str, policies: dict) -> str:
    status = policies.get(kind) if isinstance(policies, dict) else None
    expected = {"optional": SKIPPED, "ci_backed": CI_REQUIRED, "required": BLOCKED}[kind]
    return status if status in {SKIPPED, CI_REQUIRED, BLOCKED} else expected


def run_project_command(
    command_id: str,
    spec: dict,
    project: Path,
    *,
    missing_tool_policy: dict | None = None,
    command_runner: Callable | None = None,
    max_timeout_seconds: float = MAX_TIMEOUT_SECONDS,
    output_limit: int = DEFAULT_OUTPUT_LIMIT,
) -> HealthCheckResult:
    """安全执行一项项目命令，并返回可序列化结果。"""

    argv = spec.get("argv") if isinstance(spec, dict) else None
    if not isinstance(argv, list) or not argv or any(not isinstance(item, str) or not item for item in argv):
        return _result(f"command:{command_id}", BLOCKED, "项目命令 argv 必须是非空字符串数组。")
    kind = _command_kind(spec)
    explicit_kind = spec.get("kind") or spec.get("requiredness") or spec.get("availability")
    if explicit_kind is not None and explicit_kind not in {"optional", "ci_backed", "required"}:
        return _result(f"command:{command_id}", BLOCKED, "项目命令可用性分类不合法。")
    if spec.get("ci_only") is True:
        return _result(f"command:{command_id}", CI_REQUIRED, "项目命令已声明只在 CI 中执行。")
    try:
        timeout = float(spec.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS))
    except (TypeError, ValueError):
        return _result(f"command:{command_id}", BLOCKED, "项目命令超时必须是数字。")
    try:
        effective_max_timeout = min(float(max_timeout_seconds), MAX_TIMEOUT_SECONDS)
    except (TypeError, ValueError):
        return _result(f"command:{command_id}", BLOCKED, "最大超时配置不是数字。")
    if effective_max_timeout <= 0 or timeout <= 0 or timeout > effective_max_timeout:
        return _result(
            f"command:{command_id}",
            BLOCKED,
            f"项目命令超时必须大于 0 且不超过 {effective_max_timeout:g} 秒。",
        )
    sensitive = spec.get("sensitive_values") or []
    if not isinstance(sensitive, list):
        return _result(f"command:{command_id}", BLOCKED, "sensitive_values 必须是字符串数组。")
    sensitive = [
        *sensitive,
        *[
            value for name, value in os.environ.items()
            if value and re.search(r"(?i)(password|passwd|secret|token|api[_-]?key|authorization)", name)
        ],
    ]
    runner = command_runner or subprocess.run
    try:
        completed = runner(
            argv,
            cwd=str(project.resolve()),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            shell=False,
        )
    except FileNotFoundError:
        status = _unavailable_status(kind, missing_tool_policy or {})
        return _result(f"command:{command_id}", status, "项目命令工具不存在；未执行自动安装。")
    except subprocess.TimeoutExpired as exc:
        status = _unavailable_status(kind, missing_tool_policy or {})
        return _result(
            f"command:{command_id}",
            status,
            f"项目命令在 {timeout:g} 秒后超时。",
            details={
                "exit_code": None,
                "timed_out": True,
                "stdout": redact_output(exc.stdout, sensitive, output_limit),
                "stderr": redact_output(exc.stderr, sensitive, output_limit),
            },
        )
    except OSError as exc:
        status = _unavailable_status(kind, missing_tool_policy or {})
        return _result(f"command:{command_id}", status, f"项目命令无法启动：{exc.__class__.__name__}")

    status = PASS if completed.returncode == 0 else _unavailable_status(kind, missing_tool_policy or {})
    message = "项目命令执行成功。" if status == PASS else f"项目命令退出码为 {completed.returncode}。"
    return _result(
        f"command:{command_id}",
        status,
        message,
        [f"exit_code:{completed.returncode}"],
        {
            "exit_code": completed.returncode,
            "timed_out": False,
            "stdout": redact_output(completed.stdout, sensitive, output_limit),
            "stderr": redact_output(completed.stderr, sensitive, output_limit),
        },
    )


def _command_specs(snapshot: dict) -> list[tuple[str, dict]]:
    commands = snapshot.get("commands") or {}
    if isinstance(commands, dict):
        values = []
        for command_id, spec in commands.items():
            values.append((str(command_id), {"argv": spec} if isinstance(spec, list) else spec))
        return [(name, spec) for name, spec in values if isinstance(spec, dict)]
    if isinstance(commands, list):
        return [
            (str(spec.get("id") or f"command-{index + 1}"), spec)
            for index, spec in enumerate(commands)
            if isinstance(spec, dict)
        ]
    return []


def _configured_check(entry, default_required: bool) -> tuple[str, bool]:
    if isinstance(entry, str):
        return entry, default_required
    if isinstance(entry, dict):
        return str(entry.get("id") or ""), bool(entry.get("required", default_required))
    return "", default_required


def execute_health(
    project: Path | str,
    run_id: str,
    *,
    config_path: Path | str | None = None,
    write_result: bool = False,
    command_runner: Callable | None = None,
    check_registry: dict[str, Callable[[HealthContext], HealthCheckResult]] | None = None,
) -> HealthReport:
    """执行配置中的核心检查和 v2 项目命令。"""

    root = Path(project).resolve()
    try:
        run_dir = _run_directory(root, run_id)
    except ValueError as exc:
        return HealthReport(run_id, BLOCKED, [_result("run_directory", BLOCKED, str(exc))], False)
    path = Path(config_path) if config_path else Path(__file__).resolve().parents[1] / "health.yml"
    try:
        config = load_health_config(path)
        state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
        if not isinstance(state, dict) or state.get("run_id") != run_id:
            raise ValueError("state.run_id 与所选运行不一致")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        report = HealthReport(run_id, BLOCKED, [_result("health_configuration", BLOCKED, str(exc))], False)
        if write_result and run_dir.is_dir():
            write_health_result(root, run_id, report)
        return report

    ctx = HealthContext(root, run_id, run_dir, state, config, command_runner)
    registry = dict(CORE_CHECKS)
    if check_registry:
        registry.update(check_registry)
    checks = []
    seen = set()
    default_required = bool(config.get("core_required", True))
    for entry in config.get("core_checks") or []:
        check_id, required = _configured_check(entry, default_required)
        if not check_id or check_id in seen:
            checks.append(_result(check_id or "invalid_core_check", BLOCKED, "核心检查 ID 为空或重复。"))
            continue
        seen.add(check_id)
        if not ctx.is_v2 and check_id in V2_ONLY_CHECKS:
            continue
        check = registry.get(check_id)
        if check is None:
            status = BLOCKED if required else SKIPPED
            checks.append(_result(check_id, status, "健康检查配置引用了未知检查。"))
            continue
        try:
            checks.append(check(ctx))
        except Exception as exc:  # 核心检查异常必须转为明确失败，不能伪装通过。
            checks.append(_result(check_id, BLOCKED, f"核心检查执行异常：{exc.__class__.__name__}: {exc}"))

    if ctx.is_v2:
        try:
            snapshot = load_policy_snapshot(root, state)
        except ValueError:
            snapshot = None
        if snapshot is not None:
            limits = config.get("command_execution") or {}
            try:
                max_timeout = float(limits.get("max_timeout_seconds") or MAX_TIMEOUT_SECONDS)
                output_limit = int(limits.get("output_limit") or DEFAULT_OUTPUT_LIMIT)
            except (TypeError, ValueError):
                checks.append(_result("command_configuration", BLOCKED, "项目命令执行限制必须是数字。"))
                max_timeout = 0
                output_limit = 0
            if max_timeout <= 0 or max_timeout > MAX_TIMEOUT_SECONDS:
                checks.append(_result(
                    "command_configuration",
                    BLOCKED,
                    f"最大命令超时必须大于 0 且不超过 {MAX_TIMEOUT_SECONDS:g} 秒。",
                ))
                max_timeout = 0
            if output_limit <= 0 or output_limit > MAX_OUTPUT_LIMIT:
                checks.append(_result(
                    "command_configuration",
                    BLOCKED,
                    f"命令输出上限必须大于 0 且不超过 {MAX_OUTPUT_LIMIT} 字符。",
                ))
                output_limit = 0
            policies = config.get("missing_tool_policy") or {}
            command_specs = _command_specs(snapshot) if max_timeout and output_limit else []
            command_ids = [command_id for command_id, _ in command_specs]
            if len(command_ids) != len(set(command_ids)):
                checks.append(_result("command_configuration", BLOCKED, "项目命令 ID 不能重复。"))
                command_specs = []
            for command_id, spec in command_specs:
                checks.append(run_project_command(
                    command_id,
                    spec,
                    root,
                    missing_tool_policy=policies,
                    command_runner=command_runner,
                    max_timeout_seconds=max_timeout,
                    output_limit=output_limit,
                ))

    status = aggregate_status(checks, config.get("result_status") or {})
    ci_check = next((item for item in checks if item.name == "ci_gap_declared"), None)
    ci_gap_declared = bool(ci_check and ci_check.status in {PASS, CI_REQUIRED})
    report = HealthReport(run_id, status, checks, ci_gap_declared)
    if write_result:
        write_health_result(root, run_id, report)
    return report


def write_health_result(project: Path | str, run_id: str, report: HealthReport) -> Path:
    """将健康结果写入固定运行产物路径。"""

    run_dir = _run_directory(Path(project), run_id)
    path = run_dir / "artifacts" / "health-result.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


# 控制器可直接调用该别名，避免在命令层复制执行逻辑。
run_health = execute_health
