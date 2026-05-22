#!/usr/bin/env python3
"""File, schema and path helpers for the LoopX controller."""

import json
from datetime import datetime
from pathlib import Path

from loopx_controller_yaml import parse_yaml_subset


def schema_root():
    return Path(__file__).resolve().parents[1] / "schemas"


def loopx_root():
    return Path(__file__).resolve().parents[1]


def load_schema(name):
    path = schema_root() / f"{name}.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def run_root(project):
    return project / ".loopx" / "runs"


def get_run_dir(project, run_id):
    return run_root(project) / run_id


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


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_event(directory, event):
    event = {"time": datetime.now().isoformat(timespec="seconds"), **event}
    with (directory / "events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def load_state(project, run_id):
    return read_json(get_run_dir(project, run_id) / "state.json")


def save_state(project, run_id, state):
    write_json(get_run_dir(project, run_id) / "state.json", state)


def load_worklist(project, state):
    worklist_path = Path(state.get("worklist") or "")
    if not worklist_path.is_absolute():
        worklist_path = project / worklist_path
    return worklist_path, parse_yaml_subset(worklist_path.read_text(encoding="utf-8"))


def project_path(project, path):
    resolved = Path(path or "")
    if not resolved.is_absolute():
        resolved = project / resolved
    return resolved
