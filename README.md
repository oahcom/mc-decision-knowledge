# MC Decision Knowledge

面向“dsv4.1 通过协议层玩 Minecraft”的决策知识层项目。项目目标不是搬运百科，而是沉淀可验证的玩家决策知识：什么时候选择什么路线、何时停止、失败如何恢复、大模型在特定状态下应该如何权衡。

## 当前范围

- 目标版本：Java 版 26.3（2026-11-01 确认的当前正式版）；具体游戏版本写入每条知识的 `game_versions`。
- 26.4 属于开发快照，不作为目标版本；未经确认不得写入版本专属结论。
- 首个里程碑：出生到铁器阶段。
- 默认验证状态：`draft`；只有来源核验、回放验证或人工验证后才可提升。
- 高置信知识只允许来自 `replay_verified` 或 `human_verified`。

## 目录结构

```text
mc-decision-knowledge/
├── project.json                 # 项目配置与质量门槛
├── schemas/                     # 知识与来源 JSON Schema
├── templates/                   # 五类知识与来源模板
├── knowledge/
│   ├── strategies/              # 阶段策略与路线选择
│   ├── playbooks/               # 高频场景手册
│   ├── failures/                # 失败诊断与恢复
│   ├── tool_guides/             # 工具使用契约
│   └── ai_heuristics/           # 面向大模型的决策启发
├── sources/                     # 来源证据记录
├── prompts/                     # 交给其他模型执行的分阶段提示词
├── scripts/                     # 校验脚本与测试
├── docs/                        # 采集规范与设计说明
└── reports/                     # 批次报告
```

## 质量规则

1. 每条知识必须引用至少一个 `source_id`。
2. 不允许无证据地把社区经验写成事实；无法核验的内容保留为 `draft` 和 `low`。
3. 版本冲突不合并，保留多条并标明适用版本。
4. 社交平台只采集公开内容，不绕过登录、验证码、速率限制或平台条款。
5. 不采集私人信息；作者信息只保留公开署名所必需的最小内容。
6. 每个批次完成后运行校验器，失败则先修复再进入下一批。

## 校验命令

```bash
python scripts/validate_knowledge.py
python scripts/validate_knowledge.py --require-nonempty
python scripts/audit_knowledge.py
python -m unittest discover -s scripts -p "test_*.py"
```

- `validate_knowledge.py`：字段契约校验（`schemas/` 是权威定义），失败返回非 0。
- `audit_knowledge.py`：跨文件语义审计，检查恢复阶梯完整性、失败卡之间的路由、错误码与来源的一致性、策略阈值标注、标签解析等。有发现时同样返回非 0，可作为批次闸门。
- 本环境只有 `python3`（WSL），上述命令请把 `python` 换成 `python3`。

## 交给其他模型时

优先把 `prompts/00_master_prompt.md` 作为总控提示词，再按阶段加载：

1. `01_source_collection.md`：采集与登记来源。
2. `02_strategy_extraction.md`：提取策略与场景手册。
3. `03_failure_and_tool_knowledge.md`：补失败恢复与工具契约。
4. `04_ai_decision_heuristics.md`：生成大模型专用决策启发。
5. `05_validation_and_audit.md`：校验、审计与批次报告。

不要让执行模型一次性完成全部阶段；每批建议 10 到 20 条知识，完成后必须校验。
