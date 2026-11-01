# Amaidesu 接入提示词：知识层与在线对照评测

你在另一台电脑上工作。目标是把 `mc-decision-knowledge` 以**可关闭、可追踪、可对照**的方式接入 Amaidesu 的 Minecraft Agent，并完成在线 A/B 评测。不要继续扩写知识库，不要先做大规模重构。

## 输入与事实边界

- `KB_ROOT`：知识库目录，包含 `knowledge/`、`sources/`、`scripts/validate_knowledge.py`。
- `AMAIDESU_ROOT`：Amaidesu 本地仓库。
- 知识库当前为候选质量：60 条知识、36 个来源；44 条 `draft`，16 条 `source_verified`，没有回放或人工验证条目。
- 策略、场景手册、AI 启发全部仍为 `draft`。`src_minecraft_wiki_version` 只能证明版本，不能证明玩法结论；Voyager/MineDojo 不能替代具体玩法证据。
- 工具指南主要参考 Mineflayer/Baritone，不等于 Amaidesu 当前 MCP 工具契约。
- 公开资料只用于定位代码；**本地 Amaidesu 代码、配置和实际 MCP schema 是唯一接入事实源**。

## 第一阶段：只读定位，先交接口图

先阅读本地架构文档和 Minecraft Agent 相关代码，定位并报告：

1. Minecraft Agent 的任务循环、规划器、提示词组装位置。
2. 游戏状态结构、失败码、任务状态和状态版本来源。
3. ToolRegistry、ToolSpec、MCP 工具列表及实际参数/返回 schema。
4. 配置加载方式、日志方式、`game.report` 或对应完成事件。
5. 本地危险保护和中断处理位置。
6. 实际游戏、服务端、协议、MaiCraftMod/相关组件版本；不得因为知识库写 26.3 就假定运行环境是 26.3。

输出 `reports/amaidesu-interface-map.md`，列出真实文件路径、类/函数、数据流和最小接入点。没有完成接口图前，不改业务代码。

## 第二阶段：实现只读 KnowledgeProvider

在 Minecraft Agent 侧增加独立只读 provider，禁止修改工具行为，禁止把知识注入主播 Planner 或本地即时保护循环。

必须支持：

- `mode=off|shadow|assist`，默认 `off`；配置变更无需改代码。
- 按 `game_version + stage/goal + state_features + failure_code` 检索；版本不匹配不返回。
- 每次最多返回：1 条 strategy、1 条 playbook、2 条 failure_recovery、1 条 ai_heuristic；初始总预算不超过 1500 tokens，可配置。
- 不新增 LLM 调用；本地加载和检索，记录检索耗时。
- 返回 `knowledge_id`、类型、验证状态、来源、命中原因和内容哈希，形成完整 retrieval trace。
- `off`：不检索、不注入。
- `shadow`：检索并记录，但不改变模型输入，用于检查命中率与开销。
- `assist`：只把命中的知识作为“带验证状态的候选建议”注入 Minecraft Agent 规划/恢复上下文，不得写成游戏事实。
- 模型上下文缺少必要状态时返回空结果，不猜测补齐。
- 版本索引、内部架构来源不得被当作玩法证据；无法映射到实际 MCP schema 的 tool_guide 字段不得进入执行约束。

建议接口（按本地代码风格适配，不要机械照搬）：

```text
retrieve(game_version, stage, goal, state_features, failure_code=None)
  -> {items, trace, retrieval_ms}
```

至少添加这些测试：off 不读取、shadow 不注入、assist 才注入、版本不匹配为空、draft 有明确标记、超预算截断、缺状态为空、检索 trace 完整、无效 JSON 不导致游戏循环崩溃。

## 第三阶段：在线对照评测

只在私有测试服和专用测试世界运行；先备份测试世界，不连接公共服务器。固定代码版本、模型、temperature、工具版本、游戏/协议版本和初始物品。使用相同种子做配对运行。

### 模式

1. `off`：基线。
2. `shadow`：确认检索不会改变行为，只增加可测量的小额本地开销。
3. `assist`：知识辅助。

### 首批任务

- 获得石质工具并制作熔炉。
- 首次夜晚存活并形成可用庇护。
- 获得 3 个铁锭并制作铁镐。
- 注入失败场景：路径卡住、背包满、工具损坏、危险中断、状态过期。

每个任务必须预先写出游戏状态可判定的成功条件和超时条件。先跑少量冒烟测试确认日志与判定正确，再扩大配对种子数；开发种子与最终留出种子分离。

### 每次运行必须记录

`run_id`、模式、种子、代码提交、配置哈希、模型与采样参数、游戏/协议/组件版本、命中知识 ID、成功/失败、实际耗时、死亡、无效工具调用、重复失败、恢复结果、LLM 调用数、tokens、规划延迟、检索耗时。

成功只能由游戏状态或独立检查器判定，不能采用模型自述。

## 验收与回滚

- `off` 与 `shadow` 的行为应一致；若不同，先修实验隔离。
- 所有 provider 测试通过；知识检索异常不能导致主任务崩溃。
- `assist` 不得降低危险场景安全性；若在留出种子上没有改善成功率、重复失败或恢复率中的至少一项，保持 `off`，如实报告负结果。
- 不得通过删除失败样本、挑选成功种子或修改成功定义制造提升。
- 报告必须给出可复现命令、原始日志路径、按任务分组的 OFF/SHADOW/ASSIST 对比和回滚方法。

## 最终交付

1. 接口图。
2. 最小代码差异和测试。
3. 配置文件示例（不包含密钥）。
4. 在线对照原始日志与汇总报告。
5. 明确结论：启用、继续 shadow，还是回滚；不得只凭观看少量运行视频宣布成功。
