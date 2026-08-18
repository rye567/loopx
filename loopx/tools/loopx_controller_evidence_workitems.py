#!/usr/bin/env python3
"""LoopX v2 方案工作项（work items）校验与运行态转换。"""

from __future__ import annotations


WORK_ITEM_INPUT_FIELDS = {
    "id",
    "title",
    "owner_agent",
    "risk_tags",
    "read_scope",
    "write_scope",
    "dependencies",
    "validation",
}
WORK_ITEM_LIST_FIELDS = {"risk_tags", "read_scope", "write_scope", "dependencies", "validation"}


def validate_work_items(items):
    errors = []
    if not isinstance(items, list):
        return ["solution.work_items 必须是数组"]
    by_id = {}
    for index, item in enumerate(items):
        path = f"solution.work_items[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{path} 必须是对象")
            continue
        unknown = set(item) - WORK_ITEM_INPUT_FIELDS
        if unknown:
            errors.append(f"{path} 包含不允许的运行态或未知字段：{', '.join(sorted(unknown))}")
        for field in WORK_ITEM_INPUT_FIELDS:
            if field not in item:
                errors.append(f"{path}.{field} 缺失")
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id.strip():
            errors.append(f"{path}.id 必须是非空字符串")
        elif item_id in by_id:
            errors.append(f"{path}.id 重复：{item_id}")
        else:
            by_id[item_id] = item
        for field in WORK_ITEM_LIST_FIELDS:
            value = item.get(field)
            if not isinstance(value, list) or any(not isinstance(entry, str) or not entry for entry in value):
                errors.append(f"{path}.{field} 必须是字符串数组")
        for field in ("title", "owner_agent"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                errors.append(f"{path}.{field} 必须是非空字符串")
    known = set(by_id)
    for item_id, item in by_id.items():
        for dependency in item.get("dependencies") or []:
            if dependency not in known:
                errors.append(f"工作项 {item_id} 引用了未知依赖：{dependency}")
            if dependency == item_id:
                errors.append(f"工作项 {item_id} 不能依赖自身")

    visiting = set()
    visited = set()

    def visit(item_id):
        if item_id in visiting:
            errors.append(f"工作项依赖存在环：{item_id}")
            return
        if item_id in visited or item_id not in by_id:
            return
        visiting.add(item_id)
        for dependency in by_id[item_id].get("dependencies") or []:
            visit(dependency)
        visiting.remove(item_id)
        visited.add(item_id)

    for item_id in by_id:
        visit(item_id)
    return errors


def runtime_work_items(items):
    errors = validate_work_items(items)
    if errors:
        raise ValueError("方案工作项校验失败：\n- " + "\n- ".join(errors))
    return [
        {
            **item,
            "status": "pending",
            "evidence": [],
            "failed_by": "",
            "return_to": "",
            "required_changes": [],
        }
        for item in items
    ]


def known_work_item_ids(worklist):
    return {item.get("id") for item in (worklist.get("items") or []) if isinstance(item, dict) and item.get("id")}


def validate_work_item_references(worklist, item_ids, extra_ids=None):
    known = known_work_item_ids(worklist).union(extra_ids or set())
    unknown = sorted({item_id for item_id in (item_ids or []) if item_id not in known})
    if unknown:
        raise ValueError(f"工作项引用不存在：{', '.join(unknown)}")
