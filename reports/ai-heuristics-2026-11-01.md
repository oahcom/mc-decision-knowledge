# AI 决策启发知识批次报告（2026-11-01）

- 项目：`mc-decision-knowledge`（目标版本 Java Edition 26.3）
- 阶段提示词：`prompts/04_ai_decision_heuristics.md`
- 产出：`knowledge/ai_heuristics/` 14 条（2026-11-01 23:4x 复核后修正；原稿误记为 12）
- 校验：`python3 scripts/validate_knowledge.py` → **42 items / 18 sources / 0 errors / 0 warnings / passed**
- 审计：`python3 scripts/audit_knowledge.py` → **Audited items: 42 / Findings: 0**
- 单元测试：`python3 -m unittest discover -s scripts -p "test_*.py"` → **15 tests OK**
- 里程碑对齐：`project.json` 要求 `ai_heuristics: 12`，本批次正好补齐

## 1. 批次与主题覆盖

14 条启发一次性写入，未超出单批 15 条上限（`project.json` 里程碑要求 12 条，超额 2 条）。五大优先主题全部覆盖：

| 主题 | 条目 |
| --- | --- |
| 安全与风险 | `ai_safety_baseline_first`、`ai_pre_explore_conservative_baseline`、`ai_hazard_interrupt_recover` |
| 路线选择 | `ai_cave_vs_branch_mining`、`ai_search_vs_relocate`、`ai_diminishing_returns_stop` |
| 计划质量 | `ai_no_plan_without_complete_state`、`ai_plan_short_checkpoints`、`ai_stale_state_plan_discard`、`ai_output_success_condition` |
| 失败恢复 | `ai_vary_retry_on_failure`、`ai_classify_failure_type` |
| 模型自我约束 | `ai_uncertain_prefer_conservative`、`ai_no_generalize_single_success` |

提示词中"模型自我约束"列出的四条（保守计划、不把一次成功当普适规律、不为完成任务忽略安全、不把推测写成事实）中，前两条独立成卡，后两条分别并入 `ai_safety_baseline_first`（不为完成任务忽略安全）与 `ai_no_plan_without_complete_state` / `ai_uncertain_prefer_conservative`（不把推测写成事实）的 `anti_patterns`，未单独重复建卡。

## 2. 字段契约与证据规则

每条启发均满足七项必备要素，并遵守证据规则：

- **evidence_type**：全部为 `ai_synthesis`（来自内部架构 `src_internal_design` 的合成规则），并搭配至少一个外部 AI 项目来源或社区来源，用于支撑"决策结构"而非"游戏事实"。
- **validation_status**：全部为 `draft`（未经回放或人工验证）。
- **confidence**：全部为 `medium`，未出现 `high`，符合"高置信只能来自 replay_verified / human_verified"的项目规则。
- **source_refs** 分布（复核后修正）：`src_internal_design` 出现于全部 14 条；`src_minedojo_voyager` 14 条；`src_minecraft_wiki_gameplay` 6 条；`src_mindcraft_project` 2 条；`src_baritone_features_pathing` 2 条；`src_mineflayer_api_events` 2 条；`src_pathfinder_reset_reasons` 1 条。均已在 `sources/` 登记。

## 3. 状态特征与协议层可达性

`state_features` 全部复用已沉淀的命名约定，可被协议层获得，不含视觉信息：

- `bot.health`、`bot.food`、`bot.inventory`、`bot.position`、`equipment_durability`——结构化状态中心
- `plan.state_version`、`runtime.state_version`、`current_step`、`step_progress`——计划与运行时版本
- `failure_code`、`attempt_count`、`last_attempt_params`、`target_signature`——失败计数
- `visited_chunks`、`search_ticks`、`interrupt_count`、`target_resource_count`——搜索进度
- `known_threats`、`shelter_available`、`waypoint_available`、`light_sources`、`combat_capability`——安全与探索基线

所有特性名均满足审计要求的 `^[a-z][a-z0-9_]*$` 或点分路径规则。

## 4. 校验器修复

首次校验报 28 条同类错误：`decision_rule` / `model_guidance` 被校验器当作"字符串列表"校验，而 `schemas/knowledge-item.schema.json` 与 `templates/ai-heuristic.template.json` 均把它们定义为**单个字符串**（`"type": "string"`）。判定为校验器缺陷而非数据缺陷，与上一批次修复 `tool_name` 同类：

1. 在 `validate_item` 的类型必填字段循环中，为 `decision_rule`、`model_guidance` 增加单字符串校验分支，不改数据去迁就错误规则。
2. 新增两个回归测试：`test_ai_heuristic_accepts_string_decision_rule_and_guidance`、`test_ai_heuristic_rejects_empty_decision_rule`。
3. 测试总数 13 → 15，全部通过。
4. 复核阶段另为审计脚本补了 3 个回归测试（干净仓库 0 发现 / 缺 jsonschema 必须报错 / 缺依赖时闸门非 0 退出），并修掉审计脚本的两处健壮性问题：缺 jsonschema 时静默跳过 → 改为记 finding 并失败；用 --root 指向没有 schemas/ 的目录时崩溃 → 改为回退到脚本自带 schema，找不到则记 finding。测试总数 15 → 18。

## 5. 已知缺口与归属

原稿把下面四条一律写成"缺口"，其中三条并不是缺陷，一条是误判。逐条归因后，真正需要跟进的只有标定工作与阶段依赖。

