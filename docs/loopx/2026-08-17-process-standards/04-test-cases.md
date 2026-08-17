# 04 测试用例设计

## 状态

- 状态：第 2 版，等待独立审核。
- 运行：`2026-08-17-loopx`。
- 执行等级：FULL。
- 依据：已批准规格与方案第 3 版。

## 测试范围

本计划验证工程标准体系的首个兼容版本，覆盖：

- 标准目录、规则检查类型和风险 profile；
- 项目策略、规则快照和来源追踪；
- 阶段专属结构定义及跨字段语义；
- 阶段记录、严格检查、证据路径与失败原子性；
- worklist 同步及工作项引用；
- 健康检查和外部命令执行策略；
- v1/v2 命令兼容与完整流程；
- README、模板、智能体、技能、命令帮助和消息的自然中文；
- 包完整性、manifest 和既有回归测试。

不连接数据库、缓存、消息队列、网络 API、CI 或真实外部扫描工具。

## 测试隔离与数据生命周期

- 每个文件系统测试使用 `tempfile.TemporaryDirectory(prefix="loopx-std-<case>-<uuid>-")` 创建独立项目根。
- 每个控制器运行使用唯一 ID：`loopx-std-<case>-<uuid>`。
- 正例与反例目录、规则、策略、产物和证据均由测试夹具在临时项目内创建。
- 符号链接用例只在运行环境支持符号链接时执行；不支持时明确记为 `SKIPPED`，CI 必须至少覆盖一个支持符号链接的平台。
- 外部命令使用本地 Python 测试脚本或 mock `subprocess.run`，不调用网络和真实项目工具。
- `TemporaryDirectory` 退出后删除全部测试文件；`tearDown` 断言临时根不存在。测试失败时测试框架仍执行清理。
- 本需求没有业务/API 数据，因此租户、用户、订单等数据准备不适用；“清理验证”指临时目录、子进程和 mock 状态均已释放。

## 夹具与辅助函数

| 夹具 | 内容 | 用途 |
| --- | --- | --- |
| `valid_catalog()` | 包含所有规则集合、有限检查类型、阶段契约和有效引用 | 规则目录正例 |
| `risk_config_all_tags()` | 当前 `critical_triggers`、`score_rules` 及新增 performance/reliability 标签 | 风险映射完整性 |
| `valid_policy()` | 阈值来源、参数数组命令、超时和 CI 声明 | 项目策略正例 |
| `valid_v2_run()` | v2 state、规则快照、worklist、阶段结果和证据文件 | 控制器与健康检查 |
| `legacy_v1_run()` | 无 `contract_version`、无规则快照的既有运行 | 兼容测试 |
| `valid_solution_artifact()` | 质量属性、决策、兼容、回滚和工作项 | 方案结构与语义 |
| `valid_test_plan_artifact()` | AC/规则映射、数据、执行、断言、清理和清理验证 | 测试计划语义 |
| `snapshot_files()` | state、stage-results、worklist、events 的 SHA-256 | 失败原子性 |

## 验收标准映射

| 验收标准 | 覆盖用例 |
| --- | --- |
| AC-001 | TC-001、TC-002、TC-003 |
| AC-002 | TC-009 |
| AC-003 | TC-010 |
| AC-004 | TC-011 |
| AC-005 | TC-012 |
| AC-006 | TC-014、TC-015、TC-016、TC-018 |
| AC-007 | TC-017 |
| AC-008 | TC-021、TC-022 |
| AC-009 | TC-003、TC-004、TC-005、TC-032、TC-033 |
| AC-010 | TC-023、TC-024、TC-028 |
| AC-011 | TC-026、TC-029 |
| AC-012 | TC-024、TC-026、TC-031 |
| AC-013 | TC-025 |

## 适用规则覆盖

当前运行是 v1，尚无规则快照；测试设计按已批准方案中的规则集合覆盖，开发时由实际 `catalog.yml` 中的稳定规则 ID 替换集合引用并由映射测试确认无遗漏。

