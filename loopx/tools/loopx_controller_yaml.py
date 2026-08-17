"""Small YAML subset helpers for LoopX worklist files."""

import json
import re


class YamlSubsetError(ValueError):
    pass


def yaml_string(value):
    return json.dumps(str(value), ensure_ascii=False)


def render_yaml_value(value):
    if isinstance(value, list):
        if not value:
            return "[]"
        return "[" + ", ".join(yaml_string(item) for item in value) + "]"
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return '""'
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.-]+", value):
        return value
    return yaml_string(value)


def dump_worklist(worklist):
    list_defaults = {"risk_tags", "read_scope", "write_scope", "dependencies", "validation", "evidence", "required_changes"}
    lines = [
        "run:",
    ]
    for key in ("id", "requirement", "mode", "status", "current_stage", "next_action"):
        if key in worklist.get("run", {}):
            lines.append(f"  {key}: {render_yaml_value(worklist['run'][key])}")
    for section in ("spec", "interview"):
        if section in worklist:
            lines.append(f"{section}:")
            for key, value in worklist[section].items():
                lines.append(f"  {key}: {render_yaml_value(value)}")
    if "stages" in worklist:
        lines.append("stages:")
        for stage in worklist.get("stages") or []:
            lines.append(f"  - id: {render_yaml_value(stage.get('id', ''))}")
            for key in ("stage", "name", "status", "required", "evidence"):
                lines.append(f"    {key}: {render_yaml_value(stage.get(key, ''))}")
    items = worklist.get("items") or []
    if not items:
        lines.append("items: []")
    else:
        lines.append("items:")
        for item in items:
            lines.append(f"  - id: {render_yaml_value(item.get('id', ''))}")
            for key in (
                "title",
                "status",
                "risk_tags",
                "owner_agent",
                "read_scope",
                "write_scope",
                "dependencies",
                "validation",
                "evidence",
                "failed_by",
                "return_to",
                "required_changes",
            ):
                default = [] if key in list_defaults else ""
                lines.append(f"    {key}: {render_yaml_value(item.get(key, default))}")
    return "\n".join(lines) + "\n"


def parse_scalar(text):
    value = text.strip()
    if value in {"", "null", "Null", "NULL", "~"}:
        return None
    if value in {"[]", "[ ]"}:
        return []
    if value in {"{}", "{ }"}:
        return {}
    if value.startswith("[") and value.endswith("]"):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise YamlSubsetError(f"invalid inline array: {value}") from exc
        if not isinstance(parsed, list):
            raise YamlSubsetError(f"expected inline array: {value}")
        return parsed
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
        if key in data:
            raise YamlSubsetError(f"duplicate key: {key}")
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
                duplicates = sorted(set(item).intersection(extra))
                if duplicates:
                    raise YamlSubsetError(f"duplicate key in list item: {', '.join(duplicates)}")
                item.update(extra)
        else:
            item = parse_scalar(rest)
        items.append(item)
    return items, index
