#!/usr/bin/env python3
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

STAGE_SEQUENCE = [
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
]
STAGES = set(STAGE_SEQUENCE)
STAGE_STATUSES = {"PASS", "CHANGES_REQUIRED", "BLOCKED", "SKIPPED", "ACCEPTED_RISK"}
PASSING_STATUSES = {"PASS", "ACCEPTED_RISK"}
STAGE_RESULT_FILES = {
    "environment_check": "01-environment-check.json",
    "assignment": "02-assignment.json",
    "solution_design": "03-solution-design.json",
    "solution_review": "04-solution-review.json",
    "test_design": "05-test-design.json",
    "test_review": "06-test-review.json",
    "development": "07-development.json",
    "quality_audit": "08-quality-audit.json",
    "code_review": "09-code-review.json",
    "test_execution": "10-test-execution.json",
    "health_gate": "11-health-gate.json",
    "final_report": "12-final-report.json",
}
DEFAULT_STAGE_OWNERS = {
    "environment_check": "environment-check-agent",
    "assignment": "project-manager",
    "solution_design": "solution-designer",
    "solution_review": "solution-reviewer",
    "test_design": "test-designer",
    "test_review": "test-reviewer",
    "development": "development",
    "quality_audit": "quality-auditor",
    "code_review": "code-reviewer",
    "test_execution": "test-runner",
    "health_gate": "quality-auditor",
    "final_report": "release-manager",
}

class YamlSubsetError(ValueError):
    pass


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


def render_yaml_value(value):
    if isinstance(value, list):
        if not value:
            return "[]"
        return "[" + ", ".join(yaml_string(item) for item in value) + "]"
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
    lines.append("items:")
    for item in worklist.get("items") or []:
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


def stage_index(stage):
    return STAGE_SEQUENCE.index(stage)


def stages_before(stage):
    return STAGE_SEQUENCE[:stage_index(stage)]


def first_changes_required(stages):
    for stage in STAGE_SEQUENCE:
        if stages.get(stage) in {"CHANGES_REQUIRED", "BLOCKED"}:
            return stage
    return None


def risk_config():
    return parse_yaml_subset((loopx_root() / "risk.yml").read_text(encoding="utf-8"))


def resolve_mode(mode, risk_tags):
    if mode != "auto":
        return mode
    config = risk_config()
    critical = set(config.get("critical_triggers", []))
    score_rules = config.get("score_rules", {})
    thresholds = config.get("thresholds", {})
    if critical.intersection(risk_tags):
        return "FULL"
    score = sum(int(score_rules.get(tag, 0)) for tag in risk_tags)
    if score >= int(thresholds.get("full_min", 6)):
        return "FULL"
    if score <= int(thresholds.get("light_max", 1)):
        return "LIGHT"
    return "STANDARD"


def default_next_stage(stage):
    index = stage_index(stage)
    if index + 1 >= len(STAGE_SEQUENCE):
        return "final_report"
    return STAGE_SEQUENCE[index + 1]


def stage_result_path(directory, stage):
    return directory / "stage-results" / STAGE_RESULT_FILES[stage]


def repair_ticket_root(project, run_id, state=None):
    state = state or load_state(project, run_id)
    path = Path(state.get("repair_tickets") or f".loopx/runs/{run_id}/repair-tickets")
    if not path.is_absolute():
        path = project / path
    return path


def repair_ticket_path(project, run_id, item_id, state=None):
    return repair_ticket_root(project, run_id, state) / f"{item_id}.json"


def read_repair_ticket(project, run_id, item_id, state=None):
    return read_json(repair_ticket_path(project, run_id, item_id, state))


def write_repair_ticket(project, run_id, item_id, ticket, state=None):
    root = repair_ticket_root(project, run_id, state)
    root.mkdir(parents=True, exist_ok=True)
    write_json(root / f"{item_id}.json", ticket)


def iter_repair_tickets(project, run_id, state=None):
    root = repair_ticket_root(project, run_id, state)
    if not root.exists():
        return []
    tickets = []
    for path in sorted(root.glob("*.json")):
        try:
            tickets.append(read_json(path))
        except ValueError:
            continue
    return tickets


def open_repair_tickets_for_stage(project, run_id, stage, state=None):
    return [
        ticket for ticket in iter_repair_tickets(project, run_id, state)
        if ticket.get("status") == "OPEN" and ticket.get("return_to") == stage
    ]