| 规则集合 | 覆盖内容 | 用例 |
| --- | --- | --- |
| common | 有效证据、规则来源、失败处理、自然表达 | TC-001、TC-014、TC-024、TC-026 |
| architecture | 简单性、模块边界、兼容、工作项范围 | TC-009、TC-019、TC-028 |
| security | 输入、路径、敏感信息、依赖和外部命令 | TC-008、TC-012、TC-018、TC-027 |
| performance | 指标来源、负载、环境、基线和允许变化 | TC-011、TC-025 |
| reliability | 原子写入、修正后重试、重复请求、恢复和状态一致性 | TC-016、TC-017、TC-028、TC-030 |
| observability | 健康结果、CI 缺口和可追溯证据 | TC-021、TC-022 |
| testing | 验收映射、异常路径、隔离和清理验证 | TC-010、TC-015、TC-029 |

## 测试用例

### A. 规则目录、风险和项目策略

| ID | 数据准备 | 执行入口 | 断言 | 清理动作 | 清理验证 |
| --- | --- | --- | --- | --- | --- |
| TC-001 有效规则目录 | 临时项目写入完整 catalog、解释文档和结构定义 | `tests.test_loopx_policy.CatalogTest.test_valid_catalog` | 加载成功；版本、规则 ID、适用阶段、检查、证据和返回阶段可追踪 | 退出临时目录 | 根目录不存在 |
| TC-002 规则目录反例矩阵 | 分别删除必填字段、制造重复 ID、悬空规则集合/文档/结构/检查、非法枚举、未知字段和审核检查向后依赖 | `tests.test_loopx_policy.CatalogTest.test_invalid_catalog_matrix` | 每个变体失败；错误包含字段路径和稳定原因；不生成快照 | 退出临时目录 | 根目录及快照均不存在 |
| TC-003 风险 profile 双向完整性 | 基于当前风险配置生成完整映射，再分别删除、增加和重复标签 | `tests.test_loopx_policy.PolicyTest.test_risk_profile_bijection` | 所有已声明标签恰好有一个 profile；空规则集合必须有理由；未声明 profile 被拒绝 | 退出临时目录 | 根目录不存在 |
| TC-004 模式与风险适用性 | 构造 docs_only、test_only、api_contract、core_state_transition、performance 等组合 | `tests.test_loopx_policy.PolicyTest.test_mode_and_risk_rule_selection` | LIGHT 不加载无关规则；STANDARD/FULL 只加载风险匹配规则；关键风险仍选择 FULL | 退出临时目录 | 根目录不存在 |
| TC-005 项目策略优先级与降级 | 公共规则、项目 profile、项目策略、规格指标给出相同阈值和不同来源；另构造降低必需规则 | `tests.test_loopx_policy.PolicyTest.test_policy_precedence_and_downgrade` | 解析结果唯一且记录来源；更具体阈值生效；无用户风险接受记录时不能降低必需规则 | 退出临时目录 | 根目录及未通过快照不存在 |
| TC-006 规则快照固定与摘要 | 初始化有效 v2 运行后修改全局 catalog，再篡改运行快照 | `tests.test_loopx_policy.PolicyTest.test_snapshot_is_fixed_and_hashed` | 运行继续使用初始化快照；全局更新不漂移；快照篡改被摘要检查发现 | 退出临时目录 | 根目录不存在 |

### B. 结构定义、YAML 和阶段语义

