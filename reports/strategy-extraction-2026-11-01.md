# 阶段 02 · 策略与手册批次报告（2026-11-01）

- 项目：`mc-decision-knowledge`（目标版本 Java Edition 26.3）
- 阶段提示词：`prompts/02_strategy_extraction.md`
- 产出：`knowledge/strategies/` **12 条**、`knowledge/playbooks/` **6 条**，合计 18 条（单批上限 20）
- 校验：`python3 scripts/validate_knowledge.py` → **60 items / 18 sources / 0 errors / 0 warnings / passed**
- 审计：`python3 scripts/audit_knowledge.py` → **Audited items: 60 / Findings: 0**
- 单元测试：`python3 -m unittest discover -s scripts -p "test_*.py"` → **22 tests OK**

## 1. 里程碑状态（本次之后）

| 类别 | 里程碑要求 | 现有 | 状态 |
| --- | --- | --- | --- |
| strategies | 12 | 12 | 达成 |
| playbooks | 5 | 6 | 达成（提示词的五类场景覆盖 6 个场景，见 §3） |
| failures | 20 | 20 | 达成 |
| tool_guides | 8 | 8 | 达成 |
| ai_heuristics | 12 | 14 | 达成 |

`knowledge/` 现有 60 条知识，**五个类别全部达标**。上一份报告里记为"阶段依赖"的 `strategies/`、`playbooks/` 目录为空这一缺口，至此关闭。

## 2. 策略（12 条）

提示词要求覆盖七个策略主题，全部覆盖，并按"可判别、可回放"的写法落地：

| 提示词主题 | 策略 |
| --- | --- |
| 开局目标排序 | `strategy_opening_priority` |
| 石质工具与熔炉路线 | `strategy_stone_tool_route` |
| 食物来源选择与可持续性 | `strategy_food_sustain` |
| 铁矿获取路线 | `strategy_iron_route` |
| 下矿前的安全基线 | `strategy_premining_safety_baseline` |
| 装备优先级与资源分配 | `strategy_equipment_allocation` |
| 探索与返回补给的权衡 | `strategy_explore_vs_resupply` |
| （夜间暴露处理） | `strategy_night_exposure` |
| （阶段工具组合） | `strategy_tool_mix_for_stage` |
| （采集配额与存放） | `strategy_collect_and_store` |
| （遇敌交战或规避） | `strategy_encounter_engage_or_avoid` |
| （恢复预算与升级路径） | `strategy_recovery_budget` |

每条策略都满足提示词的硬约束：

- **禁止发明数值阈值**：全部条目不含自造的格数/时间/血量阈值（脚本扫描 18 条，零命中）。需要阈值的地方改为引用失败卡或写成状态条件，例如"生命与食物高于安全基线"而不是具体数字。
- **禁止把单一路线写成唯一答案**：每条策略 3 条候选路线 + 3 条取舍说明，且每条路线的适用条件写在取舍里，不是并列罗列。
- **禁止空话**：触发条件、动作、检查项一律写成状态与动作；`actions` 的第一步永远是"读状态"，最后一步是"回写状态事实"。

## 3. 手册（6 条）

提示词要求覆盖五类场景，本批次产出 6 份手册（把"背包与工具管理"独立成册，因为它同时服务开局、采矿与战斗三个场景）：

| 提示词场景 | 手册 | 关联策略 |
| --- | --- | --- |
| 开局资源建立 | `playbook_opening_resource_buildup` | stg_opening_priority、stg_tool_mix_for_stage |
| 首次夜晚 | `playbook_first_night_shelter` | stg_night_exposure、stg_premining_safety_baseline |
| 石质工具与熔炉 | `playbook_stone_tool_furnace` | stg_stone_tool_route、stg_equipment_allocation |
| 下矿准备与执行 | `playbook_iron_mining_run` | stg_iron_route、stg_premining_safety_baseline、stg_explore_vs_resupply |
| 战斗与撤退 | `playbook_combat_retreat` | stg_encounter_engage_or_avoid、stg_equipment_allocation |
| 背包与工具管理 | `playbook_inventory_tool_management` | stg_collect_and_store、stg_tool_mix_for_stage、stg_equipment_allocation |

每份手册都包含提示词要求的七要素：

1. **适用状态**写在 `trigger.conditions`；**不适用状态**写在 `abort_condition`（统一以"不适用："开头）
2. **开始前检查清单** `checklist`（5~7 项，可逐条核对，不是"检查装备"这种空话）
3. **可选策略** `candidate_routes`（3~4 条）
4. **继续条件** `continue_condition`
5. **退出条件** `exit_condition`
6. **失败入口** `failure_entry_points`——全部指向真实存在的 `failure_*` 条目（脚本核对，零悬空）
7. **完成后需要更新的状态事实**——写在 `actions` 的最后一步，逐条列出要回写的字段（工具/材料、庇护所位置、燃料储备、掉落物归属等）

## 4. 前向引用闭环

上一批的知识里，`link_strategy:` / `link_playbook:` 指向的是尚未存在的实体。本批次做了两件事把它变成硬约束：

1. **`knowledge/registry.json` 扩充**：12 个 `stg_*` + 6 个 `pb_*` 预留 ID，并新增 `entity_map`，把领域 ID 映射到条目 ID。
2. **校验器新增两条规则**：
   - `entity_map` 中登记的条目必须真实存在，否则直接报错——悬空映射无法再悄悄通过；
   - 手册的 `failure_entry_points` 必须指向真实存在的 `failure_recovery` 条目（既不能指向不存在的 ID，也不能指向非失败类条目）。

