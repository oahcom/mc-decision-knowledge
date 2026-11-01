# 项目初始化报告：2026-11-01

## 交付内容

- 建立项目 `mc-decision-knowledge`，覆盖策略、场景手册、失败恢复、工具契约和大模型决策启发五类知识。
- 定义 `knowledge-item.schema.json` 与 `source.schema.json`。
- 提供五类知识模板和来源模板。
- 实现标准库校验器 `scripts/validate_knowledge.py`。
- 提供 5 个单元测试，覆盖合法条目、高置信限制、未知来源、类型必填字段和目录归属。
- 预置 8 个候选来源，包括 Minecraft Wiki、Mineflayer、Baritone、Voyager、Mindcraft、MineDojo 和内部设计说明。
- 提供总控提示词和 5 个分阶段执行提示词，供其他模型接手采集与知识合成。

## 校验结果

- 单元测试：5 个全部通过。
- 来源记录：8 条。
- 知识条目：0 条。
- 校验错误：0。
- 警告：知识库为空，这是初始化阶段的预期状态。

## 下一步

1. 确认目标 Java 版本并写入 `project.json` 的 `target_game_version`。
2. 将 `prompts/00_master_prompt.md` 和 `prompts/01_source_collection.md` 交给执行模型。
3. 首批目标：新增 10 到 20 个高质量来源，不生成正式知识。
4. 第二批开始提取 `spawn_to_iron` 策略和场景手册。
5. 每批完成后运行校验器并写批次报告。
