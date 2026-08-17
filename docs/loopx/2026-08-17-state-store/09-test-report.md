# 测试报告

## 结论

本地自动测试全部通过，未发现 LoopX 既有流程功能、v1/v2 兼容或新单文件状态后端的回归。

## 数据准备

- 正式验证 run ID：`2026-08-17-state-store`。
- 存储专项测试为每个用例创建唯一临时项目、唯一 run ID 和独立 `LOOPX_STATE_DIR`。
- 完整流程用例创建临时 Git 项目、最小 CI 文件、结构化方案/测试/开发/质量产物和确认凭据。
- 锁、摘要、目录冲突、非法 token、提交失败和清理失败使用局部故障注入，不访问外部系统。

## 执行入口与结果

- `python3 -m unittest tests.test_loopx_store`：26/26 PASS。
- `python3 -m unittest discover -s tests`：143/143 PASS。
- `python3 loopx/tools/loopx_check.py package --root .`：PASS。
- `python3 -m py_compile loopx/tools/*.py tests/test_loopx_store.py`：PASS。
- `git diff --check`：PASS。

## 核心断言

- 新运行项目内不存在 `docs/loopx/runs/<run_id>`，项目流程控制 JSON 数量为 0。
- 用户状态运行目录静稳时只有 `run.json`，无锁、所有权文件或临时文件。
- FULL 17 阶段、确认、返工状态、健康检查、Git 检查、经验记录、严格复核和 close 全部可执行。
- 旧 v1/v2 项目运行继续使用旧目录，不迁移、不删除，也不创建同名用户容器。
- 摘要篡改、路径越界、非法容器、锁竞态和文件系统异常被拒绝；失败提交不替换原容器，不提前输出成功信息。

## 清理动作与验证

- 每个专项测试在 `tearDown` 删除临时项目和状态根，并断言测试根目录不存在。
- 完整流程用例结束时断言项目没有控制 JSON、状态运行目录仅有 `run.json`，随后删除其临时根。
- 故障注入用例断言锁、owner、reclaim、tmp 和已回滚导入文件均不残留。
- 测试结束后无需要人工清理的测试数据；清理验证结果记录在运行产物 `artifacts/test-execution-evidence.json`。

## 未覆盖

- 未执行远端 CI、Windows、网络文件系统和真实多进程压力测试。
- 未执行 commit、push、真实发布或外部系统调用。
