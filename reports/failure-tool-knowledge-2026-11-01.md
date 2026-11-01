# 失败恢复与工具契约知识批次报告（2026-11-01）

- 项目：`mc-decision-knowledge`（目标版本 Java Edition 26.3）
- 阶段提示词：`prompts/03_failure_and_tool_knowledge.md`
- 产出：`knowledge/failures/` 20 条、`knowledge/tool_guides/` 8 条，共 28 条
- 校验：`python3 scripts/validate_knowledge.py` → **28 items / 18 sources / 0 errors / 0 warnings / passed**
- 审计：`python3 scripts/audit_knowledge.py` → **Audited items: 28 / Findings: 0**（连续两轮零发现，见 §11）
- 里程碑对齐：`project.json` 要求 `failures: 20`、`tool_guides: 8`，本批次正好补齐，未超额

## 1. 批次拆分

| 批次 | 内容 | 条数 | 校验结果 |
| --- | --- | --- | --- |
| A | 8 个工具契约 + 12 张工具相关失败卡 | 20 | 20 items / 0 errors（首轮暴露校验器缺陷，修复后通过，见 §7） |
| B | 8 张生存与环境类失败卡 | 8 | 28 items / 0 errors（累计） |

每批均在写入后立即校验，未使用"攒完再验"的方式。批次 A 的 20 条已达单批上限，因此拆为两批而非一次写入 28 条。

## 2. 优先失败主题覆盖

提示词列出的 12 个优先主题全部有卡片，且多数主题拆成"可区分"的多张卡，而不是一张卡塞多个根因。

| 优先主题 | 卡片 |
| --- | --- |
| 目标资源搜索无进展 | `failure_search_no_progress`、`failure_search_area_repeat` |
| 路径不可达或卡死 | `failure_path_no_path`、`failure_path_stuck`、`failure_path_thrash_reset` |
| 工具耐久不足 | `failure_tool_durability_low`、`failure_tool_broken_mid_task` |
| 背包已满 | `failure_inventory_full` |
| 合成失败或材料缺失 | `failure_craft_missing_material`、`failure_craft_no_recipe` |
| 被战斗或坠落打断 | `failure_combat_interrupt`、`failure_fall_interrupt` |
| 食物不足 | `failure_food_insufficient` |
| 夜晚暴露 | `failure_night_exposure` |
| 岩浆或危险方块 | `failure_lava_hazard` |
| 状态不同步（以为已获得） | `failure_state_desync_inventory` |
| 计划过期（状态版本变化） | `failure_plan_stale` |
| 相同失败重复出现 | `failure_repeat_same_failure` |
| 扩展：冶炼中断 | `failure_smelt_output_blocked`、`failure_smelt_fuel_starved` |

## 3. 工具契约覆盖

| 提示词要求 | 文件 | 主要失败码 |
| --- | --- | --- |
| `mine` / `dig` | `tool_mine_block` | `dig_aborted` `dig_double_call` `dig_out_of_reach` `dig_wrong_tool` `dig_timeout` `dig_no_drop` |
| `craft` | `tool_craft_item` | `craft_no_recipe` `craft_missing_material` `craft_table_unreachable` `craft_window_desync` `craft_inventory_full` |
| `smelt` | `tool_smelt_item` | `smelt_output_blocked` `smelt_fuel_starved` `smelt_input_rejected` `smelt_window_desync` |
| `pathfind` / `goto` | `tool_pathfind_goto` | `NoPath` `Timeout` `GoalChanged` `PathStopped` `path_reset:stuck` `path_reset:block_updated` `status:partial` |
| `collect` / `pickup` | `tool_collect_drops` | `pickup_no_entity` `pickup_out_of_reach` `pickup_contested` `pickup_desync` |
| `attack` / `retreat` | `tool_combat_engage_retreat` | `combat_outnumbered` `combat_cornered` `retreat_no_path` `retreat_interrupted` |
| `deposit` / inventory | `tool_inventory_deposit` | `container_full` `deposit_wrong_item` `deposit_desync` |
| `eat` / survival | `tool_eat_recover` | `eat_no_food` `eat_interrupted` `eat_not_hungry` |

### 八个必备维度到 schema 字段的映射

`schemas/knowledge-item.schema.json` 没有独立的"超时"和"禁用场景"字段，且顶层 `additionalProperties: false`。为避免改 schema 破坏已有契约，八个维度按下列方式落位，语义不丢失：

