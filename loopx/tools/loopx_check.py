#!/usr/bin/env python3
"""LoopX local harness checks.

This tool intentionally uses only the Python standard library. It supports two
modes:

- kit: validate that the LoopX kit contains standardization assets.
- project: validate a target project's local LoopX run structure and evidence.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

PASS = "PASS"
PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
LOCAL_INCOMPLETE_CI_REQUIRED = "LOCAL_INCOMPLETE_CI_REQUIRED"
BLOCKED = "BLOCKED"

REQUIRED_STANDARDS = [
    "requirement-standard.md",
    "development-standard.md",
    "testing-standard.md",
    "quality-standard.md",
    "release-standard.md",
]

REQUIRED_SKILLS = [
    "requirement-interview-skill.md",
    "architecture-design-skill.md",
    "design-review-skill.md",
    "test-design-skill.md",
    "quality-scan-skill.md",
    "release-check-skill.md",
]

REQUIRED_AGENT_DOCS = [
    "controller.md",
    "requirement-manager.md",
    "release-manager.md",
]

REQUIRED_TEMPLATES = [
    "00-requirement-intake.md",
    "11-release-readiness.md",
    "12-final-report.md",
]

REQUIRED_SCHEMAS = [
    "state.schema.json",
    "stage-result.schema.json",
    "worklist.schema.json",
    "health-result.schema.json",
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
            name=f"required_{label}",
            status=BLOCKED,
            message=f"Missing required {label}: {', '.join(missing)}",
            evidence=existing(base / name for name in names),
        )
    return CheckResult(
        name=f"required_{label}",
        status=PASS,
        message=f"All required {label} are present.",
        evidence=[str(base / name) for name in names],
    )


def file_contains_all(path: Path, required_terms: list[str]) -> bool:
    text = path.read_text(encoding="utf-8")
    lowered = text.lower()
    return all(term.lower() in lowered for term in required_terms)


def check_skill_contracts(root: Path) -> CheckResult:
    base = root / "loopx" / "skills"
    missing_contract = []
    required_terms = ["purpose", "inputs", "procedure", "output", "pass criteria", "failure"]
    for name in REQUIRED_SKILLS:
        path = base / name
        if path.exists() and not file_contains_all(path, required_terms):
            missing_contract.append(name)
    if missing_contract:
        return CheckResult(
            name="skill_contracts",
            status=BLOCKED,
            message="Some skills do not declare the full contract.",
            evidence=missing_contract,
        )
    return CheckResult(
        name="skill_contracts",
        status=PASS,
        message="All required skills declare input/output/gate contracts.",
        evidence=[str(base / name) for name in REQUIRED_SKILLS if (base / name).exists()],
    )


def evaluate_kit(root: Path) -> HarnessReport:
    root = root.resolve()
    checks = [
        check_required_files(root, "standards", "loopx/standards", REQUIRED_STANDARDS),
        check_required_files(root, "skills", "loopx/skills", REQUIRED_SKILLS),
        check_required_files(root, "agent_docs", "loopx/agents", REQUIRED_AGENT_DOCS),
        check_required_files(root, "templates", "loopx/templates", REQUIRED_TEMPLATES),
        check_required_files(root, "schemas", "loopx/schemas", REQUIRED_SCHEMAS),
        check_skill_contracts(root),
    ]
    status = BLOCKED if any(check.status == BLOCKED for check in checks) else PASS
    return HarnessReport(mode="kit", root=str(root), status=status, checks=checks)


def load_json(path: Path) -> tuple[dict | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, f"{path} does not exist"
    except json.JSONDecodeError as exc:
        return None, f"{path} is not valid JSON: {exc}"


def find_latest_run(root: Path) -> Path | None:
    runs = root / ".loopx" / "runs"
    if not runs.exists():
        return None
    candidates = [path for path in runs.iterdir() if path.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def check_project_run(root: Path) -> CheckResult:
    latest = find_latest_run(root)
    if latest is None:
        return CheckResult(
            name="loopx_run_state",
            status=PASS_WITH_WARNINGS,
            message="No .loopx run found; project has not created a local LoopX run yet.",
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
            message=f"Latest run state is missing required fields: {', '.join(missing)}",
            evidence=[str(latest / "state.json")],
        )
    return CheckResult(
        name="loopx_run_state",
        status=PASS,
        message=f"Latest run state is readable: {state.get('run_id')}",
        evidence=[str(latest / "state.json")],
    )


def check_project_stage_results(root: Path) -> CheckResult:
    latest = find_latest_run(root)
    if latest is None:
        return CheckResult("stage_results", PASS_WITH_WARNINGS, "No run stage results found yet.", [])
    stage_dir = latest / "stage-results"
    if not stage_dir.exists():
        return CheckResult("stage_results", BLOCKED, "stage-results directory is missing.", [str(latest)])
    result_files = sorted(stage_dir.glob("*.json"))
    if not result_files:
        return CheckResult("stage_results", PASS_WITH_WARNINGS, "No stage result files have been written yet.", [str(stage_dir)])
    invalid = []
    for path in result_files:
        data, error = load_json(path)
        if error:
            invalid.append(error)
            continue
        for key in ["stage", "status", "return_to", "next_action", "affected_work_items", "evidence"]:
            if key not in data:
                invalid.append(f"{path.name} missing {key}")
    if invalid:
        return CheckResult("stage_results", BLOCKED, "Invalid stage result files.", invalid)
    return CheckResult("stage_results", PASS, "Stage result files are structurally readable.", [str(path) for path in result_files])


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
        return CheckResult("forbidden_patterns", BLOCKED, "Forbidden source patterns found.", findings[:50])
    return CheckResult("forbidden_patterns", PASS, "No forbidden source patterns found.", [])


def check_ci_gap(root: Path) -> CheckResult:
    workflow_dir = root / ".github" / "workflows"
    if workflow_dir.exists() and any(workflow_dir.glob("*.yml")):
        return CheckResult("ci_gap", PASS, "CI workflow files detected.", [str(path) for path in workflow_dir.glob("*.yml")])
    return CheckResult(
        "ci_gap",
        LOCAL_INCOMPLETE_CI_REQUIRED,
        "No GitHub Actions workflow detected; final report must declare CI/remote gap.",
        [],
    )


def evaluate_project(root: Path) -> HarnessReport:
    root = root.resolve()
    checks = [
        check_project_run(root),
        check_project_stage_results(root),
        check_forbidden_patterns(root),
        check_ci_gap(root),
    ]
    if any(check.status == BLOCKED for check in checks):
        status = BLOCKED
    elif any(check.status == LOCAL_INCOMPLETE_CI_REQUIRED for check in checks):
        status = LOCAL_INCOMPLETE_CI_REQUIRED
    elif any(check.status == PASS_WITH_WARNINGS for check in checks):
        status = PASS_WITH_WARNINGS
    else:
        status = PASS
    return HarnessReport(mode="project", root=str(root), status=status, checks=checks)


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
    parser.add_argument("mode", choices=["kit", "project"], help="Check LoopX kit assets or a target project.")
    parser.add_argument("--root", default=".", help="Repository or project root.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root)
    report = evaluate_kit(root) if args.mode == "kit" else evaluate_project(root)
    if args.format == "json":
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print_text(report)
    return 0 if report.status in {PASS, PASS_WITH_WARNINGS, LOCAL_INCOMPLETE_CI_REQUIRED} else 1


if __name__ == "__main__":
    sys.exit(main())
