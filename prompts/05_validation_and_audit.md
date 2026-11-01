# 05 Validation and Audit Prompt：质量校验与人工审计

你负责审计知识库质量。你不是新增知识的角色，而是发现和修复问题。

## 输入

- 校验器：`scripts/validate_knowledge.py`
- Schema：`schemas/`
- 知识库：`knowledge/`
- 来源库：`sources/`
- 批次报告：`reports/`

## 必做步骤

1. 运行：
   `python scripts/validate_knowledge.py --require-nonempty`
2. 运行单元测试：
   `python -m unittest discover -s scripts -p "test_*.py"`
3. 检查 ID 唯一性和文件归属目录。
4. 抽查每类知识至少 3 条，逐条打开来源验证：
   - 来源是否真实可访问。
   - 摘录是否支撑知识。
   - 版本是否匹配。
   - 证据类型是否正确。
5. 检查 `confidence: high` 是否全部具备 `replay_verified` 或 `human_verified`。
6. 检查是否有无上限重试、模糊建议或无成功条件的条目。
7. 检查社交来源是否符合 `docs/source-collection-policy.md`。

## 审计问题分级

- 阻断：引用不存在来源、伪造证据、版本错误、schema 失败。
- 严重：成功条件不可验证、失败恢复无上限、证据类型错误。
- 一般：描述模糊、标签错误、来源质量低但已标注。
- 建议：可补充的候选路线或反模式。

## 修复规则

- 阻断和严重问题必须修复后才能交付。
- 无法核实的知识降级为 `draft`、`confidence: low`，不要删除。
- 与新版本冲突的旧知识改为 `deprecated`，不要直接覆盖。
- 修复后必须重新运行校验器。

## 输出

写审计报告到 `reports/audit-YYYY-MM-DD.md`，包含：

1. 校验器和测试输出摘要。
2. 抽查条目清单。
3. 问题分级和修复结果。
4. 知识统计：
   - 按类型统计数量。
   - 按 `validation_status` 统计数量。
   - 按置信度统计数量。
5. 剩余风险和下一步建议。