| 要求 | 落位字段 |
| --- | --- |
| 工具名 | `tool_name`（字符串） |
| 参数和类型 | `parameters[]`（`name` / `type` / `required` / `description`） |
| 前置条件 | `preconditions[]` |
| 预期后置状态 | `expected_effects[]` + `success_condition` |
| 常见失败模式和错误码 | `failure_modes[]`，错误码优先使用实现里真实存在的名字（`err.name`、事件名、`path_reset` reason） |
| 超时与中断语义 | `abort_condition[]` + 参数 `timeout_ms`；明确"中断不等于成功" |
| 结果验证方式 | `verification[]` |
| 何时不应使用 | `risk_notes[]`（写成禁止式，与 `preconditions` 互补） |

若后续要由运行时直接读取超时值，建议在 schema 增加结构化字段（如 `timeout_ms`、`interrupt_policy`），而不是继续放在文案里；这属于 schema 变更，需单独评审。

## 4. 恢复分级与阈值约定

所有 20 张失败卡的 `recovery_steps` 均以 `L1`–`L4` 前缀显式分级，且四级齐备（自检脚本已核对，无缺级）：

1. `L1` 工具内部重试或换目标——必须改变至少一个参数，且有次数上限。
2. `L2` 局部子任务重规划——目标不变，改路线/改资源点/改批量。
3. `L3` 回到最近安全检查点——保存已得资源，重置基线。
4. `L4` 升级给大模型——废弃当前计划，绑定新的 `state_version`。

`escalate_after` 语义：在相同 `(failure_id, target_signature, state_version)` 下允许的恢复轮次上限，达到即进入 L4。分布如下：

| 阈值 | 卡片 | 依据 |
| --- | --- | --- |
| 1（1 张） | `failure_lava_hazard` | 熔岩伤害不可逆，第一次出现就放弃作业面，不允许"修正后重试" |
| 2（16 张） | 路径、合成、装备、状态同步、坠落、夜晚、食物、背包等 | 单次失败成本高：掉物品、掉耐久、掉生命 |
| 3（3 张） | `failure_search_no_progress`、`failure_path_thrash_reset`、`failure_repeat_same_failure` | 探索型/元失败允许有限次参数变化，但仍硬性封顶 |

全部卡片均写明 `forbidden_actions`，其中共享的禁止项包括：原样重发同一目标、无上限重试、把超时当"再等等"、把预测状态当事实。**没有任何卡片允许无限重试。**

## 5. 与策略/手册的关联方式

schema 没有 `related_playbooks` 字段，因此关联写在 `tags` 里，使用可解析前缀：

- `link_playbook:<id>`：该失败是本手册的入口，或该工具被该手册使用
- `link_strategy:<id>`：该失败对应哪条策略的失效分支
- `theme:<slug>`：检索主题（`search` / `path` / `durability` / `capacity` / `state-sync` / `hazard` …）

本批次固定了以下**预留 ID**，02 阶段产出手册与策略时必须使用同名 ID，否则标签会悬空：

```text
playbooks: pb_opening_resource_buildup, pb_first_night_shelter,
           pb_stone_tool_furnace, pb_iron_mining_run, pb_combat_retreat
strategies: stg_opening_priority, stg_food_sustain, stg_iron_route,
            stg_night_exposure, stg_equipment_allocation, stg_explore_vs_resupply
```

当前分布：`pb_iron_mining_run` 19 次（它是本里程碑的集成手册，多数工具与采矿失败都挂在它下面），`pb_combat_retreat` 3，`pb_stone_tool_furnace` 3，`pb_first_night_shelter` 1。注意 validator 目前**不校验标签引用**，悬空标签不会报错，这是已知缺口（§8）。

## 6. 证据基础

新增 9 条细粒度来源（原有 9 条为项目级粗粒度来源，无法支撑错误码级知识）：

