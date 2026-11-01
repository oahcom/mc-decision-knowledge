# Amaidesu 双机交接说明

## 当前优先级

1. 在 Amaidesu 电脑上完成只读接口定位。
2. 接入 `off / shadow / assist` 三模式 KnowledgeProvider。
3. 在这台游戏电脑上使用私有测试世界做配对在线对照。
4. 知识库精修暂缓，不用新增条目数量作为验收。

## 当前知识库结论

结构完整，但仍是候选库：60 条知识、36 个来源，校验器无错误，28 个测试通过；44 条为 `draft`，没有回放验证。核心策略、手册和 AI 启发全部是 `draft`，不能直接当成已验证运行时规则。

## 迁移后使用

设置两个路径变量：

```bash
export KB_ROOT=/path/to/mc-decision-knowledge
export AMAIDESU_ROOT=/path/to/Amaidesu
```

先运行：

```bash
cd "$KB_ROOT"
python3 scripts/validate_knowledge.py
python3 -m unittest discover -s scripts -p "test_*.py"
```

然后把 `prompts/06_amaidesu_integration_eval.md` 整体交给另一台电脑上的执行模型。要求它先交接口图，再做最小接入，不在不了解本地代码的情况下修改任务循环或工具。

## 游戏电脑注意事项

- 先核实实际服务端、协议和组件版本，不能默认与知识库的 26.3 一致。
- 使用私有测试服和专用测试世界，运行前备份。
- 固定种子、初始状态、模型与工具配置，按 OFF/SHADOW/ASSIST 配对运行。
- 保留原始日志和成功判定器输出，不用模型自述或人工观感作为成功证据。
