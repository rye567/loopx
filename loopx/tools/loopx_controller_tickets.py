#!/usr/bin/env python3
"""Repair ticket storage helpers for LoopX controller runs.

返工票据是阶段回退的证据，不在这里决定流程；这里只处理读写路径，
流程判断由 loopx_controller_flow.py 和 loopx_controller_repair.py 负责。
"""

from pathlib import Path

from loopx_controller_io import load_state, project_path, read_json, write_json


def repair_ticket_root(project, run_id, state=None):
    state = state or load_state(project, run_id)
    path = Path(state.get("repair_tickets") or f"docs/loopx/runs/{run_id}/artifacts/repair-tickets")
    if not path.is_absolute():
        path = project_path(project, path)
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