| source_id | 类型 | 提供的可核对事实 |
| --- | --- | --- |
| `src_mineflayer_api_actions` | official_document | `dig` 在"被中断"时同样 resolve；重复 dig 触发 fatal `diggingAborted`；`craft` 完成后背包才更新；熔炉方法名与 `fuel ∈ [0,1]` |
| `src_mineflayer_api_events` | official_document | `diggingCompleted` / `diggingAborted` / `forcedMove` / `blockUpdate` 语义 |
| `src_pathfinder_goto_errors` | source_code | `NoPath` / `Timeout` / `GoalChanged` / `PathStopped` 四个具名错误及原文消息 |
| `src_pathfinder_reset_reasons` | source_code | A* 状态 `partial/timeout/noPath/success`；9 种 `path_reset` reason；`stuck` 的 3500 ms 阈值；`thinkTimeout` 5000 ms |
| `src_baritone_usage_commands` | official_document | `goto` / `stop` / `cancel` / `forcecancel` 的命令级中断语义 |
| `src_baritone_settings_timeouts` | source_code | 超时与阈值默认值：500/2000/4000/5000/40000 ms、`pathingMaxChunkBorderFetch` 50、`maxFallHeightNoWater` 3、`blockReachDistance` 4.5 |
| `src_baritone_features_pathing` | official_document | 危险方块规避；渲染距离导致的分段规划与提前退出 |
| `src_issue_pathfinder_stuck_stairs` | issue_or_pr | issue #343：楼梯朝向导致寻路认为可走、实际走不上去（野外证据，可靠性 B） |
| `src_issue_pathfinder_parkour_physics` | issue_or_pr | issue #227（协作者报告）：物理模拟跳不过判定可达的 2 格跳跃 |

证据强度分布：`source_verified` 16 条（8 个工具契约 + 8 张失败卡，其错误码/默认值可在源码或官方文档里逐字核对），`draft` 12 条（生存、环境、搜索与规划类，依赖玩法文档与架构推理）。置信度最高为 `medium`——没有任何条目经过回放或人工验证，符合项目"高置信只能来自 `replay_verified` / `human_verified`"的规则。

自审查阶段起，每条 `source_verified` 必须声明 `verified_scope`（`api_contract` / `error_codes` / `default_values` / `gameplay_mechanics` / `project_policy`），且至少包含一项可外部核对的范围；只有 `project_policy` 的条目不得标为 `source_verified`。这解决了"官方文档结论"与"我方设定的阈值"混在同一个状态位里的问题。

顺带记录一处来源内部矛盾：Baritone `FEATURES.md` 称持水桶可坠落更远（约 23 格），而 `Settings.java` 的 `maxFallHeightBucket` 默认为 20。本批次以**设置默认值为准**，并在来源 `notes` 中标明，没有把两个数字混写成一条事实。

## 7. 校验器修复

首次运行批次 A 校验时报 8 条同类错误：

```text
tool_name must be a list of non-empty strings
```

原因是 `validate_knowledge.py` 在类型必填字段循环里，对 `tool_guide` 的 `tool_name` 套用了"字符串列表"校验；而 `schemas/knowledge-item.schema.json` 与 `templates/tool-guide.template.json` 都把 `tool_name` 定义为**单个字符串**。判定为校验器缺陷而非数据缺陷，因此：

1. 在 `validate_item` 中为 `tool_name` 增加独立分支（非空字符串校验），不改数据去迁就错误规则；
2. 增加两个回归测试：`test_tool_guide_accepts_string_tool_name`、`test_tool_guide_rejects_empty_tool_name`；
3. `python3 -m unittest discover -s scripts -p "test_*.py"` → **7 tests OK**（原 5 + 新增 2）。

自审查阶段在同一文件继续补齐了四条新规则并扩充到 **13 tests**：`escalation_unit` 必填、`verified_scope` 必填、仅 `project_policy` 不得 `source_verified`、`parameters[].type` 必须在枚举内、`link_*` 标签必须能解析（详见 §11）。

## 8. 已知缺口

自审查 18 轮后，本节按"是否仍为未关闭的问题"重新分类。

**已关闭**（原 4、5 项）：

- 标签引用无校验 → 新增 `knowledge/registry.json` 登记预留 ID，validator 与审计都会拒绝悬空 `link_*` 标签。
- `escalate_after` 与 `recovery_steps` 的一致性靠人工 → 审计脚本检查 L1 声明的尝试次数不得大于 `escalate_after`，并检查 L1–L4 齐全有序。
- `escalate_after` 单位未定义 → 新增 `escalation_unit` 字段（`recovery_round` / `attempt`），20 张卡全部显式声明。
- 缺 issue 级证据 → 已补 `src_issue_pathfinder_stuck_stairs`（#343）与 `src_issue_pathfinder_parkour_physics`（#227），并用于 `failure_path_stuck` 的成因。

