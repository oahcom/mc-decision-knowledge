# 02 Strategy Extraction Prompt：策略与场景手册

你负责把已登记来源转化为 `strategy` 和 `playbook` 知识。不要新增来源；证据不足时停止并报告。

## 输入

- 知识模板：
  - `templates/strategy.template.json`
  - `templates/playbook.template.json`
- 来源目录：`sources/`
- 目标范围：`project.json` 中的 `spawn_to_iron`

## Strategy 条目要求

每条策略必须回答：

1. 这个策略解决什么阶段目标？
2. 什么状态下应该考虑它？
3. 有哪些候选路线？
4. 每条路线的收益、成本和风险是什么？
5. 什么条件下必须放弃？
6. 成功如何由游戏状态验证？

优先主题：

- 开局目标排序：木头、工作台、基础工具、食物、庇护所。
- 石质工具与熔炉路线。
- 食物来源选择与可持续性。
- 铁矿获取路线：洞穴、分支挖矿、替代来源。
- 下矿前的安全基线。
- 装备优先级与资源分配。
- 探索与返回补给的权衡。

## Playbook 条目要求

首版必须覆盖五类场景：

1. 开局资源建立。
2. 首次夜晚。
3. 下矿准备与执行。
4. 战斗与撤退。
5. 背包与工具管理。

每份手册必须包含：

- 适用状态与不适用状态。
- 开始前检查清单。
- 可选策略。
- 继续条件。
- 退出条件。
- 失败入口，引用具体 `failure_` ID。
- 完成后需要更新的状态事实。

## 证据规则

- `official_document`：只用于官方或权威文档明确说明的内容。
- `community_consensus`：至少需要两个独立高质量来源，或一个 A 级来源加明确社区实践。
- `expert_heuristic`：来源是高质量玩家经验，但缺少可复现实验。
- 无法确认版本时，`game_versions` 写 `version-independent` 并在 summary 中说明限制。

## 禁止

- 禁止写“一般来说应该小心”这类空话；必须写成状态条件和动作。
- 禁止发明数值阈值，例如生命值、食物格数、距离、时间。
- 禁止把单一路线写成唯一正确答案。
- 禁止引用不存在的 `source_id`。
- 禁止把模板文件直接复制到 knowledge 目录。

## 输出

1. 新增 `knowledge/strategies/*.json` 与 `knowledge/playbooks/*.json`。
2. 每批不超过 20 条。
3. 运行 `python scripts/validate_knowledge.py`。
4. 写批次报告到 `reports/strategy-extraction-YYYY-MM-DD.md`。
5. 汇报哪些条目仍是 `draft`，以及需要什么证据才能提升。
