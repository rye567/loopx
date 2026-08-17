#!/usr/bin/env python3
"""LoopX 本地 harness 检查。

本工具只依赖 Python 标准库，支持两种模式：

- package：检查 LoopX 包是否包含标准化资产。
- project：检查目标项目的本地 LoopX run 结构和证据。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from loopx_health import aggregate_status as aggregate_health_status  # noqa: E402
from loopx_health import execute_health  # noqa: E402
from loopx_controller_io import get_run_dir  # noqa: E402
from loopx_controller_state import latest_run_id  # noqa: E402
from loopx_controller_store import ExternalRunSession, StoreError, uses_project_backend  # noqa: E402

PASS = "PASS"
PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
LOCAL_INCOMPLETE_CI_REQUIRED = "LOCAL_INCOMPLETE_CI_REQUIRED"
BLOCKED = "BLOCKED"

REQUIRED_STANDARDS = [
    "principles.md",
    "requirement-standard.md",
    "architecture-standard.md",
    "security-standard.md",
    "performance-standard.md",
    "reliability-observability-standard.md",
    "development-standard.md",
    "testing-standard.md",
    "quality-standard.md",
    "release-standard.md",
]

REQUIRED_SKILLS = [
    "requirement-interview-skill.md",
    "spec-generation-skill.md",
    "spec-review-skill.md",
    "mode-selection-skill.md",
    "stage-tracking-skill.md",
    "architecture-design-skill.md",
    "design-review-skill.md",
    "test-design-skill.md",
    "quality-scan-skill.md",
    "release-check-skill.md",
    "compound-capture-skill.md",
]

REQUIRED_AGENT_DOCS = [
    "controller.md",
    "requirement-manager.md",
    "requirement-interviewer-agent.md",
    "spec-writer-agent.md",
    "spec-reviewer-agent.md",
    "mode-selector-agent.md",
    "release-manager.md",
]

REQUIRED_TEMPLATES = [
    "00-requirement-intake.md",
    "01-requirement-interview.md",
    "02-spec.md",
    "03-spec-review.md",
    "04-mode-selection.md",
    "tracking-snapshot.md",
    "11-release-readiness.md",
    "12-final-report.md",
    "13-compound-capture.md",
    "loopx-policy.yml",
]

REQUIRED_SCHEMAS = [
    "standard-catalog.schema.json",
    "project-policy.schema.json",
    "state.schema.json",
    "stage-result.schema.json",
    "worklist.schema.json",
    "interview.schema.json",
    "spec.schema.json",
    "mode.schema.json",
    "tracking.schema.json",
    "health-result.schema.json",
    "compound-learning.schema.json",
    "solution.schema.json",
    "test-plan.schema.json",
    "development-evidence.schema.json",
    "quality-result.schema.json",
    "performance-result.schema.json",
    "security-result.schema.json",
]

REQUIRED_POLICY_FILES = [
    "standards/catalog.yml",
    "risk.yml",
    "health.yml",
    "project-profiles.yml",
]

FORBIDDEN_SOURCE_PATTERNS = [
    (re.compile(r"System\.out\.println"), "Java debug print"),
    (re.compile(r"console\.log\("), "JavaScript debug print"),
    (re.compile(r"TODO\s*:\s*delete|FIXME\s*:\s*ignore", re.IGNORECASE), "unsafe temporary marker"),
]

SOURCE_EXTENSIONS = {".java", ".kt", ".py", ".js", ".ts", ".tsx", ".go", ".rs"}
SKIP_DIRS = {".git", ".loopx", "node_modules", "dist", "build", "target", ".venv", "venv"}


@dataclass
class CheckResult:
    name: str
    status: str
    message: str
    evidence: list[str] = field(default_factory=list)


@dataclass
class HarnessReport:
    mode: str
    root: str
    status: str
    checks: list[CheckResult]

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "root": self.root,
            "status": self.status,
            "checks": [check.__dict__ for check in self.checks],
        }


def existing(paths: Iterable[Path]) -> list[str]:
    return [str(path) for path in paths if path.exists()]


def check_required_files(root: Path, label: str, relative_dir: str, names: list[str]) -> CheckResult:
    base = root / relative_dir
    missing = [name for name in names if not (base / name).exists()]
    if missing:
        return CheckResult(
            name=f"必需_{label}",
            status=BLOCKED,
            message=f"缺少必需 {label}: {', '.join(missing)}",
            evidence=existing(base / name for name in names),
        )
    return CheckResult(
        name=f"必需_{label}",
        status=PASS,
        message=f"所有必需 {label} 均存在。",
        evidence=[str(base / name) for name in names],
    )


def file_contains_all(path: Path, required_terms: list[str]) -> bool:
    text = path.read_text(encoding="utf-8")
    lowered = text.lower()
    return all(term.lower() in lowered for term in required_terms)


def check_skill_contracts(root: Path) -> CheckResult:
    base = root / "loopx" / "skills"
    missing_contract = []
    required_terms = ["目的", "输入", "步骤", "输出", "通过标准", "失败处理"]
    for name in REQUIRED_SKILLS:
        path = base / name
        if path.exists() and not file_contains_all(path, required_terms):
            missing_contract.append(name)
    if missing_contract:
        return CheckResult(
            name="技能契约",
            status=BLOCKED,
            message="部分技能未声明完整契约。",
            evidence=missing_contract,
        )
    return CheckResult(
        name="技能契约",
        status=PASS,
        message="所有必需技能均声明输入、输出和检查契约。",
        evidence=[str(base / name) for name in REQUIRED_SKILLS if (base / name).exists()],
    )


def evaluate_package(root: Path) -> HarnessReport:
    root = root.resolve()
    checks = [
        check_required_files(root, "标准", "loopx/standards", REQUIRED_STANDARDS),
        check_required_files(root, "技能", "loopx/skills", REQUIRED_SKILLS),
        check_required_files(root, "智能体文档", "loopx/agents", REQUIRED_AGENT_DOCS),
        check_required_files(root, "模板", "loopx/templates", REQUIRED_TEMPLATES),
        check_required_files(root, "结构契约", "loopx/schemas", REQUIRED_SCHEMAS),
        check_required_files(root, "策略资源", "loopx", REQUIRED_POLICY_FILES),
        check_skill_contracts(root),
    ]
    status = BLOCKED if any(check.status == BLOCKED for check in checks) else PASS
    return HarnessReport(mode="package", root=str(root), status=status, checks=checks)


def load_json(path: Path) -> tuple[dict | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, f"{path} 不存在"
    except json.JSONDecodeError as exc:
        return None, f"{path} 不是合法 JSON: {exc}"


def find_latest_run(root: Path) -> Path | None:
    run_id = latest_run_id(root)
    return get_run_dir(root, run_id) if run_id else None


def check_project_run(root: Path) -> CheckResult:
    latest = find_latest_run(root)
    if latest is None:
        return CheckResult(
            name="loopx_run_state",
            status=PASS_WITH_WARNINGS,
            message="未发现 docs/loopx/runs/<run_id>；项目尚未创建本地 LoopX run。",
            evidence=[],
        )
    state, error = load_json(latest / "state.json")
    if error:
        return CheckResult("loopx_run_state", BLOCKED, error, [str(latest)])
    required = ["run_id", "requirement", "mode", "status", "current_stage", "worklist", "events", "stages"]
    missing = [key for key in required if key not in state or state[key] in (None, "")]
    if missing:
        return CheckResult(
            name="loopx_run_state",
            status=BLOCKED,
            message=f"最新 run state 缺少必需字段: {', '.join(missing)}",
            evidence=[str(latest / "state.json")],
        )
    return CheckResult(
        name="loopx_run_state",
        status=PASS,
        message=f"最新 run state 可读取: {state.get('run_id')}",
        evidence=[str(latest / "state.json")],
    )


def check_project_stage_results(root: Path) -> CheckResult:
    latest = find_latest_run(root)
    if latest is None:
        return CheckResult("stage_results", PASS_WITH_WARNINGS, "尚未发现 run 阶段结果。", [])
    stage_dir = latest / "stage-results"
    if not stage_dir.exists():
        return CheckResult("stage_results", BLOCKED, "缺少 stage-results 目录。", [str(latest)])
    result_files = sorted(stage_dir.glob("*.json"))
    if not result_files:
        return CheckResult("stage_results", PASS_WITH_WARNINGS, "尚未写入阶段结果文件。", [str(stage_dir)])
    invalid = []
    for path in result_files:
        data, error = load_json(path)
        if error:
            invalid.append(error)
            continue
        for key in ["stage", "status", "return_to", "next_action", "affected_work_items", "evidence"]:
            if key not in data:
                invalid.append(f"{path.name} 缺少 {key}")
    if invalid:
        return CheckResult("stage_results", BLOCKED, "阶段结果文件结构无效。", invalid)
    return CheckResult("stage_results", PASS, "阶段结果文件结构可读取。", [str(path) for path in result_files])


def iter_source_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in SOURCE_EXTENSIONS:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def check_forbidden_patterns(root: Path) -> CheckResult:
    findings = []
    for path in iter_source_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern, label in FORBIDDEN_SOURCE_PATTERNS:
            if pattern.search(text):
                findings.append(f"{path}: {label}")
    if findings:
        return CheckResult("forbidden_patterns", BLOCKED, "发现禁止的源码模式。", findings[:50])
    return CheckResult("forbidden_patterns", PASS, "未发现禁止的源码模式。", [])


def check_ci_gap(root: Path) -> CheckResult:
    workflow_dir = root / ".github" / "workflows"
    if workflow_dir.exists() and any(workflow_dir.glob("*.yml")):
        return CheckResult("ci_gap", PASS, "检测到 CI workflow 文件。", [str(path) for path in workflow_dir.glob("*.yml")])
    return CheckResult(
        "ci_gap",
        LOCAL_INCOMPLETE_CI_REQUIRED,
        "未检测到 GitHub Actions workflow；最终报告必须声明 CI/远端缺口。",
        [],
    )


def _evaluate_project_loaded(root: Path) -> HarnessReport:
    latest = find_latest_run(root)
    if latest is None:
        checks = [
            check_project_run(root),
            check_project_stage_results(root),
            check_forbidden_patterns(root),
            check_ci_gap(root),
        ]
        status = aggregate_health_status(check.status for check in checks)
        return HarnessReport(mode="project", root=str(root), status=status, checks=checks)

    # 项目模式与控制器共用配置驱动的执行器，避免两处维护不同判断。
    health_report = execute_health(root, latest.name, write_result=False)
    checks = [
        check_project_run(root),
        *[
            CheckResult(item.name, item.status, item.message, item.evidence)
            for item in health_report.checks
        ],
        check_forbidden_patterns(root),
    ]
    status = aggregate_health_status([health_report.status, *(check.status for check in checks)])
    return HarnessReport(mode="project", root=str(root), status=status, checks=checks)


def evaluate_project(root: Path) -> HarnessReport:
    root = root.resolve()
    try:
        run_id = latest_run_id(root)
        if run_id is None or uses_project_backend(root, run_id):
            return _evaluate_project_loaded(root)
        with ExternalRunSession(root, run_id):
            return _evaluate_project_loaded(root)
    except (StoreError, OSError) as exc:
        return HarnessReport(
            mode="project",
            root=str(root),
            status=BLOCKED,
            checks=[CheckResult("loopx_run_state", BLOCKED, f"状态存储错误：{exc}", [])],
        )


def print_text(report: HarnessReport) -> None:
    print(f"LoopX check: {report.mode}")
    print(f"root: {report.root}")
    print(f"status: {report.status}")
    for check in report.checks:
        print(f"- [{check.status}] {check.name}: {check.message}")
        for item in check.evidence[:10]:
            print(f"  evidence: {item}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LoopX local harness checks.")
    parser.add_argument("mode", choices=["package", "project"], help="Check LoopX package assets or a target project.")
    parser.add_argument("--root", default=".", help="Repository or project root.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root)
    report = evaluate_package(root) if args.mode == "package" else evaluate_project(root)
    if args.format == "json":
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print_text(report)
    return 0 if report.status in {PASS, PASS_WITH_WARNINGS, LOCAL_INCOMPLETE_CI_REQUIRED} else 1


if __name__ == "__main__":
    sys.exit(main())