def record_stage_result(project, run_id, stage, status, evidence, return_to="", next_action=None, affected_work_items=None, blocked_reason=""):
    directory = get_run_dir(project, run_id)
    state = load_state(project, run_id)
    result = {
        "stage": stage,
        "status": status,
        "return_to": return_to,
        "next_action": next_action or (return_to if status == "CHANGES_REQUIRED" else default_next_stage(stage)),
        "affected_work_items": affected_work_items or [],
        "evidence": evidence,
        "user_confirmation_required": status in {"CHANGES_REQUIRED", "BLOCKED"},
        "blocked_reason": blocked_reason,
    }
    write_json(stage_result_path(directory, stage), result)
    state.setdefault("stages", {})[stage] = status
    state["active_agent"] = state.get("stage_owners", DEFAULT_STAGE_OWNERS).get(stage, stage)
    if status == "CHANGES_REQUIRED":
        target = return_to or stage
        state["current_stage"] = target
        state["active_agent"] = state.get("stage_owners", DEFAULT_STAGE_OWNERS).get(target, target)
        state["next_action"] = f"repair_{target}"
        for later_stage in STAGE_SEQUENCE[stage_index(target) + 1:]:
            if later_stage != stage:
                state["stages"].pop(later_stage, None)
    save_state(project, run_id, state)
    append_event(directory, {
        "type": "stage_recorded",
        "stage": stage,
        "status": status,
        "return_to": return_to,
    })
    return result


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
    risk_tags = args.risk_tags or []
    mode = resolve_mode(args.mode, risk_tags)
    directory = get_run_dir(project, run_id)
    if directory.exists():
        print(f"run already exists: {run_id}", file=stdout)
        return 1
    directory.mkdir(parents=True)
    (directory / "stage-results").mkdir()
    (directory / "repair-tickets").mkdir()

    state = {
        "run_id": run_id,
        "requirement": args.requirement,
        "mode": mode,
        "status": "ACTIVE",
        "current_stage": "environment_check",
        "next_action": "assignment",
        "active_agent": DEFAULT_STAGE_OWNERS["environment_check"],
        "stage_owners": DEFAULT_STAGE_OWNERS,
        "risk_tags": risk_tags,
        "confirmation_policy": "verification_gated",
        "max_auto_repair": 2,
        "worklist": f".loopx/runs/{run_id}/worklist.yml",
        "events": f".loopx/runs/{run_id}/events.jsonl",
        "repair_tickets": f".loopx/runs/{run_id}/repair-tickets",
        "loop_attempts": {},
        "stages": {},
    }
    write_json(directory / "state.json", state)
    (directory / "worklist.yml").write_text(render_worklist(run_id, args.requirement, mode), encoding="utf-8")
    event = {"type": "run_created", "run_id": run_id, "current_stage": "environment_check"}
    (directory / "events.jsonl").write_text(json.dumps(event, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"created run {run_id}", file=stdout)
    print(f"mode: {mode}", file=stdout)
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


def cmd_record_stage(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        result = record_stage_result(
            project,
            run_id,
            args.stage,
            args.status,
            args.evidence,
            return_to=args.return_to or "",
            next_action=args.next_action,
            affected_work_items=args.item or [],
            blocked_reason=args.blocked_reason or "",
        )
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    print(f"{result['status']} {result['stage']}", file=stdout)
    print(f"next_action: {result['next_action']}", file=stdout)
    return 0


def advance_blockers(project, run_id, state, target_stage):
    blockers = []
    stages = state.get("stages", {})
    for ticket in iter_repair_tickets(project, run_id, state):
        return_to = ticket.get("return_to")
        if ticket.get("status") == "OPEN" and return_to in STAGES and stage_index(return_to) < stage_index(target_stage):
            blockers.append(f"repair ticket {ticket.get('item')} must be CLOSED before {target_stage}")
    changed = first_changes_required(stages)
    if changed:
        blockers.append(f"{changed} is {stages[changed]}; return before advancing")
    for stage in stages_before(target_stage):
        if stages.get(stage) not in PASSING_STATUSES:
            blockers.append(f"{stage} must be PASS before {target_stage}")
    if target_stage == "development" and stages.get("solution_review") not in PASSING_STATUSES:
        blockers.append("solution_review must be PASS before development")
    return blockers


def cmd_advance(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        state = load_state(project, run_id)
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    blockers = advance_blockers(project, run_id, state, args.to)
    if blockers:
        print("FAIL advance blocked", file=stdout)
        for blocker in blockers:
            print(f"- {blocker}", file=stdout)
        return 1
    state["current_stage"] = args.to
    state["active_agent"] = state.get("stage_owners", DEFAULT_STAGE_OWNERS).get(args.to, args.to)
    state["next_action"] = default_next_stage(args.to)
    save_state(project, run_id, state)
    append_event(get_run_dir(project, run_id), {"type": "advanced", "to": args.to})
    print(f"PASS advanced to {args.to}", file=stdout)
    return 0


def business_write_blockers(state):
    blockers = []
    if state.get("current_stage") != "development":
        blockers.append("current_stage must be development")
    if state.get("stages", {}).get("solution_review") not in PASSING_STATUSES:
        blockers.append("solution_review must be PASS before business writes")
    changed = first_changes_required(state.get("stages", {}))
    if changed:
        blockers.append(f"{changed} is {state['stages'][changed]}")
    return blockers


def cmd_can_write(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        state = load_state(project, run_id)
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    if args.kind == "loopx":
        print("PASS loopx writes allowed", file=stdout)
        return 0
    blockers = business_write_blockers(state)
    if blockers:
        print("FAIL business writes locked", file=stdout)
        for blocker in blockers:
            print(f"- {blocker}", file=stdout)
        return 1
    print("PASS business writes unlocked", file=stdout)
    return 0


def update_worklist_feedback(project, state, item_id, return_to, reason):
    try:
        worklist_path, worklist = load_worklist(project, state)
    except (FileNotFoundError, YamlSubsetError):
        return
    for item in worklist.get("items") or []:
        if item.get("id") == item_id:
            item["status"] = "CHANGES_REQUIRED"
            item["failed_by"] = "user_feedback"
            item["return_to"] = return_to
            changes = item.get("required_changes") or []
            if reason not in changes:
                changes.append(reason)
            item["required_changes"] = changes
    worklist["run"]["current_stage"] = return_to
    worklist_path.write_text(dump_worklist(worklist), encoding="utf-8")


def fail_review(project, run_id, from_stage, return_to, item_id, reasons):
    state = load_state(project, run_id)
    owner = state.get("stage_owners", DEFAULT_STAGE_OWNERS).get(return_to, return_to)
    attempts = state.setdefault("loop_attempts", {})
    attempt = int(attempts.get(item_id, 0)) + 1
    attempts[item_id] = attempt
    ticket = {
        "type": "review_failed",
        "item": item_id,
        "from_stage": from_stage,
        "return_to": return_to,
        "assigned_to": owner,
        "attempt": attempt,
        "status": "OPEN",
        "required_changes": reasons,
        "artifact": "",
        "revision": 0,
        "changes_from_review": [],
    }
    state["current_stage"] = return_to
    state["next_action"] = f"repair_{return_to}"
    state["active_agent"] = owner
    state.setdefault("stages", {})[from_stage] = "CHANGES_REQUIRED"
    for later_stage in STAGE_SEQUENCE[stage_index(return_to) + 1:]:
        if later_stage != from_stage:
            state["stages"].pop(later_stage, None)
    save_state(project, run_id, state)
    write_repair_ticket(project, run_id, item_id, ticket, state)
    for reason in reasons:
        update_worklist_feedback(project, state, item_id, return_to, reason)
    record_stage_result(
        project,
        run_id,
        from_stage,
        "CHANGES_REQUIRED",
        reasons,
        return_to=return_to,
        next_action=f"repair_{return_to}",
        affected_work_items=[item_id],
    )
    return ticket


def cmd_fail_review(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        ticket = fail_review(project, run_id, args.from_stage, args.return_to, args.item, args.reason)
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    print(f"CHANGES_REQUIRED {args.from_stage}", file=stdout)
    print(f"repair_ticket: {ticket['item']}", file=stdout)
    print(f"return_to: {ticket['return_to']}", file=stdout)
    print(f"assigned_to: {ticket['assigned_to']}", file=stdout)
    print(f"attempt: {ticket['attempt']}", file=stdout)
    return 0


def cmd_review_feedback(args, stdout):
    args.from_stage = "solution_review"
    args.reason = [args.reason]
    return cmd_fail_review(args, stdout)


def cmd_claim_stage(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        state = load_state(project, run_id)
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    if state.get("current_stage") != args.stage:
        print(f"FAIL current_stage is {state.get('current_stage')}", file=stdout)
        return 1
    owner = state.get("stage_owners", DEFAULT_STAGE_OWNERS).get(args.stage, args.stage)
    state["active_agent"] = owner
    save_state(project, run_id, state)
    print(f"PASS claimed {args.stage}", file=stdout)
    print(f"assigned_to: {owner}", file=stdout)
    for ticket in open_repair_tickets_for_stage(project, run_id, args.stage, state):
        print(f"repair_ticket: {ticket.get('item')}", file=stdout)
        print(f"attempt: {ticket.get('attempt')}", file=stdout)
        for change in ticket.get("required_changes", []):
            print(f"required_change: {change}", file=stdout)
    return 0


def cmd_close_repair(args, stdout):
    project = Path(args.project).resolve()
    try:
        run_id = resolve_run_id(project, args.run_id)
        state = load_state(project, run_id)
        ticket = read_repair_ticket(project, run_id, args.item, state)
    except ValueError as exc:
        print(str(exc), file=stdout)
        return 1
    if args.revision < 2:
        print("FAIL repair revision must be >= 2", file=stdout)
        return 1
    ticket["status"] = "CLOSED"
    ticket["artifact"] = args.artifact
    ticket["revision"] = args.revision
    ticket["changes_from_review"] = args.change
    write_repair_ticket(project, run_id, args.item, ticket, state)
    from_stage = ticket.get("from_stage")
    if from_stage:
        state.setdefault("stages", {}).pop(from_stage, None)
    save_state(project, run_id, state)
    print(f"PASS repair closed {args.item}", file=stdout)
    print(f"artifact: {args.artifact}", file=stdout)
    print(f"revision: {args.revision}", file=stdout)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="LoopX state controller.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="Create a local LoopX run state.")
    init.add_argument("requirement")
    init.add_argument("--run-id")
    init.add_argument("--mode", choices=["auto", "LIGHT", "STANDARD", "FULL"], default="auto")
    init.add_argument("--risk-tags", nargs="*", default=[])
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

    record = subparsers.add_parser("record-stage", help="Record a machine-readable LoopX stage result.")
    record.add_argument("--run-id")
    record.add_argument("--stage", required=True, choices=STAGE_SEQUENCE)
    record.add_argument("--status", required=True, choices=sorted(STAGE_STATUSES))
    record.add_argument("--evidence", action="append", default=[])
    record.add_argument("--return-to", choices=STAGE_SEQUENCE)
    record.add_argument("--next-action")
    record.add_argument("--item", action="append")
    record.add_argument("--blocked-reason")
    record.add_argument("--project", default=".")
    record.set_defaults(func=cmd_record_stage)

    advance = subparsers.add_parser("advance", help="Advance only when previous LoopX gates pass.")
    advance.add_argument("--run-id")
    advance.add_argument("--to", required=True, choices=STAGE_SEQUENCE)
    advance.add_argument("--project", default=".")
    advance.set_defaults(func=cmd_advance)

    can_write = subparsers.add_parser("can-write", help="Check whether writes are unlocked.")
    can_write.add_argument("--run-id")
    can_write.add_argument("--kind", choices=["business", "loopx"], default="business")
    can_write.add_argument("--project", default=".")
    can_write.set_defaults(func=cmd_can_write)

    fail_review_parser = subparsers.add_parser("fail-review", help="Create a review-driven repair ticket and return to the owner stage.")
    fail_review_parser.add_argument("--run-id")
    fail_review_parser.add_argument("--from", dest="from_stage", required=True, choices=STAGE_SEQUENCE)
    fail_review_parser.add_argument("--return-to", required=True, choices=STAGE_SEQUENCE)
    fail_review_parser.add_argument("--item", required=True)
    fail_review_parser.add_argument("--reason", action="append", required=True)
    fail_review_parser.add_argument("--project", default=".")
    fail_review_parser.set_defaults(func=cmd_fail_review)

    claim = subparsers.add_parser("claim-stage", help="Claim the current stage and show open repair tickets for its owner role.")
    claim.add_argument("stage", choices=STAGE_SEQUENCE)
    claim.add_argument("--run-id")
    claim.add_argument("--project", default=".")
    claim.set_defaults(func=cmd_claim_stage)

    close = subparsers.add_parser("close-repair", help="Close a repair ticket after updating the original artifact revision.")
    close.add_argument("--run-id")
    close.add_argument("--item", required=True)
    close.add_argument("--artifact", required=True)
    close.add_argument("--revision", required=True, type=int)
    close.add_argument("--change", action="append", required=True)
    close.add_argument("--project", default=".")
    close.set_defaults(func=cmd_close_repair)

    feedback = subparsers.add_parser("review-feedback", help="Record user review feedback and return to a prior stage.")
    feedback.add_argument("--run-id")
    feedback.add_argument("--item", required=True)
    feedback.add_argument("--return-to", required=True, choices=STAGE_SEQUENCE)
    feedback.add_argument("--reason", required=True)
    feedback.add_argument("--project", default=".")
    feedback.set_defaults(func=cmd_review_feedback)
    return parser


def main(argv=None, stdout=None):
    stdout = stdout or sys.stdout
    args = build_parser().parse_args(argv)
    return args.func(args, stdout)


if __name__ == "__main__":
    sys.exit(main())
