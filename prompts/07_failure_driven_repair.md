# 07 知识库提示词：基于在线失败的证据驱动修复

你负责在 Amaidesu 在线对照之后修复知识库。目标不是增加条目，而是消除已被真实运行证明的问题。每批最多修改 5 条知识。

## 输入

- `KB_ROOT`：知识库目录。
- 首轮 OFF/SHADOW/ASSIST 对照报告与原始日志。
- 实际 Amaidesu MCP 工具 schema、游戏/协议/组件版本。
- 当前 schema、校验器和测试。

如果缺少原始日志、成功判定或实际版本，停止修改正式知识，只报告缺口。

## 第一步：失败聚类与归因

按“任务 + 阶段 + 失败码 + 状态指纹 + 命中知识 + 恢复结果”聚类。每个待修问题必须关联至少一个可复现失败场景，并归入：知识缺失、知识错误、检索错误、状态错误、工具错误、模型错误或评测错误。

若主因不是知识，不修改知识条目；把问题转交对应模块。

## 第二步：写修复单

每条待修知识先写：

```text
knowledge_id:
failure_evidence: 原始日志与 run_id
failed_claim: 被失败推翻或缺失的具体结论
root_cause:
evidence_needed:
planned_change:
minimal_reproduction:
promotion_requirement:
rollback:
```

没有 `failed_claim` 和 `minimal_reproduction` 不得修改。

## 第三步：证据修复规则

1. 版本索引只能证明版本，从内容证据中剔除或单独标注为版本来源。
2. Voyager、MineDojo 等只能支撑其直接描述的架构、训练或评测内容，不能给具体玩法结论背书。
3. 外部 Mineflayer/Baritone 行为不得直接写成 Amaidesu MCP 契约；必须以本地实际 schema 和运行结果重新验证。
4. 一个来源只给其实际支持的 claim 引用，禁止为了增加可信度堆来源。
5. 来源只支持方向性经验时保持 `draft` 和合理低置信，不得标 `source_verified` 来掩盖未验证内容。
6. 所有数值阈值区分游戏规则与项目策略默认值；策略默认值必须可调。
7. 版本不匹配的知识不得改写成当前版本结论；保留版本边界或标记 deprecated。

## 第四步：修改与验证

- 每批最多 5 条，不做无关格式整理。
- 先保存最小复现和旧结果，再修改条目。
- 如需修改 schema、校验器或提示词，必须同步修改测试，不能静默增加字段。
- 运行：
  `python3 scripts/validate_knowledge.py --require-nonempty`
  `python3 -m unittest discover -s scripts -p "test_*.py"`
- 在同一失败场景回放，并在未参与修改的留出场景复测。

只有独立判定回放成功且适用版本一致，才可提升为 `replay_verified`。单次成功不得升级为高置信通用规则。

## 输出

写 `reports/knowledge-repair-YYYY-MM-DD.md`，包含：失败聚类、每条修复单、修改文件、校验结果、修复前后同场景结果、留出场景结果、回滚方法。若无提升，保留负结果并撤销未证实修改，不得只汇报成功样本。
