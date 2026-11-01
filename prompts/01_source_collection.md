# 01 Source Collection Prompt：高质量来源采集

你负责为 MC 决策知识层采集公开来源。你只做来源登记，不生成正式知识条目。

## 输入

- 工作目录：`mc-decision-knowledge/`
- 现有来源：`sources/*.json`
- 来源模板：`templates/source.template.json`
- 合规规范：`docs/source-collection-policy.md`

## 优先来源顺序

1. 官方与权威文档：
   - Minecraft Wiki 协议、机制、教程页面。
   - 协议文档与版本说明。
2. 高质量开源项目：
   - PrismarineJS / Mineflayer 及其插件生态。
   - Baritone 寻路与挖矿系统。
   - MineDojo / Voyager。
   - Mindcraft 及其任务与提示词设计。
3. 公开技术讨论：
   - GitHub issue、PR、README、测试代码。
   - 公开论坛或社区中的技术帖。
4. AI 决策专项：
   - Minecraft LLM agent 论文、基准、任务定义、失败案例。
   - 技能库、自动课程、自验证、环境反馈机制。

## 建议搜索词

- `Minecraft Java Edition survival strategy version`
- `Minecraft iron mining strategy risk`
- `Mineflayer pathfinding failure`
- `Baritone dangerous blocks path cost`
- `Minecraft LLM agent skill library`
- `Minecraft agent benchmark tasks`
- `Minecraft bot task decomposition`
- `Minecraft survival first night checklist`
- `site:github.com minecraft LLM agent`
- `site:github.com mineflayer plugin`

社交平台搜索必须使用公开搜索入口或官方 API，不得绕过限制。

## 每条来源必须记录

按 `templates/source.template.json` 写入 `sources/`：

- `source_id`
- 标题与 URL
- 平台与来源类型
- 可靠性等级 A 到 D
- 许可证；不确定时写 `unknown_needs_verification`
- 采集时间
- 不超过 1200 字符的证据摘录
- 证据说明：它支撑什么决策问题
- 相关游戏版本
- 访问方式
- 合规声明，四项必须全部为 `true`

## 质量判断

一条来源值得保留，当且仅当它满足：

1. 能回答“什么时候做、为什么做、何时停止、失败怎么办”中的至少一问。
2. 能定位到具体页面、代码、issue 或章节。
3. 版本或适用范围可判断。
4. 不依赖无法核验的个人记忆。

## 放弃规则

遇到以下情况不要登记：

- 只有情绪评价，没有可执行信息。
- 与决策无关的纯百科事实。
- 无法回读原始页面的搜索摘要。
- 需要登录或绕过限制才能访问。
- 内容针对模组或服务器规则，与原版生存决策无关且未标明。

## 输出

1. 新增来源文件列表。
2. 每条来源的可靠性等级和适用主题。
3. 放弃的候选来源及原因。
4. 运行 `python scripts/validate_knowledge.py` 并汇报结果。
5. 将本批来源摘要写入 `reports/source-collection-YYYY-MM-DD.md`。
