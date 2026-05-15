#!/usr/bin/env python3
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

STAGES = {
    "environment_check",
    "assignment",
    "solution_design",
    "solution_review",
    "test_design",
    "test_review",
    "development",
    "quality_audit",
    "code_review",
    "test_execution",
    "health_gate",
    "final_report",
}
STAGE_STATUSES = {"PASS", "CHANGES_REQUIRED", "BLOCKED", "SKIPPED", "ACCEPTED_RISK"}

class YamlSubsetError(ValueError):
    pass


def schema_root():
    return Path(__file__).resolve().parents[1] / "schemas"


def load_schema(name):
    path = schema_root() / f"{name}.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def run_root(project):
    return project / ".loopx" / "runs"


def get_run_dir(project, run_id):
    return run_root(project) / run_id


def slugify(text):
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return slug[:48] or "loopx-run"


def default_run_id(requirement):
    return f"{datetime.now().strftime('%Y-%m-%d')}-{slugify(requirement)}"


def yaml_string(value):
    return json.dumps(str(value), ensure_ascii=False)


def render_worklist(run_id, requirement, mode):
    return f"""run:
  id: {yaml_string(run_id)}
  requirement: {yaml_string(requirement)}
  mode: {mode}
  status: ACTIVE
  current_stage: environment_check
  next_action: assignment

items: []
"""


def parse_scalar(text):
    value = text.strip()
    if value in {"", "null", "Null", "NULL", "~"}:
        return None
    if value in {"[]", "[ ]"}:
        return []
    if value in {"{}", "{ }"}:
        return {}
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        return value


def yaml_lines(text):
    lines = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        lines.append((indent, raw.strip()))
    return lines


def split_key_value(text):
    if ":" not in text:
        raise YamlSubsetError(f"expected key/value pair: {text}")
    key, raw_value = text.split(":", 1)
    key = key.strip()
    if not key:
        raise YamlSubsetError(f"empty key in line: {text}")
    return key, raw_value.strip()


def parse_yaml_subset(text):
    lines = yaml_lines(text)
    if not lines:
        return {}
    value, index = parse_block(lines, 0, lines[0][0])
    if index != len(lines):
        raise YamlSubsetError(f"unexpected YAML content near: {lines[index][1]}")
    return value


def parse_block(lines, index, indent):
    if lines[index][1].startswith("- "):
        return parse_list(lines, index, indent)
    return parse_dict(lines, index, indent)


def parse_dict(lines, index, indent):
    data = {}
    while index < len(lines):
        current_indent, stripped = lines[index]
        if current_indent < indent:
            break
        if current_indent > indent:
            raise YamlSubsetError(f"unexpected indentation near: {stripped}")
        if stripped.startswith("- "):
            break
        key, raw_value = split_key_value(stripped)
        index += 1
        if raw_value:
            data[key] = parse_scalar(raw_value)
        elif index < len(lines) and lines[index][0] > current_indent:
            data[key], index = parse_block(lines, index, lines[index][0])
        else:
            data[key] = None
    return data, index


def parse_list(lines, index, indent):
    items = []
    while index < len(lines):
        current_indent, stripped = lines[index]
        if current_indent < indent:
            break
        if current_indent != indent or not stripped.startswith("- "):
            break
        rest = stripped[2:].strip()
        index += 1
        if not rest:
            if index < len(lines) and lines[index][0] > current_indent:
                item, index = parse_block(lines, index, lines[index][0])
            else:
                item = None
        elif ":" in rest:
            key, raw_value = split_key_value(rest)
            if raw_value:
                item = {key: parse_scalar(raw_value)}
            elif index < len(lines) and lines[index][0] > current_indent:
                item = {}
                item[key], index = parse_block(lines, index, lines[index][0])
            else:
                item = {key: None}
            if index < len(lines) and lines[index][0] > current_indent:
                extra, index = parse_block(lines, index, lines[index][0])
                if not isinstance(extra, dict):
                    raise YamlSubsetError(f"expected mapping after list item: {rest}")
                item.update(extra)
        else:
            item = parse_scalar(rest)
        items.append(item)
    return items, index


def path_join(path, key):
    if isinstance(key, int):
        return f"{path}[{key}]" if path else f"[{key}]"
    return f"{path}.{key}" if path else str(key)


def type_matches(value, expected):
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def validate_schema(value, schema, path=""):
    errors = []
    expected = schema.get("type")
    if expected and not type_matches(value, expected):
        errors.append(f"{path or '$'} must be {expected}")
        return errors

    if "enum" in schema and value not in schema["enum"]:
        allowed = ", ".join(str(item) for item in schema["enum"])
        errors.append(f"{path or '$'} must be one of: {allowed}")

    if expected == "object":
        required = schema.get("required", [])
        for key in required:
            if key not in value or value[key] is None:
                errors.append(f"{path_join(path, key)} is required")
        properties = schema.get("properties", {})
        for key, child_schema in properties.items():
            if key in value and value[key] is not None:
                errors.extend(validate_schema(value[key], child_schema, path_join(path, key)))

    if expected == "array" and "items" in schema:
        for index, item in enumerate(value):
            errors.extend(validate_schema(item, schema["items"], path_join(path, index)))

    return errors


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"{path} does not exist")
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc


