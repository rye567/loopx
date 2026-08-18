#!/usr/bin/env python3
"""LoopX 健康检查的项目命令安全执行。

 命令必须以参数数组声明，执行时不经过 shell，也不会尝试安装缺失工具；
 输出统一经过脱敏与截断，避免凭据进入健康结果。
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, Iterable

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from loopx_health_base import (  # noqa: E402
    BLOCKED,
    CI_REQUIRED,
    DEFAULT_OUTPUT_LIMIT,
    DEFAULT_TIMEOUT_SECONDS,
    MAX_TIMEOUT_SECONDS,
    PASS,
    SKIPPED,
    HealthCheckResult,
    _result,
)


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