| ID | 数据准备 | 执行入口 | 断言 | 清理动作 | 清理验证 |
| --- | --- | --- | --- | --- | --- |
| TC-007 受控结构校验子集 | 构造 `minItems`、`minLength`、`additionalProperties: false` 的正反例 | `tests.test_loopx_policy.SchemaSubsetTest` | 支持项按字段路径报错；既有 type/enum/required/properties/items 行为不回归；不接受未声明高级关键字 | 清理内存夹具 | 无临时文件和全局状态 |
| TC-008 YAML 重复键与未知字段 | 在普通对象和列表合并对象中构造重复键；策略中加入拼写错误字段 | `tests.test_loopx_policy.YamlSafetyTest` | 两类重复键均报错；关键对象未知字段报错；合法 `extensions` 保留 | 退出临时目录 | 根目录不存在 |
| TC-009 方案产物结构与语义 | 构造完整方案；依次删除简单性、边界、安全、性能、兼容、可靠性、可观测性、回滚；构造空的不适用理由 | `tests.test_loopx_evidence.EvidenceTest.test_solution_artifact_semantics` | 正例通过；缺少适用质量属性失败；不适用项无具体理由失败；工作项字段合法 | 退出临时目录 | 根目录不存在 |
| TC-010 测试计划映射与清理 | 构造全部 AC 和适用规则映射；分别遗漏 AC、规则、数据准备、入口、断言、清理、清理验证 | `tests.test_loopx_evidence.EvidenceTest.test_test_plan_coverage_and_cleanup` | 正例通过；任何映射或生命周期字段缺失均失败；明确不适用必须有理由 | 退出临时目录 | 根目录不存在 |
| TC-011 性能风险与方案审核 | 分别创建有完整性能目标、缺目标来源、缺负载/环境/基线/允许变化的 v2 方案审核输入 | `tests.test_loopx_evidence.EvidenceTest.test_performance_risk_controls_solution_review` | 完整目标允许 `solution_review` 记录 PASS；命中性能风险但缺少任一必需维度时不能记录 PASS，状态和事件不变；不注入统一固定数值 | 退出临时目录 | 根目录不存在 |
| TC-012 安全结果语义 | 为身份、权限、租户、输入、敏感信息、依赖、外部副作用构造 PASS/CI_REQUIRED/BLOCKED/SKIPPED | `tests.test_loopx_evidence.EvidenceTest.test_security_controls_by_risk` | 只要求适用控制；必需控制无证据时失败；未覆盖状态符合规则策略；证据不含模拟凭据 | 退出临时目录并清空 mock | 根目录不存在，mock 调用为空 |

### C. v2 控制器、证据和 worklist

| ID | 数据准备 | 执行入口 | 断言 | 清理动作 | 清理验证 |
| --- | --- | --- | --- | --- | --- |
| TC-013 新运行初始化 | 临时项目放置有效 catalog/risk/profile，可选策略为空 | `tests.test_loopx_evidence.LoopxControllerV2Test.test_init_v2` | state 写入 `contract_version: 2`、目录版本、快照路径和摘要；旧初始化参数仍可用 | 退出临时目录 | 根目录不存在 |
| TC-014 有效阶段结果记录 | 创建 v2 运行、必需产物、全部规则结果和项目内证据文件 | `tests.test_loopx_evidence.LoopxControllerV2Test.test_record_stage_pass_with_artifacts` | PASS 成功；产物类型、版本、规则结果及非空证据写入；下一状态正确 | 退出临时目录 | 根目录不存在 |
| TC-015 阶段记录失败矩阵 | 分别使用空证据、缺失文件、目录、错误产物类型/版本/运行 ID/阶段、失败规则、无确认的风险接受和阶段级风险接受 | `tests.test_loopx_evidence.LoopxControllerV2Test.test_record_stage_rejects_invalid_evidence_matrix`、`test_required_rule_failure_and_unconfirmed_acceptance_are_rejected` | 每个变体失败，原因可定位；阶段不变；不能用宽泛审核结果替代机器结果 | 退出临时目录 | 根目录不存在 |
| TC-016 失败原子性 | 分别制造输入校验失败、底层第二个目标替换失败，并保存 state、stage-results、worklist、events 摘要 | `tests.test_loopx_evidence.LoopxControllerV2Test.test_record_stage_failure_is_atomic`、`test_atomic_writer_restores_replaced_files_after_storage_error`、`test_record_stage_restores_all_targets_after_storage_error` | 校验失败不写入；存储失败恢复已替换目标；四类文件摘要逐一相同；没有临时结果、备份或半写事件 | 退出临时目录 | 根目录不存在，无残留临时文件 |
| TC-017 严格检查复核 | 先创建有效 v2 运行，再删除证据、篡改快照、改变产物版本或规则结果 | `tests.test_loopx_evidence.LoopxControllerV2Test.test_strict_validate_v2_artifacts` | 完整运行通过；每种篡改被发现；错误指向阶段、规则和证据 | 退出临时目录 | 根目录不存在 |
| TC-018 证据路径边界 | 构造绝对路径、`..`、缺失文件、目录、项目内符号链接和指向项目外的符号链接 | `tests.test_loopx_evidence.EvidencePathTest.test_resolved_path_boundary` | 只接受解析后仍在项目内的普通文件；外链、目录、缺失和越界路径失败 | 删除外部目标并退出临时目录 | 项目根和外部目标均不存在 |
| TC-019 worklist 同步 | 方案产物含两个合法工作项和依赖；再构造重复 ID、未知依赖和依赖环 | `tests.test_loopx_evidence.WorklistTest.test_solution_work_items_sync` | 合法项同步并补齐约定默认值；非法集合不修改 worklist | 退出临时目录 | 根目录不存在 |
| TC-020 工作项引用统一检查 | 对 `record-stage`、`fail-review`、`review-feedback`、`close-repair` 分别传入已知和未知 ID | `tests.test_loopx_evidence.WorklistTest.test_all_commands_validate_item_reference` | v2 已知 ID 按原语义执行；未知 ID 均失败且不改状态；v1 保持原兼容行为 | 退出临时目录 | 根目录不存在 |
| TC-030 修正后重试与重复请求 | 第一次使用无效证据触发失败，修正产物后重试；成功后再次提交完全相同请求 | `tests.test_loopx_evidence.LoopxControllerV2Test.test_retry_and_duplicate_submission` | 首次失败无文件变化；修正后只推进一次；重复请求要么稳定返回已有结果，要么明确拒绝且不追加事件，不能重复推进或覆盖证据 | 退出临时目录 | 根目录不存在，事件中只有一次有效转换 |
| TC-032 等级选择与固定快照 | 用 LIGHT 初始化含核心状态风险的 v2 运行，再选择 FULL；另篡改原快照后重试 | `tests.test_loopx_evidence.LoopxControllerV2Test.test_mode_selection_updates_snapshot_and_fails_without_partial_writes` | 新快照从初始化时固定候选规则生成；state、快照和 worklist 等级一致；摘要同步；篡改时状态、产物和事件均不改变 | 退出临时目录 | 根目录不存在，无部分写入 |
| TC-033 逐规则风险接受 | 为 OBS 规则构造有/无匹配确认文件的质量结果，并同时放入无关的整体等级降级记录 | `tests.test_loopx_evidence.LoopxControllerV2Test.test_rule_acceptance_requires_matching_quality_confirmation` | 整体等级降级不能替代逐规则确认；只有规则 ID、理由和真实确认文件匹配时允许通过 | 退出临时目录 | 根目录不存在 |

