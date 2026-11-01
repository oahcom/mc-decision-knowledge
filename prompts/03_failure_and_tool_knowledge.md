# 03 Failure and Tool Knowledge Prompt：失败恢复与工具契约

你负责构建 `failure_recovery` 与 `tool_guide` 知识。重点是可诊断、可恢复、可验证，不是解释游戏概念。

## 输入

- 模板：
  - `templates/failure.template.json`
  - `templates/tool-guide.template.json`
- 来源：`sources/`
- 重点来源：
  - Mineflayer 文档、示例、测试和 issue。
  - Baritone 使用文档与路径行为。
  - 协议层错误与状态同步问题。
  - 本项目运行日志，如果用户提供。

## Failure Recovery 条目要求

每张失败卡片必须包含：

1. 可观察症状。
2. 可能原因列表。
3. 诊断步骤。
4. 分级恢复步骤。
5. 升级阈值 `escalate_after`，必须为整数且大于 0。
6. 禁止动作。
7. 成功条件。
8. 与策略或手册的关联。

优先失败主题：

- 目标资源搜索无进展。
- 路径不可达或卡死。
- 工具耐久不足。
- 背包已满。
- 合成失败或材料缺失。
- 被战斗或坠落打断。
- 食物不足。
- 夜晚暴露。
- 岩浆或危险方块。
- 状态不同步：以为已获得物品但背包未变化。
- 计划过期：状态版本变化后继续旧计划。
- 相同失败重复出现。

## Tool Guide 条目要求

每个工具必须记录：

- 工具名。
- 参数和类型。
- 前置条件。
- 预期后置状态。
- 常见失败模式和错误码。
- 超时与中断语义。
- 结果验证方式。
- 何时不应使用该工具。

优先工具：

- `mine` / `dig`
- `craft`
- `smelt`
- `pathfind` / `goto`
- `collect` / `pickup`
- `attack` / `retreat`
- `deposit` / inventory management
- `eat` / survival protection

## 恢复分级

1. 工具内部重试或换目标。
2. 局部子任务重规划。
3. 回到最近安全检查点。
4. 升级给大模型重新选择策略。

任何卡片不得允许无限重试。

## 输出

1. 新增 `knowledge/failures/*.json` 与 `knowledge/tool_guides/*.json`。
2. 每批不超过 20 条。
3. 运行 `python scripts/validate_knowledge.py`。
4. 写批次报告到 `reports/failure-tool-knowledge-YYYY-MM-DD.md`。
