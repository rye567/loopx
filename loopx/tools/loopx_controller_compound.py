#!/usr/bin/env python3
"""记录和校验可复用的 LoopX 经验。"""

import json
import re
from datetime import datetime
from pathlib import Path

from loopx_controller_io import append_event, get_run_dir, load_schema, load_state, project_path, save_state, validate_schema
from loopx_controller_state import resolve_run_id, slugify
from loopx_controller_yaml import YamlSubsetError, parse_yaml_subset


def compound_artifact_rel(run_id):
    return f"docs/loopx/runs/{run_id}/artifacts/compound-capture.md"


def project_solution_rel(category, title):
    return f"docs/loopx/solutions/{slugify(category, max_length=64)}/{slugify(title, max_length=64)}.md"


def render_scalar(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return '""'
    text = str(value)
    if re.fullmatch(r"[A-Za-z0-9_.:/-]+", text):
        return text
    return json.dumps(text, ensure_ascii=False)


def render_frontmatter(data):
    lines = ["---"]
    for key, value in data.items():
        if isinstance(value, list):
            if value:
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {render_scalar(item)}")
            else:
                lines.append(f"{key}: []")
        else:
            lines.append(f"{key}: {render_scalar(value)}")
    lines.append("---")
    return "\n".join(lines)


def render_compound_document(metadata, learning, prevention):
    reason = metadata.get("reason") or ""
    body = [
        render_frontmatter(metadata),
        "",
        f"# {metadata.get('title')}",
        "",
        "## 摘要",
        "",
        metadata.get("summary") or reason,
        "",
    ]
    if metadata.get("decision") == "captured":
        body.extend([
            "## 经验",
            "",
            learning,
            "",
            "## 预防措施",
            "",
            prevention,
            "",
        ])
    else:
        body.extend([
            "## 未沉淀原因",
            "",
            reason,
            "",
        ])
    return "\n".join(body)


def build_compound_metadata(run_id, state, args, artifact_rel, project_doc_rel):
    decision = args.decision
    reason = args.reason or ""
    title = args.title or ("本次未沉淀可复用经验" if decision == "skipped" else "")
    summary = args.summary or reason
    risk_tags = args.risk_tags if args.risk_tags is not None else state.get("risk_tags", [])
    return {
        "schema_version": "v1",
        "run_id": run_id,
        "decision": decision,
        "category": args.category,
        "title": title,
        "summary": summary,
        "reason": reason,
        "risk_tags": risk_tags or [],
        "applies_to": args.applies_to or [],
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "reusable": decision == "captured",
        "artifact": artifact_rel,
        "project_doc": project_doc_rel,
    }


def compound_input_errors(args):
    errors = []
    if args.decision == "skipped" and not args.reason:
        errors.append("--decision 为 skipped 时必须提供 --reason")
    if args.decision == "captured":
        for name in ("title", "summary", "learning", "prevention"):
            if not getattr(args, name):
                errors.append(f"--decision 为 captured 时必须提供 --{name.replace('_', '-')}")
    if args.write_project_doc and args.decision != "captured":
        errors.append("使用 --write-project-doc 时，--decision 必须为 captured")
    return errors


def extract_frontmatter(text):
    if not text.startswith("---\n"):
        raise ValueError("文档必须包含 frontmatter")
    marker = "\n---"
    end = text.find(marker, 4)
    if end == -1:
        raise ValueError("frontmatter 缺少结束标记")
    raw = text[4:end]
    try:
        data = parse_yaml_subset(raw)
    except YamlSubsetError as exc:
        raise ValueError(f"frontmatter 不是有效的 LoopX YAML：{exc}") from exc
    body = text[end + len(marker):]
    if body.startswith("\n"):
        body = body[1:]
    return data, body


def validate_learning_file(path, schema, validate_schema):
    try:
        text = Path(path).read_text(encoding="utf-8")
        metadata, body = extract_frontmatter(text)
    except (OSError, ValueError) as exc:
        return [str(exc)]
    errors = validate_schema(metadata, schema, "frontmatter")
    decision = metadata.get("decision")
    if decision == "captured":
        required_headings = (("## 经验", "## Learning"), ("## 预防措施", "## Prevention"))
        for chinese_heading, legacy_heading in required_headings:
            if chinese_heading not in body and legacy_heading not in body:
                errors.append(f"captured 记录必须包含 {chinese_heading} 章节")
    if decision == "skipped" and "## 未沉淀原因" not in body and "## Skip Reason" not in body:
        errors.append("skipped 记录必须包含 ## 未沉淀原因 章节")
    return errors


def validate_compound_capture(project, capture, schema, validate_schema):
    errors = []
    capture = capture or {}
    decision = capture.get("decision")
    if decision not in {"captured", "skipped"}:
        return ["final_report 记录为 PASS 前，state.compound_capture.decision 必须为 captured 或 skipped"]
    artifact = Path(capture.get("artifact") or "")
    if not artifact.is_absolute():
        artifact = project_path(project, artifact)
    if not artifact.exists():
        errors.append("final_report 记录为 PASS 前，state.compound_capture.artifact 指向的文件必须存在")
    else:
        errors.extend(validate_learning_file(artifact, schema, validate_schema))
    project_doc = capture.get("project_doc") or ""
    if project_doc:
        project_doc_path = Path(project_doc)
        if not project_doc_path.is_absolute():
            project_doc_path = project_path(project, project_doc_path)
        if not project_doc_path.exists():
            errors.append("state.compound_capture.project_doc 已记录时，对应文件必须存在")
    return errors


def cmd_compound(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        state = load_state(project, run_id)
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    errors = compound_input_errors(args)
    if errors:
        print(f"FAIL 经验沉淀记录失败：{run_id}", file=stdout)
        for error in errors:
            print(f"- {error}", file=stdout)
        return 1
    artifact_rel = compound_artifact_rel(run_id)
    # 长期知识库必须显式打开，默认只记录当前 run 的收口证据。
    project_doc_rel = project_solution_rel(args.category, args.title) if args.write_project_doc else ""
    metadata = build_compound_metadata(run_id, state, args, artifact_rel, project_doc_rel)
    document = render_compound_document(metadata, args.learning or "", args.prevention or "")
    artifact_path = project_path(project, artifact_rel)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(document, encoding="utf-8")
    validation_errors = validate_learning_file(artifact_path, load_schema("compound-learning"), validate_schema)
    if validation_errors:
        print(f"FAIL 经验沉淀记录失败：{run_id}", file=stdout)
        for error in validation_errors:
            print(f"- {error}", file=stdout)
        return 1
    if project_doc_rel:
        project_doc_path = project / project_doc_rel
        project_doc_path.parent.mkdir(parents=True, exist_ok=True)
        project_doc_path.write_text(document, encoding="utf-8")
    state["compound_capture"] = {
        "decision": metadata["decision"],
        "artifact": artifact_rel,
        "project_doc": project_doc_rel,
        "reusable": metadata["reusable"],
    }
    save_state(project, run_id, state)
    append_event(get_run_dir(project, run_id), {
        "type": "compound_capture_recorded",
        "decision": metadata["decision"],
        "artifact": artifact_rel,
        "project_doc": project_doc_rel,
    })
    print(f"PASS 已记录经验沉淀决定：{run_id}", file=stdout)
    print(f"决定：{metadata['decision']}", file=stdout)
    print(f"运行产物：{artifact_rel}", file=stdout)
    if project_doc_rel:
        print(f"项目文档：{project_doc_rel}", file=stdout)
    return 0


def cmd_validate_learning(args, stdout):
    project = Path(args.project).resolve()
    path = Path(args.path)
    if not path.is_absolute():
        path = project_path(project, path)
    errors = validate_learning_file(path, load_schema("compound-learning"), validate_schema)
    if errors:
        print(f"FAIL 经验文档检查未通过：{path}", file=stdout)
        for error in errors:
            print(f"- {error}", file=stdout)
        return 1
    print(f"PASS 经验文档检查通过：{path}", file=stdout)
    return 0