结果：全库 60 条的 `link_*` 标签与 `failure_entry_points` **全部可解析到实体**，不再有前向引用。

## 5. 校验器修复：`scenario` 的第三例同类缺陷

写入手册后首轮校验报 6 条错误：

```text
scenario must be a list of non-empty strings
```

原因与前两批完全同源：`schemas/knowledge-item.schema.json` 与 `templates/playbook.template.json` 都把 `scenario` 定义为**单个字符串**，而校验器在类型必填字段循环里对它套用了"字符串列表"校验。这已经是同一类缺陷的第三次出现（`tool_name` → `decision_rule`/`model_guidance` → `scenario`）。

这次不再逐个加分支，而是**改成通用规则**：

```python
# Fields the schema defines as a single string. Every one of them previously
# tripped the generic "list of strings" branch of the type-field loop.
STRING_FIELDS = {"tool_name", "decision_rule", "model_guidance", "scenario"}
```

并补两个回归测试（`scenario` 为字符串时通过、为列表时报错）。测试总数 20 → 22。

## 6. 审计新增规则与一次自查捕获

审计脚本新增 `audit_playbooks`，要求每份手册必须声明**不适用状态**，且 `actions` 必须包含**状态回写**步骤——这两条正是提示词里点名、却容易被写成隐含约定的要求。

本批次也被审计抓到自己一次：新条目我按"整点"写了 `created_at = 23:55`，而实际时钟还在 23:53，审计的未来时间戳检查直接报了 6 条 finding。已按真实时钟重新打戳。**这道检查就是为这种情况准备的**——上一轮我正因为写了未来时间戳（22:52）才在复核时被发现。

## 7. 仍是 draft 的条目与提升所需证据

**全部 60 条均为 `draft`**（`confidence` 为 medium），符合项目"高置信只能来自 `replay_verified` 或 `human_verified`"的规则。本批次 18 条的提升条件如下：

### 7.1 策略类（12 条）

| 策略 | 需要什么证据才能提升 |
| --- | --- |
| `strategy_opening_priority` | 在真实开局中记录"目标实际推进顺序"与"阻断关系判断"是否一致；需要多局回放样本才能确认排序规则不是事后合理化 |
| `strategy_stone_tool_route` | 同一出生点下分别走三条路线，记录各自的"到达石制工具/熔炉所需工时"与中断次数；这是路线取舍，缺对照数据无法定优 |
| `strategy_food_sustain` | 统计各来源的实际获取间隔与单位产出，并验证"可重复获取"判断是否成立；需要跨多个生物群系与昼夜样本 |
| `strategy_iron_route` | 三条路线在同等装备下的单位时间铁矿产出、死亡/掉装率对比 |
| `strategy_premining_safety_baseline` | 有/无基线两次下矿的存活率与资源回收率对照 |
| `strategy_equipment_allocation` | 按中断主因分配 vs 平均分配的对比数据；需人工标注中断原因 |
| `strategy_explore_vs_resupply` | 返程成本占比与最终带回产量的关系曲线 |
| `strategy_night_exposure` | 四种夜间处置的存活率与次日状态对比 |
| `strategy_tool_mix_for_stage` | 不同携带组合下的掉落物带回率与工具损坏率 |
| `strategy_collect_and_store` | 各存放方式的实际丢失率与往返成本 |
| `strategy_encounter_engage_or_avoid` | 交战 vs 规避的净收益（掉落价值 − 耐久与生命损失） |
| `strategy_recovery_budget` | 各档预算的实际成功率与总耗时；需要人为制造同码失败才能采样 |

### 7.2 手册类（6 条）

| 手册 | 需要什么证据才能提升 |
| --- | --- |
| `playbook_opening_resource_buildup` | 按清单执行与跳步执行的对照回放 |
| `playbook_first_night_shelter` | 封闭方式与次日资源/存活状态的关联数据 |
| `playbook_stone_tool_furnace` | 各生产链节点的失败点分布（哪一步最常断） |
| `playbook_iron_mining_run` | 一次完整作业的检查点数据：目标计数曲线、中断次数、返程损耗 |
| `playbook_combat_retreat` | 撤退阈值触发后的实际存活率；阈值本身需要标定 |
| `playbook_inventory_tool_management` | 腾位动作前后的关键物资保有率与掉落物带回率 |

### 7.3 共同前提

所有提升都以**可重放的事件日志**为前提：需要记录状态版本、目标计数变化、工具与背包 diff、中断事件与失败码。日志格式确定后，可按上表逐条做 `replay_verified` 升级。

## 8. 已知限制

1. **玩法细节仍以社区来源为主**：策略与手册的 `evidence_type` 为 `community_consensus` / `expert_heuristic`，依据是 Minecraft Wiki 与各 AI 项目经验；具体配方、冶炼时长等版本相关事实**未写死在条目里**，需要时以当前版本为准并回放核验。
2. **阈值一律没有写死**：这是刻意的。阈值应由回放数据标定后再写回条目，而不是先写一个看起来合理的数字。
3. **来源仍是 18 条**：本批次未新增来源，复用了既有来源；后续若要提升策略条目的置信度，应补充针对具体玩法路线的实测来源。

## 9. 复现

```bash
cd /home/administrator/mc-decision-knowledge
python3 scripts/validate_knowledge.py
python3 scripts/audit_knowledge.py
python3 -m unittest discover -s scripts -p "test_*.py"
```

环境说明：本机 WSL 只有 `python3`（无 `python` 别名）；WSL 已安装 jsonschema 4.26.0，严格 JSON Schema 校验在此环境实际执行。
