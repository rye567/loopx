#!/usr/bin/env python3
"""发布 tag 与 manifest 版本一致性检查（CI 专用）。

规则：
- 非 tag 触发（普通 push / PR）：跳过检查，直接 PASS。
- tag 触发（refs/tags/vX.Y.Z[.后缀]）：tag 中的版本必须与根目录
  ``manifest.json`` 和 ``loopx/manifest.json`` 的 ``version`` 完全一致，
  且两个 manifest 之间也一致；否则 FAIL，防止发错版本进插件市场。
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 允许 v0.1.1、v0.1.1-beta.1、v0.1.1.rc1 等形式；主版本部分必须是三段数字。
_TAG_PATTERN = re.compile(r"^refs/tags/v(\d+\.\d+\.\d+(?:[-.][\w.]+)?)$")


def manifest_version(path: Path) -> str:
    """读取单个 manifest 的 version 字段；缺失或非法时返回占位描述。"""

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"<无法读取：{exc.__class__.__name__}>"
    value = data.get("version") if isinstance(data, dict) else None
    return value if isinstance(value, str) and value else "<缺失或非字符串>"


def check_release(ref: str, root: Path) -> tuple[bool, list[str]]:
    """校验 tag 与 manifest 版本；返回 (是否通过, 消息列表)。"""

    match = _TAG_PATTERN.match(ref)
    if not match:
        return True, [f"SKIP 非 tag 触发（GITHUB_REF={ref or '未设置'}），跳过 tag 一致性检查"]
    tag_version = match.group(1)
    root_version = manifest_version(root / "manifest.json")
    loopx_version = manifest_version(root / "loopx" / "manifest.json")

    problems = []
    if root_version != tag_version:
        problems.append(f"manifest.json version={root_version} 与 tag v{tag_version} 不一致")
    if loopx_version != tag_version:
        problems.append(f"loopx/manifest.json version={loopx_version} 与 tag v{tag_version} 不一致")
    if root_version != loopx_version:
        problems.append(f"两个 manifest 版本不一致：{root_version} != {loopx_version}")
    if problems:
        return False, problems
    return True, [f"PASS tag v{tag_version} 与两个 manifest 版本一致"]


def main() -> int:
    ok, messages = check_release(os.environ.get("GITHUB_REF", ""), ROOT)
    for message in messages:
        print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
