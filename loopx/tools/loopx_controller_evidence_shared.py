#!/usr/bin/env python3
"""LoopX v2 证据模块的共享常量与文件解析。

 产物类型映射、版本与规则状态等契约常量，以及项目内相对文件的
 安全解析都集中在这里；语义校验、工作项校验和阶段记录准备模块
 共同依赖本模块，避免相互引用形成环。
"""

from __future__ import annotations

from pathlib import Path

from loopx_controller_io import project_path
from loopx_controller_store import runtime_relative_path


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