**仍开放，但已标注为可接受限制**（不再是缺陷）：

1. **阈值未标定**：`escalate_after` 与 3.5 s / 5 s / 60 s 判据来自源码默认值与推理。用户未提供运行日志，因此没有伪造"实测"结论；所有策略数字都带 `verified_scope: project_policy` 或"策略阈值"标注，`confidence` 上限为 medium。
2. **版本相关数值未硬化**：单件冶炼时间、煤的处理件数写成了"需按版本回放核验"的参数说明。
3. **失败卡与启发式未联动**：`ai_heuristics/` 尚为空，"何时放弃目标"目前散落在失败卡的 L4 步骤里，04 阶段应抽出为独立规则。

## 9. 下一批建议

1. ~~采集真实 issue~~ → 已完成 2 条（#343、#227）；下一批补带复现步骤与维护者回应的 case。
2. 拿到运行日志后做阈值标定：把 `escalate_after`、stuck 判定窗口、拾取确认读取次数替换为实测值，并提升到 `replay_verified`。
3. ~~validator 增加标签与阶梯规则~~ → 已完成，另新增 `scripts/audit_knowledge.py` 承担 12 类跨文件语义检查。
4. 02 阶段产出手册/策略时复用 §5 的预留 ID（已登记在 `knowledge/registry.json`），并在手册 `failure_entry_points` 中反向引用本批次的失败卡。

## 10. 复现

```bash
cd /home/administrator/mc-decision-knowledge
python3 scripts/validate_knowledge.py
python3 scripts/validate_knowledge.py --require-nonempty
python3 scripts/audit_knowledge.py
python3 -m unittest discover -s scripts -p "test_*.py"
```

环境说明：本机 WSL 只有 `python3`（3.14.4），没有 `python` 别名，因此 `README.md` 里的 `python scripts/validate_knowledge.py` 在此环境需改用 `python3`。本次未修改 README，仅在此记录。

## 11. 自审查与契约升级（18 轮）

本批次产出后做了独立自审查（三方 × 六维度），完整轮次日志见 `reports/failure-tool-self-review-2026-11-01.md`。共 18 轮、37 项发现全部关闭，R17 与 R18 连续两轮零发现。

### 契约变更（schema 2026-11-01 → 2026-11-01.2）

- 新增 `escalation_unit`（`recovery_round` / `attempt`），失败卡必填：解决 `escalate_after` 单位未定义，运行时不会在"提前放弃"与"无限重试"之间各写各的。
- 新增 `verified_scope`（枚举数组），`source_verified` 必填且至少含一项可外部核对的范围：把"官方结论"与"我方设定的阈值"拆开表达。
- `parameters[].type` 收紧为枚举并要求 `name`/`type` 必填：类型不再是自由文本。
- 新增 `knowledge/registry.json` 登记预留 ID，`link_*` 标签必须可解析：02 阶段改名会立刻报错而不是静默失效。
- 新增 `scripts/audit_knowledge.py`：12 类跨文件语义检查，退出码非 0 即未通过。

### 数据侧修复（按维度）

- D1 事实准确性："挖掘噪声吸引实体"（普通怪不循声）、"工具在合成/放置中被消耗"、"耐久按硬度扣减"、"末影箱"（铁器阶段不可得）、"饥饿阈值 14 低于回血阈值 18" 等 5 处事实错误已改正。
- D3 可诊断性：四组会同时命中的卡片（合成、路径、冶炼、工具）补"判别："首行；`bot.entities(item)` 伪语法改正。
- D4 可恢复性：`escalate_after=1` 与"首次即升级"的自相矛盾已改为"完成 1 轮恢复后复发即升级"；交战 10–12 的滞回带显式化。
- D5 可验证性：3 条含"最终/能安全"的成功条件改为可即时判定。
- D6 可维护性：`stage` 误标（28 条全为 `iron_age`）、`state_features` 命名混乱、伪属性名、`verified_scope` 虚标均已修正。

### 复检

```text
python3 scripts/validate_knowledge.py   → 28 items / 18 sources / 0 errors / 0 warnings / passed
python3 scripts/audit_knowledge.py      → Audited items: 28 / Findings: 0
python3 -m unittest discover -s scripts  → 13 tests OK
严格 JSON Schema（Draft 2020-12）       → 0 违规
```