### D. 健康检查与外部命令

| ID | 数据准备 | 执行入口 | 断言 | 清理动作 | 清理验证 |
| --- | --- | --- | --- | --- | --- |
| TC-021 配置驱动健康检查 | 临时 `health.yml` 声明全部核心检查，并准备一份完整 v2 运行 | `tests.test_loopx_health.HealthConfigTest.test_executes_declared_core_checks` | 每个配置项恰好执行一次；未知必需检查导致失败；结果包含检查 ID、状态和证据 | 退出临时目录 | 根目录不存在 |
| TC-022 状态汇总矩阵 | 分别模拟全部通过、CI 执行、可选工具缺失、必需工具缺失和混合结果 | `tests.test_loopx_health.HealthResultTest.test_status_aggregation` | 准确得到 PASS、CI_REQUIRED、SKIPPED 或 BLOCKED 组合；不得把未执行项写成 PASS | 清空 mock 并退出临时目录 | 无子进程，根目录不存在 |
| TC-027 外部命令安全执行 | 策略配置 Python 参数数组、超时、非零退出和含模拟敏感值输出 | `tests.test_loopx_health.HealthCommandTest.test_safe_command_execution` | 不使用 shell；参数不拼接；超时终止；退出码保留；敏感值脱敏；不自动安装工具 | 确认子进程结束并退出临时目录 | 无存活子进程，根目录不存在 |

### E. 兼容、自然中文和整体回归

