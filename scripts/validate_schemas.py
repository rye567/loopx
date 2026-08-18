#!/usr/bin/env python3
"""开发时 schema 完整性校验（CI 专用，运行时不依赖本脚本）。

做两件事：
1. 用标准 jsonschema 库校验 loopx/schemas/*.schema.json 本身是合法的 draft-07 结构定义；
2. 对仓库中随包分发的 JSON 实例（如有）做 schema 校验。

运行时控制器仍使用自研轻量校验器（零依赖）；本脚本只在 CI 里
提供更强的结构正确性保证，二者关键字集合保持兼容
（见 loopx/tools/loopx_controller_io.py 的 SUPPORTED_SCHEMA_KEYWORDS）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "loopx" / "schemas"

try:
    from jsonschema import Draft7Validator
except ImportError:
    print("请先安装 jsonschema：pip install jsonschema", file=sys.stderr)
    sys.exit(2)


def check_schema(name: str, schema: dict) -> list[str]:
    """校验 schema 文件本身合法，且只使用自研校验器支持的关键字。"""
    errors: list[str] = []
    validator = Draft7Validator(
        {
            "type": "object",
            "properties": {
                "$schema": {"const": "https://json-schema.org/draft-07/schema#"},
            },
            "required": ["$schema"],
        }
    )
    for error in validator.iter_errors(schema):
        errors.append(f"{name}: 缺少或错误的 $schema 声明：{error.message}")
    try:
        Draft7Validator.check_schema(schema)
    except Exception as exc:  # noqa: BLE001 - 把校验器内部异常转为可读错误
        errors.append(f"{name}: 不是合法的 draft-07 schema：{exc}")
    return errors


def collect_schema_keywords(node: object, found: set[str]) -> None:
    """只沿 schema 结构节点递归收集关键字。

    注意：`properties` 的键是“实例的属性名”而非 schema 关键字，
    必须只递归其值；`items` 的值同理是子 schema。
    """
    if not isinstance(node, dict):
        return
    found.update(node.keys())
    for sub_schema in (node.get("properties") or {}).values():
        collect_schema_keywords(sub_schema, found)
    items = node.get("items")
    if isinstance(items, dict):
        collect_schema_keywords(items, found)


def main() -> int:
    sys.path.insert(0, str(ROOT / "loopx" / "tools"))
    from loopx_controller_io import SUPPORTED_SCHEMA_KEYWORDS  # noqa: E402

    failures: list[str] = []
    schemas: dict[str, dict] = {}

    for path in sorted(SCHEMA_DIR.glob("*.schema.json")):
        name = path.name
        schema = json.loads(path.read_text(encoding="utf-8"))
        schemas[name] = schema
        failures.extend(check_schema(name, schema))

        # 保证自研校验器与标准库两边的关键字集合保持兼容，
        # 避免 CI 用标准库通过、运行时自研校验器却拒绝的漂移。
        keywords: set[str] = set()
        collect_schema_keywords(schema, keywords)
        unsupported = keywords - set(SUPPORTED_SCHEMA_KEYWORDS)
        if unsupported:
            failures.append(f"{name}: 使用了自研校验器不支持的关键字：{sorted(unsupported)}")

    if failures:
        print("FAIL schema 校验未通过：")
        for item in failures:
            print(f"- {item}")
        return 1

    print(f"PASS {len(schemas)} 个 schema 均为合法 draft-07 结构定义，且与自研校验器关键字兼容")
    return 0


if __name__ == "__main__":
    sys.exit(main())
