# 失败与工具知识自审查（三方 × 六维度，18 轮收敛）

- 审查对象：`knowledge/failures/` 20 条、`knowledge/tool_guides/` 8 条、18 条来源、`scripts/` 校验与审计代码
- 审查周期：2026-11-01 22:2x – 22:5x，共 18 轮
- 终止条件：连续两轮（R17、R18）零发现
- 结论：**37 项发现全部关闭，连续两轮零发现**；剩余事项均为已在制品内标注的可接受限制，不是缺陷

## 1. 审查设定

三个视角刻意互相冲突，避免同一种偏好被重复计分：

| 视角 | 关心什么 | 最不能接受 |
| --- | --- | --- |
| R1 规范方 | 结构、命名、证据可追溯、演进成本 | 状态位撒谎（"已验证"混着自定阈值） |
| R2 执行方 | 字段能否直接驱动代码、阈值能否判定 | 语义未定义（同一字段两种实现） |
| R3 消费方 | 能否检索到唯一正确的卡、读完能否行动 | 同一状态命中多张卡，只能靠猜 |

六个维度：D1 事实准确性、D2 结构合规性、D3 可诊断性、D4 可恢复性、D5 可验证性、D6 可维护/可检索性。

每轮的检查由四部分组成，缺一不算"跑过"：

1. `python3 scripts/validate_knowledge.py`（字段契约）
2. `python3 scripts/audit_knowledge.py`（跨文件语义审计，见 §3）
3. `python3 -m unittest discover -s scripts`（13 tests）
4. 人工抽样：逐字读 ≥2 张卡；R16 对剩余 13 张做了全字段扫描，至此 28 条均被逐条核过

## 2. 轮次日志

| 轮 | 发现 | 内容 | 处理 |
| --- | --- | --- | --- |
| R1 | 12 | 阶段误标、四组卡片路由歧义、命名、类型矛盾、措辞、来源歧义、时间戳 | 修复 7，遗留 5 转契约级问题 |
| R2 | 2 | `bot.entities(item)` 是我写的伪语法 | 改为 `bot.entities` + 派生特征 |
| R3 | 1 | issue #343 摘录声称"无维护者诊断"，但我只看到评论计数 | 删除未验证断言 |
| R4 | 1 | `escalate_after=1` 与"首次即升级"矛盾，L2/L3 永不执行 | 改为"完成 1 轮恢复后复发即升级" |
| R5 | 2 | `path_stuck` 重复成因；策略阈值标注只在工具卡有 | 合并成因；统一标注 |
| R6 | 3 | 2 张工具卡虚标 `error_codes`；`dig_aborted` 非原生名 | 收缩验证范围；改用 `diggingAborted` |
| R7 | 2 | `night_exposure` 证据类型与来源不符；3 条成功条件含"最终/能安全" | 改 `community_consensus`；改为可即时判定 |
| R8 | 3 | 食物成功阈值 14 低于自身主张的回血阈值 18；岩浆生命阈值缺标注；耐久触发/成功单位不一致 | 统一为 18 / 补标注 / 统一为"任务所需消耗的 120%" |
| R9 | 1 | 交战 12 与撤退 10 之间是滞回带，未写明 | 显式写入 precondition 与 abort |
| R10 | 2 | `recipesFor` 第 3 参数是 `minResultCount`，我传了合成次数；`plan_stale` 特征名与条件名不一致 | 修正语义；统一为 `plan.state_version` |
| R11 | 2 | `goto` 把 6 个 `path_reset` 原因塞进 2 条（无法按码索引）；2 个工具缺超时中止 | 拆成 6 条；补 timeout abort |
| R12 | 0 | 扫描器把原生错误名判为"非 snake_case"噪声 | 判定为设计意图，写入白名单规则（检查器改进，非数据缺陷） |
| R13 | 3 | "挖掘噪声吸引实体"（普通怪不循声）；"工具在合成/放置中被消耗"（不成立）；特殊移动建模表述过强 | 三处均改写为可支持表述 |
| R14 | 1 | `tool_smelt_item` 前置条件引用未声明的 `count` | 改为 `input_count` |
| R15 | 0 | — | — |
| R16 | 2 | 铁器阶段出现"末影箱"；耐久"按硬度扣减"（实为按方块数 1 点） | 改为"箱子等容器"；改为按方块数 |
| R17 | 0 | — | — |
| R18 | 0 | — | — |

合计 37 项发现，全部关闭。**R17、R18 连续两轮零发现。**

## 3. 从"人肉复查"升级为可执行判据

自审查如果只靠肉眼，第二轮就会开始自我宽容。因此把判断固化成脚本 `scripts/audit_knowledge.py`（stdlib；`jsonschema` 存在时额外做严格 schema 校验），退出码非 0 即视为未通过。它检查的是 schema 表达不了的跨文件语义：

