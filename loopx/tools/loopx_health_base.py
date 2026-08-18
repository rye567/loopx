#!/usr/bin/env python3
"""LoopX 健康检查的公共契约层（常量、数据结构与基础辅助）。

 检查器在 ``loopx_health_checks.py``，项目命令执行在
 ``loopx_health_commands.py``，执行入口仍由 ``loopx_health.py`` 提供；
 三者都只依赖本模块，避免互相形成环。
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from loopx_controller_contracts import (  # noqa: E402
    PASSING_STATUSES,
    STAGE_RESULT_FILES,
    STAGE_SEQUENCE,
)
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

# 供门面 re-export，保持 ``loopx_health.STAGE_SEQUENCE`` 等旧引用可用。
__all__ = [
    "PASS",
    "CI_REQUIRED",
    "SKIPPED",
    "BLOCKED",
    "PASS_WITH_WARNINGS",
    "LOCAL_INCOMPLETE_CI_REQUIRED",
    "PASSING_STATUSES",
    "STAGE_RESULT_FILES",
    "STAGE_SEQUENCE",
]


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