| 原稿条目 | 实际归属 | 说明 |
| --- | --- | --- |
| ① 所有启发未经回放验证 | **状态，不是缺陷** | 条目已如实标 `draft` / `medium`，符合项目"高置信只能来自 replay/human verified"的规则。§6 已给出每条的回放实验设计。 |
| ② 数值阈值未标定 | **标定任务，不是搜集问题** | 阈值是本项目自定的运行参数（policy），外部来源无法标定它——再多搜集资料也不会让它变准。解法是自建评测集/回放来标定；在标定之前，条目只写语义、不写数字是正确的做法（已核：14 条中未出现任何未标定的具体阈值）。 |
| ③ `strategies/`、`playbooks/` 仍空 | **阶段依赖，不是本批缺陷** | 04 阶段不产出策略与手册。前向引用的 ID 已在 `knowledge/registry.json` 登记，并由 validator 与审计强制解析（已核：14 条的 `link_*` 标签全部可解析）；02 阶段若改用别的 ID 会立刻校验失败。 |
| ④ `jsonschema` 未安装 | **误判（环境搞错）** | 项目真实环境是 WSL，其中已安装 jsonschema 4.26.0，严格 JSON Schema 校验**实际执行且 0 违规**。该结论多半来自在 Windows 侧跑审计（那里确实没有 jsonschema），与此前 `python` / `python3` 属同一类环境错配。 |

### ④ 暴露出的真实缺陷（已修）

审计脚本此前在缺少 `jsonschema` 时会打印一行提示后**继续并返回通过**，于是"严格 schema 校验被跳过"这件事在任何一次运行记录里都看不出失败——这正是它能被误判成"已知缺口"的原因。已改为：缺依赖时直接记一条 finding 并以非 0 退出。现在两侧行为是——

```text
WSL（有 jsonschema）：Audited items: 42 / Findings: 0 / 退出码 0
Windows（无 jsonschema）：Findings: 1（跳过即失败）/ 退出码 1
```

### 真正待办

1. **标定**：按 §6 的回放实验设计拿到运行日志，把 ② 里的阈值标成具体数字，并逐条提升 `validation_status`。
2. **联动**：02 阶段产出 `strategies/` / `playbooks/` 时复用 `registry.json` 中的预留 ID，本批 14 条的 `link_*` 标签即可自动解析。

## 6. 每条启发的升级回放实验

升级到 `replay_verified` 前，每条需对应的回放实验：

| 条目 | 回放实验 |
| --- | --- |
| `ai_safety_baseline_first` | 构造生命/食物/耐久低于基线的状态，回放验证模型是否先执行恢复再进入收益计划；统计低基线强行探索时的死亡/掉装率 |
| `ai_pre_explore_conservative_baseline` | 在无光源/无退路标记状态下下潜，回放验证是否被门槛拦截；对比有/无基线时的洞穴探索存活率与资源回收率 |
| `ai_hazard_interrupt_recover` | 注入战斗/坠落/岩浆中断事件，验证模型是否先确认危险解除再决策，统计中断后续跑导致二次失败的比例 |
| `ai_cave_vs_branch_mining` | 在低/高装备两组状态下回放，验证路线选择是否随状态切换；记录两种路线的单位时间铁矿产出与死亡成本 |
| `ai_search_vs_relocate` | 构造低产区块，回放验证有效进度归零时是否切换区域，而非原地空耗；对比切换前后的资源获取率 |
| `ai_diminishing_returns_stop` | 回放中统计单位时间新发现，验证跌破阈值时是否停止；标定一个可用的边际收益阈值 |
| `ai_no_plan_without_complete_state` | 屏蔽某个关键状态字段，验证模型是否请求补齐而非用推测填充；统计残缺状态生成计划的重规划次数 |
| `ai_plan_short_checkpoints` | 回放带/不带检查点的长任务，对比偏离发现延迟与整体失败率 |
| `ai_stale_state_plan_discard` | 在计划执行中主动递增 state_version，验证模型是否废弃旧计划并绑定新版本重生成 |
| `ai_output_success_condition` | 抽样模型产出的成功条件，验证运行时能否对每一条即时判定达成/失败/未完成 |
| `ai_vary_retry_on_failure` | 制造同一 failure_code，验证每次重试是否改变至少一个维度，并确认达到上限时升级而非循环 |
| `ai_classify_failure_type` | 注入工具失败、状态错误、策略错误各若干，验证归类准确率与恢复动作匹配率 |
| `ai_uncertain_prefer_conservative` | 在信息遮蔽状态下回放，验证是否选可逆低损失计划，统计冒进决策的不可逆损失 |
| `ai_no_generalize_single_success` | 回放单次成功后模型是否克制外推；验证多环境/多状态重复后的结论收敛性 |

## 7. 复现

```bash
cd /home/administrator/mc-decision-knowledge
python3 scripts/validate_knowledge.py
python3 scripts/audit_knowledge.py
python3 -m unittest discover -s scripts -p "test_*.py"
```

环境说明：本机 WSL 只有 `python3`（无 `python` 别名），因此 `python` 需改用 `python3`（与既有批次一致）。WSL 已安装 jsonschema 4.26.0，严格 JSON Schema 校验在此环境实际执行；若在未装该依赖的环境（如 Windows 侧）运行，`audit_knowledge.py` 会因跳过严格校验而以非 0 退出，不再把"跳过"当成"通过"。

复核补充（2026-11-01 23:4x）：本批 14 条已用与失败/工具批次同一套审计规则复核，42 条整体 0 发现；另核对了 17 条提示词主题的覆盖——"达到恢复上限后必须升级"落在 `ai_vary_retry_on_failure` 的 `model_guidance`，"不把推测写成事实"落在 `ai_uncertain_prefer_conservative` 的 `anti_patterns`，无遗漏。