1. 失败卡恢复阶梯必须恰好是 L1、L2、L3、L4 且有序
2. `escalate_after` 为正整数，且 L1 的"只允许 N 次"不得大于该阈值
3. 共享同一触发条件的失败卡，必须至少一方在首条诊断里指向另一方（防止"两张卡同时命中"）
4. 工具卡的 `stage` 必须是 `general`
5. 工具卡每个 `failure_mode` 必须带错误码，且格式为 `snake_case` / `ns:code` / 白名单原生名（`NoPath`、`diggingAborted` 等）
6. 声明 `error_codes` 的卡，其至少一个码必须逐字出现在所引来源摘录中（否则视为自造码虚标）
7. `risk_notes` 必须写明禁用场景；`abort_condition` 必须含超时/中断语义
8. 字面量生命/饥饿阈值必须带"策略阈值"标注
9. `state_features` 只能是 snake_case 或受控点路径（`bot.*`、`furnace.*`、`movements.*`、`plan.*`、`runtime.*`）
10. `summary` ≤500 字符；时间戳不得未来化；`source_verified` 必须含可外部核对的范围
11. `evidence_type=official_document` 必须真的引用了官方类来源
12. 严格 JSON Schema（Draft 2020-12）零违规

## 4. 契约变更（schema 2026-11-01 → 2026-11-01.2）

R1 遗留的 5 项里有 3 项是契约缺陷，只能改 schema，不能改文案绕开：

| 变更 | 解决的问题 | 影响面 |
| --- | --- | --- |
| 新增 `escalation_unit`（`recovery_round` / `attempt`），`failure_recovery` 必填 | `escalate_after` 单位未定义，运行时可能按"单次尝试"实现而无限重试 | 20 张卡 + 模板 + validator + 测试 |
| 新增 `verified_scope`（枚举数组），`source_verified` 必填且至少含一项可外部核对的范围 | "已验证"混着自定策略阈值，状态位无法表达部分验证 | 16 条 + validator + 测试 |
| `parameters[].type` 收紧为枚举，并要求 `name`、`type` 必填 | 类型是自由文本（曾出现 `boolean|string`），无法生成校验 | 8 张工具卡 + schema + validator |
| 新增 `knowledge/registry.json` 登记预留 ID，`link_*` 标签必须能解析 | 前向引用无校验，02 阶段改名会静默失效 | 26 个标签 + validator + 2 个测试 |

`project.json` 的 `validation.schema_version` 同步为 `2026-11-01.2`，并登记 `audit_command`。测试从 5 个增至 13 个，覆盖：字符串型 `tool_name`、缺 `escalation_unit`、缺 `verified_scope`、仅 `project_policy` 不得 `source_verified`、非法参数类型、悬空标签、registry 解析。

## 5. 三方各自最不能接受的一点（收敛后）

- **规范方**：`source_verified` 现在必须自带 `verified_scope`，且只有 `project_policy` 一项时校验直接失败。这条规则把"我知道这是我定的"变成机器可查，而不是靠自觉。
- **执行方**：`escalation_unit` 已进制品。运行时不必再猜 `escalate_after=2` 是两次调用还是两轮阶梯；猜错的两种实现会导致"提前放弃"或"无限重试"，后者正是项目红线。
- **消费方**：四组原本会同时命中的卡（合成、路径、冶炼、工具）现在都有首行判别句，指向另一张卡。检索命中多张时不再靠标题猜。

## 6. 可接受限制（已标注，不构成缺陷）

1. **阈值未经回放标定**：`escalate_after`、3.5 s / 5 s / 60 s 等来自源码默认值与推理。所有策略数字均以 `verified_scope: project_policy` 或"策略阈值"标注，`confidence` 上限为 medium。要做的是拿运行日志标定后提升，而不是把现状当已验证。
2. **无 26.3 实机回放**：版本相关数值（单件冶炼时间、煤的处理件数）写成了"需按版本回放校准"的参数说明，没有硬编码。
3. **issue 证据只到"可能原因"级**：#343、#227 均未被维护者修复，可靠性定 B，只用于支撑成因，不支撑结论性阈值。
4. **工具卡双模式**：`attack / retreat` 一个契约承载两种行为，成功条件因此分段表述。拆分会让工具卡超过 8 条，暂不拆，已在卡内明确分段。

## 7. 复检

```bash
cd /home/administrator/mc-decision-knowledge
python3 scripts/validate_knowledge.py        # 42 items / 18 sources / 0 errors / 0 warnings
python3 scripts/audit_knowledge.py           # Audited items: 42 / Findings: 0
python3 -m unittest discover -s scripts -p "test_*.py"   # 18 tests OK
```

（此处条数已更新到 ai_heuristics 批次之后的当前状态；R17/R18 当时为 28 items / 13 tests。）

R17 与 R18 的完整输出均为 `Findings: 0` / `Validation passed.`，两次之间没有任何文件改动，符合"连续两轮零发现"的收敛定义。

> 后续变更（2026-11-01 23:4x，ai_heuristics 批次期间）：审计脚本改为在缺少 jsonschema 时**记 finding 并以非 0 退出**——此前它会打印提示后继续并返回"通过"，导致"严格 schema 校验被跳过"在任何一次运行记录里都看不出失败，这正是它被误判成"已知缺口"的原因。同时补了 `--root` 指向无 `schemas/` 目录时的回退逻辑（原先会直接崩溃），并新增 `scripts/test_audit_knowledge.py`（3 个测试），测试总数 13 → 18。