def latest_run_id(project):
    root = run_root(project)
    if not root.exists():
        return None
    runs = [path for path in root.iterdir() if path.is_dir()]
    if not runs:
        return None
    return max(runs, key=lambda path: path.stat().st_mtime).name


def resolve_run_id(project, run_id):
    if run_id:
        return run_id
    resolved = latest_run_id(project)
    if not resolved:
        raise ValueError("no LoopX runs found")
    return resolved


def validate_run(project, run_id):
    errors = []
    directory = get_run_dir(project, run_id)
    state_path = directory / "state.json"
    try:
        state = read_json(state_path)
    except ValueError as exc:
        return [str(exc)]

    errors.extend(validate_schema(state, load_schema("state")))
    if state.get("run_id") != run_id:
        errors.append("state.run_id must match selected run")
    if state.get("current_stage") and state["current_stage"] not in STAGES:
        errors.append("current_stage is not a known LoopX stage")
    for stage, status in state.get("stages", {}).items():
        if stage not in STAGES:
            errors.append(f"stages.{stage} is not a known LoopX stage")
        if status not in STAGE_STATUSES:
            errors.append(f"stages.{stage} has invalid status {status}")

    worklist_rel = state.get("worklist") or f".loopx/runs/{run_id}/worklist.yml"
    worklist_path = Path(worklist_rel)
    if not worklist_path.is_absolute():
        worklist_path = project / worklist_path
    try:
        worklist = parse_yaml_subset(worklist_path.read_text(encoding="utf-8"))
        errors.extend(validate_schema(worklist, load_schema("worklist")))
    except FileNotFoundError:
        errors.append(f"{worklist_path} does not exist")
    except YamlSubsetError as exc:
        errors.append(f"{worklist_path} is not valid LoopX YAML: {exc}")

    stage_result_root = directory / "stage-results"
    if stage_result_root.exists():
        for result_path in sorted(stage_result_root.glob("*.json")):
            try:
                result = read_json(result_path)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            errors.extend(validate_schema(result, load_schema("stage-result"), result_path.name))
    return errors


def cmd_init(args, stdout):
    project = Path(args.project).resolve()
    run_id = args.run_id or default_run_id(args.requirement)
    directory = get_run_dir(project, run_id)
    if directory.exists():
        print(f"run already exists: {run_id}", file=stdout)
        return 1
    directory.mkdir(parents=True)
    (directory / "stage-results").mkdir()

    state = {
        "run_id": run_id,
        "requirement": args.requirement,
        "mode": args.mode,
        "status": "ACTIVE",
        "current_stage": "environment_check",
        "confirmation_policy": "verification_gated",
        "max_auto_repair": 2,
        "worklist": f".loopx/runs/{run_id}/worklist.yml",
        "events": f".loopx/runs/{run_id}/events.jsonl",
        "stages": {},
    }
    (directory / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (directory / "worklist.yml").write_text(render_worklist(run_id, args.requirement, args.mode), encoding="utf-8")
    event = {"type": "run_created", "run_id": run_id, "current_stage": "environment_check"}
    (directory / "events.jsonl").write_text(json.dumps(event, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"created run {run_id}", file=stdout)
    print(f"state: {state['worklist'].rsplit('/', 1)[0]}/state.json", file=stdout)
    return 0


def cmd_status(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        state = read_json(get_run_dir(project, run_id) / "state.json")
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    print(f"run_id: {state.get('run_id')}", file=stdout)
    print(f"mode: {state.get('mode')}", file=stdout)
    print(f"status: {state.get('status')}", file=stdout)
    print(f"current_stage: {state.get('current_stage')}", file=stdout)
    print(f"next_action: {state.get('next_action', 'validate')}", file=stdout)
    return 0


def cmd_validate(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    errors = validate_run(project, run_id)
    if errors:
        print(f"FAIL {run_id}", file=stdout)
        for error in errors:
            print(f"- {error}", file=stdout)
        return 1
    print(f"PASS {run_id}", file=stdout)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="LoopX state controller.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="Create a local LoopX run state.")
    init.add_argument("requirement")
    init.add_argument("--run-id")
    init.add_argument("--mode", choices=["LIGHT", "STANDARD", "FULL"], default="STANDARD")
    init.add_argument("--project", default=".")
    init.set_defaults(func=cmd_init)

    status = subparsers.add_parser("status", help="Show a LoopX run status.")
    status.add_argument("run_id", nargs="?")
    status.add_argument("--project", default=".")
    status.set_defaults(func=cmd_status)

    validate = subparsers.add_parser("validate", help="Validate LoopX run state and worklist.")
    validate.add_argument("run_id", nargs="?")
    validate.add_argument("--project", default=".")
    validate.set_defaults(func=cmd_validate)
    return parser


def main(argv=None, stdout=None):
    stdout = stdout or sys.stdout
    args = build_parser().parse_args(argv)
    return args.func(args, stdout)


if __name__ == "__main__":
    sys.exit(main())
