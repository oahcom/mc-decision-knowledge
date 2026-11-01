# 04 AI Decision Heuristics Prompt：大模型专用决策启发

你负责生成 `ai_heuristic` 知识。这不是普通攻略，而是帮助 dsv4.1 在特定状态下做出更好选择的规则。

## 输入

- 模板：`templates/ai-heuristic.template.json`
- 内部设计来源：`src_internal_design`
- 已有知识：`knowledge/strategies/`、`knowledge/playbooks/`、`knowledge/failures/`
- 外部 AI 项目来源：Voyager、MineDojo、Mindcraft 等。

## 生成前检查

先确认：

1. 已有策略和失败知识覆盖当前主题。
2. 状态特征可以由协议层获得。
3. 启发规则可以转成计划或重规划条件。
4. 不依赖视觉信息，除非明确标注为不可用状态。

## 每条 AI 启发必须包含

1. `decision_rule`：一句话可执行规则。
2. `state_features`：决策需要的最小状态集合。
3. `alternative_comparison`：候选方案之间的收益、成本和风险。
4. `anti_patterns`：模型容易犯的错误。
5. `model_guidance`：给模型的明确操作指导。
6. `abort_condition`：何时停止或重规划。
7. `source_refs`：至少一个来源。

## 优先主题

### 安全与风险

- 生命、食物、装备、退路不满足时优先恢复安全。
- 深入探索前的保守基线。
- 危险事件抢占后如何恢复任务。

### 路线选择

- 洞穴探索与分支挖矿的比较。
- 继续搜索与更换区域的判断。
- 探索收益递减时的停止条件。

### 计划质量

- 状态不完整时不要生成计划。
- 计划必须有短检查点。
- 旧状态版本上的计划必须废弃。
- 输出成功条件，而不是口头描述。

### 失败恢复

- 相同失败不要用相同方式重试。
- 区分工具失败、状态错误和策略错误。
- 达到恢复上限后必须升级。

### 模型自我约束

- 不确定时选择保守计划。
- 不把一次成功当成普适规律。
- 不为完成任务而忽略安全条件。
- 不把推测写成事实。

## 证据规则

- 来自内部架构的规则引用 `src_internal_design`，`evidence_type` 使用 `ai_synthesis`。
- 来自 Voyager、MineDojo、Mindcraft 等项目的经验，必须引用对应外部来源。
- 未经回放验证的启发只能是 `draft` 或 `source_verified`，置信度不得为 `high`。

## 输出

1. 新增 `knowledge/ai_heuristics/*.json`。
2. 每批不超过 15 条。
3. 运行 `python scripts/validate_knowledge.py`。
4. 写批次报告到 `reports/ai-heuristics-YYYY-MM-DD.md`。
5. 明确列出每条启发需要什么回放实验才能升级。
