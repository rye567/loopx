#!/usr/bin/env python3
"""LoopX 控制器的文件、结构定义和路径辅助函数。"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from loopx_controller_store import active_run_dir, resolve_runtime_path
from loopx_controller_yaml import parse_yaml_subset


SUPPORTED_SCHEMA_KEYWORDS = {
    "type",
    "enum",
    "required",
    "properties",
    "items",
    "minItems",
    "minLength",
    "additionalProperties",
    "title",
    "description",
}


def schema_root():
    return Path(__file__).resolve().parents[1] / "schemas"


def loopx_root():
    return Path(__file__).resolve().parents[1]


def load_schema(name):
    path = schema_root() / f"{name}.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def run_root(project):
    return project / "docs" / "loopx" / "runs"


def get_run_dir(project, run_id):
    active = active_run_dir(project, run_id)
    return active if active is not None else run_root(project) / run_id


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
    unsupported = sorted(set(schema) - SUPPORTED_SCHEMA_KEYWORDS)
    if unsupported:
        errors.append(f"{path or '$'} 的结构定义包含不支持的关键字：{', '.join(unsupported)}")
        return errors
    expected = schema.get("type")
    if expected and not type_matches(value, expected):
        errors.append(f"{path or '$'} 必须是 {expected}")
        return errors

    if "enum" in schema and value not in schema["enum"]:
        allowed = ", ".join(str(item) for item in schema["enum"])
        errors.append(f"{path or '$'} 必须是以下值之一：{allowed}")

    if expected == "string" and "minLength" in schema and len(value) < int(schema["minLength"]):
        errors.append(f"{path or '$'} 长度必须大于或等于 {schema['minLength']}")

    if expected == "object":
        required = schema.get("required", [])
        for key in required:
            if key not in value or value[key] is None:
                errors.append(f"{path_join(path, key)} 为必填项")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(f"{path_join(path, key)} 不允许出现")
        for key, child_schema in properties.items():
            if key in value and value[key] is not None:
                errors.extend(validate_schema(value[key], child_schema, path_join(path, key)))

    if expected == "array":
        if "minItems" in schema and len(value) < int(schema["minItems"]):
            errors.append(f"{path or '$'} 至少需要 {schema['minItems']} 项")
        if "items" in schema:
            for index, item in enumerate(value):
                errors.extend(validate_schema(item, schema["items"], path_join(path, index)))

    return errors


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"文件不存在：{path}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"文件不是有效 JSON：{path}：{exc}") from exc


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def json_text(data):
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def event_line(event):
    payload = {"time": datetime.now().isoformat(timespec="seconds"), **event}
    return json.dumps(payload, ensure_ascii=False) + "\n"


def atomic_write_texts(files):
    """先准备全部内容；替换失败时恢复已更新目标，避免留下半更新状态。"""

    temporary = []
    backups = {}
    replaced = []
    try:
        for raw_path, content in files.items():
            path = Path(raw_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            backup_path = None
            if path.exists():
                backup = tempfile.NamedTemporaryFile(
                    mode="wb",
                    dir=path.parent,
                    prefix=f".{path.name}.",
                    suffix=".bak",
                    delete=False,
                )
                try:
                    backup.write(path.read_bytes())
                    backup.flush()
                    os.fsync(backup.fileno())
                finally:
                    backup.close()
                backup_path = Path(backup.name)
                os.chmod(backup_path, path.stat().st_mode & 0o777)
            backups[path] = backup_path
            handle = tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            )
            try:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            finally:
                handle.close()
            temporary.append((Path(handle.name), path))
        try:
            for source, target in temporary:
                source.replace(target)
                replaced.append(target)
        except Exception as exc:
            rollback_errors = []
            for target in reversed(replaced):
                backup_path = backups.get(target)
                try:
                    if backup_path is None:
                        target.unlink(missing_ok=True)
                    else:
                        os.replace(backup_path, target)
                except OSError as rollback_exc:
                    rollback_errors.append(f"{target}：{rollback_exc}")
            if rollback_errors:
                raise RuntimeError("多文件写入失败且无法完整恢复：" + "；".join(rollback_errors)) from exc
            raise
    finally:
        for source, _ in temporary:
            try:
                source.unlink()
            except FileNotFoundError:
                pass
        for backup_path in backups.values():
            if backup_path is None:
                continue
            try:
                backup_path.unlink()
            except FileNotFoundError:
                pass


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
        worklist_path = project_path(project, worklist_path)
    return worklist_path, parse_yaml_subset(worklist_path.read_text(encoding="utf-8"))


def project_path(project, path):
    return resolve_runtime_path(project, path or "")