| ID | 数据准备 | 执行入口 | 断言 | 清理动作 | 清理验证 |
| --- | --- | --- | --- | --- | --- |
| TC-023 v1 兼容回归 | 复制无版本字段的 v1 fixture，准备原格式证据和阶段结果 | `tests.test_loopx_evidence.LoopxLegacyCompatibilityTest.test_v1_end_to_end` 负责自由文本记录兼容；`tests.test_loopx_controller` 和 `tests.test_loopx_health.HealthConfigTest.test_v1_does_not_require_v2_snapshot_or_rule_results` 分别覆盖检查、修复、推进、健康检查和收口 | v1 各能力继续可用；不要求快照、新产物或新字段；不把单个用例描述为完整流程 | 退出临时目录 | 根目录不存在 |
| TC-024 CLI 兼容与自然中文 | 枚举顶层及全部子命令；准备成功、参数错误、流程错误和正常的物理访问控制产品名 fixture | `tests.test_loopx_standardization.LoopxCliLanguageTest.test_commands_and_messages` | 既有主命令和参数仍可调用；帮助、成功、错误、状态、下一步和报告使用首选自然表达；正常安全词汇不被替换；内部 ID 仅在兼容位置出现 | 退出临时目录 | 根目录不存在 |
| TC-025 500/60 配置化 | 未配置项目阈值、显式启用阈值、覆盖更严格阈值三组项目 | `tests.test_loopx_policy.QualityThresholdTest.test_project_owned_thresholds` | 未配置时不作为通过条件；配置后按来源和值检查；LoopX 不注入统一默认数值 | 退出临时目录 | 根目录不存在 |
| TC-026 包资产与文档一致性 | 使用真实仓库，枚举新增标准、结构定义、模板、智能体、技能、README 和 manifests；执行前保存 `git status --porcelain=v1 -uall` 完整快照 | `tests.test_loopx_standardization`、`tests.test_loopx_skill_package` | 资源存在、引用不悬空、清单同步、自然中文范围通过、未写入禁止目录 | 无写入；执行后再次读取完整状态 | 前后完整状态快照逐字一致，包括未跟踪文件 |
| TC-028 v2 完整流程 | 临时项目从 init 开始，生成方案、测试、开发、质量、安全、性能和健康产物，依次推进至收口 | `tests.test_loopx_evidence.LoopxControllerV2E2ETest.test_full_v2_seventeen_stage_close` | 17 个阶段保持不变；规则与证据逐步累积；确认阶段仍需确认；最终证据矩阵完整 | 退出临时目录 | 根目录不存在 |
| TC-029 全量回归与包检查 | 使用真实仓库；执行前保存 `git status --porcelain=v1 -uall` 完整快照，不准备外部数据 | `python3 -m unittest discover -s tests`；`python3 loopx/tools/loopx_check.py package --root .` | 全部测试和包完整性检查返回 0；现有 73 个基线用例不回归 | 无业务清理；检查测试临时目录；执行后再次读取完整状态 | 无残留 `loopx-std-*` 目录，前后完整状态快照逐字一致 |
| TC-031 自然中文人工复核 | 汇总本次修改的 README、流程文档、模板、智能体、技能、命令帮助、消息和报告清单 | 独立审核者逐文件检查，并把文件清单、发现和结论写入 `docs/loopx/2026-08-17-process-standards/07-quality-audit.md#自然中文人工复核` | 用户可见说明自然直接；未使用生硬流程比喻；正常安全领域词汇不误改；内部 ID 只出现在兼容上下文；结论有文件级证据 | 只读审核，不修改运行数据 | 审核记录存在且 `git status --porcelain=v1 -uall` 仅增加预期文档变化 |

## 核心状态风险适用性

当前运行包含 `core_state_transition`，因此必须执行 TC-016、TC-017、TC-028 和 TC-030。其他常见状态风险逐项判断如下：

| 风险 | 结论 | 理由与后续约束 |
| --- | --- | --- |
| 失败后重试 | 适用 | 阶段记录可能因证据或规则失败；TC-030 验证修正后可重试且只推进一次 |
| 重复提交与幂等 | 适用 | CLI 可能被自动化重复调用；TC-030 要求重复请求不重复推进、不重复写事件、不覆盖首次证据 |
| 并发写入 | 当前不适用 | LoopX 是本地单进程 CLI，本方案没有并行写入协议；第一版明确为单写者契约。若未来支持并发执行，必须先设计文件锁、冲突检测和并发恢复测试，不能沿用本结论 |
| 重复消息 | 不适用 | 本需求不消费 MQ 或事件总线消息，controller 事件是本地追加审计记录，不存在消息确认或重复消费协议 |
| 分页 | 不适用 | 本需求没有分页 API、游标或分批读取契约；规则、阶段和工作项均作为本地完整集合校验 |
| 时间窗口 | 不适用 | 除审计时间戳外，没有超时窗口、过期决策或时间范围业务规则；时间戳不参与通过判断 |

