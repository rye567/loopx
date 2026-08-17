#!/usr/bin/env python3
"""Release and close commands for LoopX runs.

收口命令只负责汇总证据；是否可以收口必须先通过 validate_run 的统一检查。
"""

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from loopx_controller_contracts import STAGE_RESULT_FILES, STAGE_SEQUENCE
from loopx_controller_flow import stage_result_path
from loopx_controller_io import (
    append_event,
    get_run_dir,
    load_state,
    load_worklist,
    read_json,
    save_state,
    write_json,
)
from loopx_controller_state import resolve_run_id
from loopx_controller_validation import validate_run
from loopx_controller_yaml import YamlSubsetError, dump_worklist


def collect_git_status(project):
    try:
        probe = subprocess.run(
            ["git", "-C", str(project), "rev-parse", "--is-inside-work-tree"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "NEED_HUMAN", "", str(exc)
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        return "NEED_HUMAN", "", "项目目录不是 Git 工作区"
    try:
        status = subprocess.run(
            ["git", "-C", str(project), "status", "--short"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "NEED_HUMAN", "", str(exc)
    if status.returncode != 0:
        return "NEED_HUMAN", "", (status.stderr or "无法读取 Git 状态").strip()
    summary = status.stdout.strip()
    if not summary:
        return "NEED_HUMAN", "", "没有检测到变更文件"
    return "PASS", summary, ""


def build_close_evidence(project, run_id, state):
    directory = get_run_dir(project, run_id)
    evidence_matrix = {}
    for stage in STAGE_SEQUENCE:
        result_path = stage_result_path(directory, stage)
        entry = {
            "status": state.get("stages", {}).get(stage, "PENDING"),
            "stage_result": f"docs/loopx/runs/{run_id}/stage-results/{STAGE_RESULT_FILES[stage]}",
            "evidence": [],
        }
        if result_path.exists():
            try:
                result = read_json(result_path)
                entry["evidence"] = result.get("evidence", [])
            except ValueError:
                entry["evidence"] = []
        evidence_matrix[stage] = entry
    return {
        "run_id": run_id,
        "status": "PASS",
        "mode": state.get("mode"),
        "git_gate": state.get("git_gate", {}),
        "compound_capture": state.get("compound_capture", {}),
        "evidence_matrix": evidence_matrix,
        "ci_coverage": {
            "status": "LOCAL_ONLY",
            "summary": "本地收口未执行 CI 或远端验证",
        },
        "uncovered": [
            "本地收口未覆盖 CI 或远端验证",
        ],
    }


def archive_intermediate_state(directory):
    """把收口后不再需要的中间状态文件归档，减少机器 JSON 对文档目录的污染。

    保留：stage-results/、close-evidence.json、interview/spec 等可读产物。
    归档：events.jsonl、repair-tickets/ 等仅运行期需要的文件，
    移到 artifacts/archive/ 下统一存放；归档失败不影响 close 收口。
    """
    if not directory.exists():
        return []
    archive_dir = directory / "artifacts" / "archive"
    moves = [
        directory / "events.jsonl",
        directory / "artifacts" / "repair-tickets",
    ]
    moved = []
    warnings = []
    for source in moves:
        if not source.exists():
            continue
        try:
            if source.is_dir():
                target = archive_dir / source.name
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    shutil.rmtree(target)
                source.rename(target)
            else:
                target = archive_dir / source.name
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    target.unlink()
                source.rename(target)
            moved.append(str(target.relative_to(directory)))
        except OSError as exc:
            warnings.append(f"无法归档 {source.name}：{exc}")
    if moved:
        # 事件日志先归档再追加，避免在 run 根目录重建 events.jsonl。
        archive_events = archive_dir / "events.jsonl"
        if archive_events.exists():
            try:
                with archive_events.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps({
                        "time": datetime.now().isoformat(timespec="seconds"),
                        "type": "close_archived",
                        "archived": moved,
                    }, ensure_ascii=False) + "\n")
            except OSError as exc:
                warnings.append(f"无法写入归档事件：{exc}")
    return warnings


def cmd_close(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        state = load_state(project, run_id)
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    if state.get("stages", {}).get("final_report") != "PASS":
        print(f"FAIL 运行无法收口：{run_id}", file=stdout)
        print("- 收口前，final_report 必须为 PASS", file=stdout)
        return 1
    # close 不自行放行，先复用严格检查，避免收口路径和 validate 路径分叉。
    errors = validate_run(project, run_id, strict=True)
    if errors:
        print(f"FAIL 运行无法收口：{run_id}", file=stdout)
        print("- 严格检查未通过", file=stdout)
        for error in errors:
            print(f"- {error}", file=stdout)
        return 1
    state["status"] = "PASS"
    state["current_stage"] = "final_report"
    state["next_action"] = "closed"
    evidence_path = get_run_dir(project, run_id) / "artifacts" / "close-evidence.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(evidence_path, build_close_evidence(project, run_id, state))
    save_state(project, run_id, state)
    try:
        worklist_path, worklist = load_worklist(project, state)
        worklist.setdefault("run", {})["status"] = "PASS"
        worklist["run"]["current_stage"] = "final_report"
        worklist["run"]["next_action"] = "closed"
        worklist_path.write_text(dump_worklist(worklist), encoding="utf-8")
    except (FileNotFoundError, YamlSubsetError):
        pass
    append_event(get_run_dir(project, run_id), {"type": "run_closed", "run_id": run_id})
    archive_warnings = archive_intermediate_state(get_run_dir(project, run_id))
    print(f"PASS 运行已收口：{run_id}", file=stdout)
    print("运行状态：PASS", file=stdout)
    for warning in archive_warnings:
        print(f"警告：{warning}", file=stdout)
    return 0


def cmd_git_gate(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        state = load_state(project, run_id)
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    status, summary, reason = collect_git_status(project)
    state["git_gate"] = {
        "status": status,
        "diff_summary": summary,
        "reason": reason,
    }
    save_state(project, run_id, state)
    append_event(get_run_dir(project, run_id), {
        "type": "git_gate",
        "status": status,
        "reason": reason,
    })
    if status == "PASS":
        print(f"PASS Git 变更检查通过：{run_id}", file=stdout)
        print(summary, file=stdout)
        return 0
    print(f"NEED_HUMAN Git 变更检查需要用户处理：{run_id}", file=stdout)
    print(f"- {reason}", file=stdout)
    return 1
