#!/usr/bin/env python3
"""Compound capture helpers for reusable LoopX learnings."""

import json
import re
from datetime import datetime
from pathlib import Path

from loopx_controller_io import append_event, get_run_dir, load_schema, load_state, save_state, validate_schema
from loopx_controller_state import resolve_run_id
from loopx_controller_yaml import YamlSubsetError, parse_yaml_subset


def slugify(text):
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return slug[:64] or "loopx-learning"


def compound_artifact_rel(run_id):
    return f"docs/loopx/runs/{run_id}/artifacts/compound-capture.md"


def project_solution_rel(category, title):
    return f"docs/loopx/solutions/{slugify(category)}/{slugify(title)}.md"


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
        "## Summary",
        "",
        metadata.get("summary") or reason,
        "",
    ]
    if metadata.get("decision") == "captured":
        body.extend([
            "## Learning",
            "",
            learning,
            "",
            "## Prevention",
            "",
            prevention,
            "",
        ])
    else:
        body.extend([
            "## Skip Reason",
            "",
            reason,
            "",
        ])
    return "\n".join(body)


def build_compound_metadata(run_id, state, args, artifact_rel, project_doc_rel):
    decision = args.decision
    reason = args.reason or ""
    title = args.title or ("Compound capture skipped" if decision == "skipped" else "")
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
        errors.append("--reason is required when decision is skipped")
    if args.decision == "captured":
        for name in ("title", "summary", "learning", "prevention"):
            if not getattr(args, name):
                errors.append(f"--{name.replace('_', '-')} is required when decision is captured")
    if args.write_project_doc and args.decision != "captured":
        errors.append("--write-project-doc requires --decision captured")
    return errors


def extract_frontmatter(text):
    if not text.startswith("---\n"):
        raise ValueError("frontmatter is required")
    marker = "\n---"
    end = text.find(marker, 4)
    if end == -1:
        raise ValueError("frontmatter closing marker is required")
    raw = text[4:end]
    try:
        data = parse_yaml_subset(raw)
    except YamlSubsetError as exc:
        raise ValueError(f"frontmatter is not valid LoopX YAML: {exc}") from exc
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
        for heading in ("## Learning", "## Prevention"):
            if heading not in body:
                errors.append(f"{heading} section is required for captured learning")
    if decision == "skipped" and "## Skip Reason" not in body:
        errors.append("## Skip Reason section is required for skipped learning")
    return errors


def validate_compound_capture(project, capture, schema, validate_schema):
    errors = []
    capture = capture or {}
    decision = capture.get("decision")
    if decision not in {"captured", "skipped"}:
        return ["state.compound_capture.decision must be captured or skipped before final_report PASS"]
    artifact = Path(capture.get("artifact") or "")
    if not artifact.is_absolute():
        artifact = Path(project) / artifact
    if not artifact.exists():
        errors.append("state.compound_capture.artifact must exist before final_report PASS")
    else:
        errors.extend(validate_learning_file(artifact, schema, validate_schema))
    project_doc = capture.get("project_doc") or ""
    if project_doc:
        project_doc_path = Path(project_doc)
        if not project_doc_path.is_absolute():
            project_doc_path = Path(project) / project_doc_path
        if not project_doc_path.exists():
            errors.append("state.compound_capture.project_doc must exist when recorded")
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
        print(f"FAIL compound capture {run_id}", file=stdout)
        for error in errors:
            print(f"- {error}", file=stdout)
        return 1
    artifact_rel = compound_artifact_rel(run_id)
    # 长期知识库必须显式打开，默认只记录当前 run 的收口证据。
    project_doc_rel = project_solution_rel(args.category, args.title) if args.write_project_doc else ""
    metadata = build_compound_metadata(run_id, state, args, artifact_rel, project_doc_rel)
    document = render_compound_document(metadata, args.learning or "", args.prevention or "")
    artifact_path = project / artifact_rel
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(document, encoding="utf-8")
    validation_errors = validate_learning_file(artifact_path, load_schema("compound-learning"), validate_schema)
    if validation_errors:
        print(f"FAIL compound capture {run_id}", file=stdout)
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
    print(f"PASS compound capture {run_id}", file=stdout)
    print(f"decision: {metadata['decision']}", file=stdout)
    print(f"artifact: {artifact_rel}", file=stdout)
    if project_doc_rel:
        print(f"project_doc: {project_doc_rel}", file=stdout)
    return 0


def cmd_validate_learning(args, stdout):
    project = Path(args.project).resolve()
    path = Path(args.path)
    if not path.is_absolute():
        path = project / path
    errors = validate_learning_file(path, load_schema("compound-learning"), validate_schema)
    if errors:
        print(f"FAIL learning {path}", file=stdout)
        for error in errors:
            print(f"- {error}", file=stdout)
        return 1
    print(f"PASS learning {path}", file=stdout)
    return 0