## 失败归因与返回阶段

测试执行报告必须为每个失败记录：用例 ID、命令、实际结果、期望结果、证据、归因、`return_to` 和是否需要 CI。不能把环境问题记成代码缺陷，也不能用修实现掩盖错误测试。

| 归因 | 判断依据 | 状态 | 返回阶段 |
| --- | --- | --- | --- |
| 实现失败 | 测试前置和期望正确，实际行为违反已批准规格或方案 | CHANGES_REQUIRED | `development` |
| 测试设计失败 | 用例遗漏约束、fixture 与场景不符、断言错误、清理设计不完整 | CHANGES_REQUIRED | `test_design` |
| 本地环境不可用 | 必需运行时、权限或文件系统能力缺失，无法得到有效实现结论 | BLOCKED | `test_execution`，等待环境恢复后重试 |
| 仅 CI 可执行 | 本地条件不具备且方案明确由 CI 执行 | CI_REQUIRED | 不误报本地通过，最终报告列出 |
| 可选增强不可用 | 不影响必需规则，且目录明确为可选 | SKIPPED | 继续并保留原因 |
| 必需工具未配置 | 适用规则要求该工具但项目没有配置或不可运行 | BLOCKED | `development` 或项目配置责任阶段，按规则 `return_to` |
| 清理或清理验证失败 | 测试创建内容可能残留，结果可信度不足 | BLOCKED | `test_execution`；完成清理并验证前不得通过 |

## 测试文件分配

| 文件 | 职责 |
| --- | --- |
| `tests/test_loopx_policy.py` | TC-001 至 TC-008、TC-025；直接覆盖规则、风险、YAML 和受控结构校验，不通过控制器间接测试底层解析器 |
| `tests/test_loopx_evidence.py` | TC-009 至 TC-020、TC-023、TC-028、TC-030、TC-032、TC-033；包含 v2 控制器、worklist、v1 fixture 和完整流程，避免继续扩大既有控制器测试文件 |
| `tests/test_loopx_health.py` | TC-021、TC-022、TC-027 |
| `tests/test_loopx_controller.py` | 保留现有 56 个控制器兼容测试，只在已有断言必须适配自然中文时做最小修改 |
| `tests/test_loopx_standardization.py` | TC-024、TC-026 的标准和结构定义内容检查、风险/阶段引用、命令消息与自然表达；TC-031 为独立人工复核，不伪装成自动测试 |
| `tests/test_loopx_skill_package.py` | TC-026 的 README、SKILL、workflow、模板、智能体和 manifest 兼容 |

## 执行顺序

1. 先运行新增模块的定向测试，确保失败原因单一且可定位。
2. 再运行 controller v1/v2 兼容和端到端测试。
3. 再运行全量 unittest 和包完整性检查。
4. 最后检查 Git 变更范围和临时目录残留。

## 环境依赖与未覆盖范围

- 必需：Python 3、标准库、可写临时目录、Git 只读命令。
- 可选：支持符号链接的文件系统；本地不支持时记录 `SKIPPED`，由 CI 补充。
- CI_REQUIRED：多平台符号链接行为、真实 CI 执行、项目外部工具适配器。
- 本轮禁止：自动安装依赖、网络调用、真实发布和生产写入。

## 阶段结果

```yaml
stage_result:
  stage: test_design
  status: PASS
  return_to: ""
  next_action: test_review
  affected_work_items:
    - W3
  evidence:
    - docs/loopx/2026-08-17-process-standards/04-test-cases.md
    - docs/loopx/runs/2026-08-17-loopx/artifacts/spec.md
    - docs/loopx/2026-08-17-process-standards/02-solution.md
  user_confirmation_required: false
  blocked_reason: ""
```
