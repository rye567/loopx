#!/usr/bin/env python3
"""LoopX 配置驱动的健康检查执行器（对外入口）。

 核心检查只依赖 Python 标准库。项目命令必须以参数数组声明，执行时不经过
 shell，也不会尝试安装缺失工具。公共契约在 ``loopx_health_base.py``，
 检查器在 ``loopx_health_checks.py``，命令执行在 ``loopx_health_commands.py``。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    # 允许 v1 场景独立加载本模块（不经过 controller 门面）。
    sys.path.insert(0, str(TOOLS_DIR))

from loopx_controller_contracts import (  # noqa: F401,E402 -- 供旧引用面 re-export
    STAGE_RESULT_FILES,
    STAGE_SEQUENCE,
)
from loopx_controller_policy import load_policy_snapshot  # noqa: E402
from loopx_health_base import (  # noqa: F401,E402
    BLOCKED,
    CI_REQUIRED,
    DEFAULT_OUTPUT_LIMIT,
    DEFAULT_TIMEOUT_SECONDS,
    MAX_OUTPUT_LIMIT,
    MAX_TIMEOUT_SECONDS,
    PASS,
    PASS_WITH_WARNINGS,
    LOCAL_INCOMPLETE_CI_REQUIRED,
    SKIPPED,
    V2_ONLY_CHECKS,
    HealthCheckResult,
    HealthContext,
    HealthReport,
    aggregate_status,
    load_health_config,
    _result,
    _run_directory,
)
from loopx_health_checks import CORE_CHECKS  # noqa: E402
from loopx_health_commands import (  # noqa: F401,E402
    redact_output,
    run_project_command,
    _command_specs,
)


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
