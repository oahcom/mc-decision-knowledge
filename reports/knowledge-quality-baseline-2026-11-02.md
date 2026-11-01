# 知识库质量基线：2026-11-02

## 自动检查

- 知识条目：60（strategy 12、playbook 6、failure_recovery 20、tool_guide 8、ai_heuristic 14）。
- 来源：36。
- 校验错误：0；单元测试：28 个通过。
- 验证状态：draft 44、source_verified 16；无 replay_verified 或 human_verified。
- 置信度：medium 56、low 4。
- 全部条目标记 26.3，共有 342 个来源引用。

## 主要风险

1. `src_minecraft_wiki_version` 被全部 60 条引用，只能支撑版本来源，不能支撑玩法结论。
2. Voyager 与 MineDojo 各被 33 条引用；Agent 架构和评测资料不能替代具体玩法证据。
3. 策略、手册、AI 启发共 32 条全部为 draft，核心决策知识尚未验证。
4. 工具指南依据外部项目 API，尚未映射到 Amaidesu 实际 MCP 工具。
5. 部分 draft 条目另有 `evidence_strength: high`，该自定义字段不能替代验证状态。

## 当前处置

不继续扩写或大规模精修。优先在 Amaidesu 上以 off/shadow/assist 模式接入并做在线对照，使用真实运行结果决定后续知识修复方向。
