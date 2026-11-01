#!/usr/bin/env python3
"""登记「机制事实来源」与「作者自定阈值声明」。

本脚本是**幂等合并**：按 (field, value, context) 去重，重复运行不会破坏已有数据。
（早期版本直接覆盖 tunable_thresholds，单独重跑会抹掉后补的声明——那是真实的
可复现性陷阱，已修正。）

用法：
    python3 scripts/apply_thresholds.py
"""
import json
import pathlib

ROOT = pathlib.Path("/home/administrator/mc-decision-knowledge")

T = lambda field, value, context, reason: {
    "field": field, "value": value, "context": context, "reason": reason,
}

# 需要追加机制事实来源的条目
SOURCE_ADDS = {
    "failure_craft_missing_material": ["src_wiki_player_interaction_range"],
    "failure_craft_no_recipe": ["src_wiki_crafting_grid_size"],
    "failure_fall_interrupt": ["src_wiki_player_health"],
    "failure_food_insufficient": ["src_wiki_hunger_regen_threshold"],
    "failure_inventory_full": ["src_wiki_inventory_slots"],
    "failure_search_area_repeat": ["src_wiki_chunk_dimensions"],
    "failure_smelt_output_blocked": ["src_minecraftdata_items_id_map"],
    "failure_tool_broken_mid_task": ["src_minecraftdata_recipes_tool_chain"],
    "failure_tool_durability_low": ["src_minecraftdata_recipes_tool_chain"],
    "tool_collect_drops": ["src_wiki_inventory_slots"],
    "tool_craft_item": ["src_wiki_player_interaction_range", "src_wiki_crafting_grid_size"],
    "tool_eat_recover": ["src_wiki_hunger_regen_threshold", "src_wiki_inventory_slots"],
    "tool_inventory_deposit": ["src_wiki_player_interaction_range"],
    "tool_mine_block": ["src_wiki_tool_durability_uses"],
    "tool_smelt_item": ["src_wiki_player_interaction_range"],
}

# 作者自定阈值声明（field / value / context / reason）
TUNABLES = {
    "failure_combat_interrupt": [
        T(
            'summary',
            '60',
            '同一作业点 60 秒内出现两次以上伤害事件',
            '受伤事件统计窗口：作者自定的滚动窗口长度，游戏未规定该窗口',
        ),
        T(
            'success_condition',
            '60',
            '恢复后 60 秒内无伤害事件',
            '确认已脱离危险期的观察窗口：作者自定',
        ),
        T(
            'abort_condition',
            '10',
            '生命 < 10 直接撤退',
            '撤退生命阈值：按玩家 20 HP 上限取 50% 作为保守余量，作者自定',
        ),
        T(
            'abort_condition',
            '60',
            '同一作业点 60 秒内第二次被打断',
            '判定重复打断的统计窗口：作者自定',
        ),
        T(
            'diagnostics',
            '8',
            '检查 8 格内敌对实体数量与类型',
            '作业点敌对实体检查半径：作者自定的安全半径',
        ),
        T(
            'diagnostics',
            '60',
            '统计 60 秒内伤害事件次数',
            '统计窗口：作者自定',
        ),
    ],
    "failure_craft_missing_material": [
        T(
            'symptoms',
            '2',
            '材料数量比配方需求少 1~2 个',
            '材料缺口量：作者自定的轻微缺失判别容差（1~2 个属可容忍范围）',
        ),
    ],
    "failure_fall_interrupt": [
        T(
            'success_condition',
            '12',
            '生命恢复到 12 以上',
            '恢复目标生命值：按 20 HP 上限取 60%，作者自定',
        ),
        T(
            'trigger',
            '4',
            '生命在一次事件中下降 ≥ 4',
            '单次伤害事件判定为「坠落」的阈值：作者自定的检测门限，与「Y 坐标在 2 秒内下降 ≥ 4 格」共同构成坠落识别条件',
        ),
        T(
            'trigger',
            '4',
            'Y 坐标在 2 秒内下降 ≥ 4 格',
            '同上：位移判据中的坠落幅度门限',
        ),
        T(
            'trigger',
            '2',
            'Y 坐标在 2 秒内下降 ≥ 4 格',
            '同上：坠落检测的时间窗（2 秒），作者自定',
        ),
    ],
    "failure_food_insufficient": [
        T(
            'trigger',
            '3',
            '背包食物库存 < 3 份',
            '随身食物存量下限：作者自定的补给冗余量',
        ),
        T(
            'success_condition',
            '3',
            '食物库存 ≥ 3 份',
            '同上：补给冗余量',
        ),
        T(
            'symptoms',
            '1',
            '背包食物库存为 0 或仅剩 1 份',
            '「几乎耗尽」的相对判据：库存为 0 或仅剩 1 份即视为不可持续，是相对量而非外部事实',
        ),
        T(
            'symptoms',
            '0',
            '背包食物库存为 0 或仅剩 1 份',
            '同上：库存归零的相对判据',
        ),
    ],
    "failure_inventory_full": [
        T(
            'success_condition',
            '3',
            '空位 ≥ 3',
            '腾位目标：作者自定的最小冗余空位数',
        ),
        T(
            'diagnostics',
            '16',
            '检查附近 16 格内是否有可用容器',
            '容器搜索半径：作者自定',
        ),
        T(
            'recovery_steps',
            '3',
            '腾出 3 个空位',
            '同上：腾位目标',
        ),
        T(
            'trigger',
            '0',
            '背包空位为 0',
            '「背包已满」的相对判据：空位为 0 是满的定义本身，不是外部事实（槽位总数 36 见 src_wiki_inventory_slots）',
        ),
    ],
    "failure_lava_hazard": [
        T(
            'success_condition',
            '3',
            '脱离熔岩 3 格以上',
            '脱离熔岩的安全间距：作者自定',
        ),
        T(
            'success_condition',
            '12',
            '生命 ≥ 12',
            '恢复目标生命值：按 20 HP 上限取 60%，作者自定',
        ),
        T(
            'abort_condition',
            '8',
            '落入熔岩且生命 < 8',
            '放弃作业面的生命阈值：作者自定',
        ),
        T(
            'abort_condition',
            '1',
            '完成 1 轮恢复后再次出现',
            '升级到 L4 前的重试轮数上限：作者自定',
        ),
    ],
    "failure_night_exposure": [
        T(
            'trigger',
            '8',
            '8 格内出现敌对实体',
            '敌对实体告警半径：作者自定',
        ),
        T(
            'success_condition',
            '60',
            '连续 60 秒无受伤',
            '脱离危险期的观察窗口：作者自定',
        ),
        T(
            'success_condition',
            '8',
            '8 格内无敌对实体',
            '同上：安全半径',
        ),
        T(
            'abort_condition',
            '8',
            '生命 < 8 且无法封闭',
            '撤退生命阈值：作者自定',
        ),
        T(
            'diagnostics',
            '8',
            '统计 8 格内敌对实体数量',
            '同上：检查半径',
        ),
        T(
            'recovery_steps',
            '3',
            '就地立柱（≥3 格高）',
            '临时庇护的立柱高度：作者自定',
        ),
        T(
            'recovery_steps',
            '2',
            '横向挖进 2 格做临时避难',
            '临时避难的挖掘深度：作者自定',
        ),
        T(
            'recovery_steps',
            '1000',
            '日落前 1000 tick 开始返程',
            '返程提前量：作者自定的 tick 预算',
        ),
    ],
    "failure_path_no_path": [
        T(
            'abort_condition',
            '12',
            '生命 < 12 时不继续尝试',
            '最低生命值：作者自定',
        ),
        T(
            'recovery_steps',
            '2',
            '把目标降级为 ±2 格容差',
            '目标降级容差：作者自定',
        ),
        T(
            'recovery_steps',
            '1',
            '只允许 1 次',
            '同层重试次数上限：作者自定',
        ),
        T(
            'recovery_steps',
            '32',
            '先接近到 32 格内再重新规划',
            '预接近距离：作者自定',
        ),
    ],
    "failure_path_stuck": [
        T(
            'trigger',
            '5',
            '5 秒内净位移',
            '卡住判定的观察窗口：作者自定',
        ),
        T(
            'trigger',
            '0.5',
            '净位移 < 0.5 格',
            '卡住判定的位移阈值：作者自定',
        ),
        T(
            'actions',
            '5',
            '统计 5 秒位移',
            '统计窗口：作者自定',
        ),
        T(
            'success_condition',
            '20',
            '连续 20 tick 净位移',
            '确认已脱离卡点的观察窗口：作者自定（20 tick 约合 1 秒）',
        ),
        T(
            'success_condition',
            '0.1',
            '净位移 > 0.1 格',
            '确认已脱离卡点的位移阈值：作者自定',
        ),
        T(
            'abort_condition',
            '10',
            '生命 < 10',
            '放弃重试的生命阈值：作者自定',
        ),
        T(
            'risk_notes',
            '5',
            '持续按住前进超过 5 秒',
            '无效操作的时间上限：作者自定',
        ),
        T(
            'diagnostics',
            '5',
            '统计 5 秒窗口内的位移向量',
            '统计窗口：作者自定',
        ),
        T(
            'symptoms',
            '5',
            '5 秒内净位移',
            '判定窗口：作者自定',
        ),
        T(
            'symptoms',
            '0.5',
            '净位移小于 0.5 格',
            '位移阈值：作者自定',
        ),
        T(
            'recovery_steps',
            '8',
            '绕行 8 格',
            '替代路线的绕行偏移距离：作者自定',
        ),
    ],
    "failure_path_thrash_reset": [
        T(
            'trigger',
            '10',
            '10 秒内 path_reset 次数',
            '重置抖动的统计窗口：作者自定',
        ),
        T(
            'trigger',
            '5',
            '次数 ≥ 5',
            '判定为抖动的重置次数阈值：作者自定',
        ),
        T(
            'trigger',
            '8',
            '净位移 < 8 格',
            '有效推进的位移阈值：作者自定',
        ),
        T(
            'actions',
            '10',
            '统计 10 秒窗口内的重置次数',
            '统计窗口：作者自定',
        ),
        T(
            'success_condition',
            '10',
            '10 秒内 path_reset',
            '统计窗口：作者自定',
        ),
        T(
            'success_condition',
            '1',
            'path_reset ≤ 1',
            '可接受的单次重置数：作者自定',
        ),
        T(
            'success_condition',
            '8',
            '净位移 > 8 格',
            '有效推进的位移阈值：作者自定',
        ),
        T(
            'diagnostics',
            '10',
            '统计 10 秒窗口的重置次数',
            '统计窗口：作者自定',
        ),
        T(
            'symptoms',
            '10',
            '10 秒内 path_reset',
            '统计窗口：作者自定',
        ),
        T(
            'symptoms',
            '5',
            '出现 5 次以上',
            '重置次数阈值：作者自定',
        ),
        T(
            'diagnostics',
            '0',
            '净位移几乎为 0',
            '区分「卡住」与「抖动」的相对判据：净位移几乎为 0 表示原地不动，是相对量而非外部事实',
        ),
    ],
    "failure_plan_stale": [
        T(
            'diagnostics',
            '10',
            '列出最近 10 个状态变更事件',
            '回溯窗口的事件条数：作者自定',
        ),
    ],
    "failure_repeat_same_failure": [
        T(
            'trigger',
            '3',
            '出现 ≥3 次',
            '判定为重复失败的次数阈值：作者自定',
        ),
        T(
            'success_condition',
            '10',
            '10 分钟内不再复现',
            '静默期长度：作者自定',
        ),
    ],
    "failure_search_area_repeat": [
        T(
            'trigger',
            '200',
            '最近 200 步内区块去重率',
            '去重率统计窗口（步数）：作者自定',
        ),
        T(
            'trigger',
            '30',
            '去重率低于 30%',
            '区块去重率下限：作者自定',
        ),
        T(
            'actions',
            '200',
            '计算最近 200 步的区块去重率',
            '统计窗口：作者自定',
        ),
        T(
            'success_condition',
            '80',
            '新区块访问率 ≥ 80%',
            '可接受的重复率上限（重复率需低于 20%）：作者自定',
        ),
        T(
            'diagnostics',
            '3',
            '抽查 3 个重复区块',
            '抽查样本量：作者自定',
        ),
        T(
            'symptoms',
            '200',
            '最近 200 步的区块去重率',
            '统计窗口：作者自定',
        ),
        T(
            'symptoms',
            '30',
            '去重率低于 30%',
            '去重率下限：作者自定',
        ),
        T(
            'recovery_steps',
            '1',
            '允许 1 次',
            '同层重试次数上限：作者自定',
        ),
        T(
            'recovery_steps',
            '16',
            '固定步长 16 格',
            '条带式扫描的单步步长：作者自定',
        ),
    ],
    "failure_search_no_progress": [
        T(
            'trigger',
            '1200',
            '1200 tick 内没有增长',
            '无进展判定的观察窗口：作者自定',
        ),
        T(
            'preconditions',
            '1200',
            '运行足够长的窗口（≥1200 tick）',
            '同上：观察窗口',
        ),
        T(
            'diagnostics',
            '1200',
            '统计 1200 tick 内有效搜索时间',
            '统计窗口：作者自定',
        ),
        T(
            'diagnostics',
            '1',
            '确认背包空位 ≥ 1',
            '最小空位要求：作者自定',
        ),
        T(
            'symptoms',
            '1200',
            '1200 tick 内零增长',
            '观察窗口：作者自定',
        ),
        T(
            'recovery_steps',
            '32',
            '单次移动 32~64 格后重新采样',
            '重采样的位移下限：作者自定',
        ),
        T(
            'recovery_steps',
            '64',
            '单次移动 32~64 格后重新采样',
            '重采样的位移上限：作者自定',
        ),
        T(
            'recovery_steps',
            '1',
            '同一策略只允许 1 次',
            '同策略重试上限：作者自定',
        ),
        T(
            'diagnostics',
            '0',
            '命中为 0',
            '「未命中」的相对判据：命中数为 0 表示目标资源未获得，是相对量而非外部事实',
        ),
        T(
            'symptoms',
            '0',
            '目标命中数为 0',
            '同上：目标命中数为 0 的相对判据',
        ),
        T(
            'possible_causes',
            '0',
            '有效新区域接近 0',
            '同上：有效新区域接近 0 表示搜索没有推进到新区域，是相对量',
        ),
    ],
    "failure_smelt_fuel_starved": [
        T(
            'recovery_steps',
            '1.5',
            '按缺口 ×1.5 一次性追加燃料',
            '燃料追加的冗余系数：作者自定',
        ),
        T(
            'trigger',
            '0',
            'furnace.fuel 归零或接近 0',
            '「燃料耗尽」的相对判据：fuel 归零即燃料烧完，由熔炉状态自洽推出，不是外部事实',
        ),
        T(
            'success_condition',
            '0',
            '差额为 0',
            '「产物与期望一致」的相对判据：差额为 0 即完全吻合，是相对量',
        ),
        T(
            'diagnostics',
            '0',
            'fuel 仍大于 0',
            '同上：fuel 未归零即不属燃料耗尽，是相对量',
        ),
        T(
            'symptoms',
            '0',
            'furnace.fuel 为 0',
            '同上：fuel 归零是燃料耗尽的判据',
        ),
    ],
    "failure_smelt_output_blocked": [
        T(
            'recovery_steps',
            '16',
            '改为分批冶炼（每批 ≤16）',
            '单批冶炼上限：作者自定',
        ),
        T(
            'diagnostics',
            '0',
            'furnace.fuel 已归零',
            '区分「燃料耗尽」与「输出槽满」的相对判据：fuel 归零归前卡，是相对量',
        ),
        T(
            'diagnostics',
            '0',
            'fuel > 0',
            '同上：fuel 未归零且输出槽非空才归本卡，是相对量',
        ),
        T(
            'diagnostics',
            '0',
            '确认 fuel 仍大于 0',
            '区分「燃料耗尽」与「输出槽满」的相对判据：确认 fuel 未归零才归本卡，是相对量而非外部事实',
        ),
    ],
    "failure_state_desync_inventory": [
        T(
            'trigger',
            '2',
            '两次读取（间隔 ≥2 tick）结果不同',
            '重读间隔：作者自定（2 tick 便于等待一帧服务端状态更新）',
        ),
        T(
            'symptoms',
            '2',
            '间隔 ≥2 tick 的两次背包读取结果不一致',
            '重读间隔：作者自定',
        ),
        T(
            'recovery_steps',
            '2',
            '间隔 ≥2 tick 重读 1 次',
            '重读间隔：作者自定',
        ),
        T(
            'recovery_steps',
            '1',
            '重读 1 次',
            '重读次数上限：作者自定',
        ),
        T(
            'recovery_steps',
            '1',
            '移动到掉落物 1 格内重新拾取',
            '拾取接近距离：作者自定',
        ),
        T(
            'success_condition',
            '0',
            '差额为 0',
            '「读取一致」的相对判据：实际数量与目标差额为 0 即完全吻合，是相对量而非外部事实',
        ),
    ],
    "failure_tool_broken_mid_task": [
        T(
            'recovery_steps',
            '2',
            '至少带 2 把工具',
            '工具备份数量：作者自定',
        ),
        T(
            'success_condition',
            '0',
            '耐久 > 0',
            '「工具仍可用」的相对判据：耐久大于 0 即未损坏，是相对量',
        ),
        T(
            'symptoms',
            '0',
            '背包同类工具数量为 0',
            '「无备用工具」的相对判据：同类工具数量为 0 即无备选，是相对量',
        ),
    ],
    "failure_tool_durability_low": [
        T(
            'trigger',
            '120',
            '任务所需消耗的 120%',
            '耐久冗余倍数：作者自定的策略阈值',
        ),
        T(
            'success_condition',
            '120',
            '任务所需消耗的 120%',
            '耐久冗余倍数：作者自定的策略阈值',
        ),
        T(
            'abort_condition',
            '5',
            '耐久 < 5% 时强制中断',
            '强制中断的耐久线：作者自定',
        ),
        T(
            'risk_notes',
            '5',
            '耐久低于 5% 时继续开采',
            '强制中断的耐久线：作者自定',
        ),
        T(
            'symptoms',
            '15',
            '装备耐久低于 15%',
            '预警耐久线：作者自定',
        ),
        T(
            'recovery_steps',
            '2',
            '补足至少 2 把工具',
            '工具备份数量：作者自定',
        ),
        T(
            'diagnostics',
            '0',
            '装备仍存在且耐久 > 0',
            '区分「耐久偏低」与「已损坏」的相对判据：耐久大于 0 且装备仍存在即归本卡，是相对量',
        ),
    ],
    "tool_collect_drops": [
        T(
            'preconditions',
            '1',
            '背包至少 1 个空位',
            '最小空位要求：作者自定',
        ),
        T(
            'abort_condition',
            '2',
            '单个掉落物绕行超过 2 次',
            '单件掉落物的绕行次数上限：作者自定',
        ),
        T(
            'parameters',
            '8',
            '搜索半径（格），默认 8',
            '工具参数的初始值（默认搜索半径）：作者可调',
        ),
        T(
            'parameters',
            '8000',
            '默认 8000',
            '工具参数的初始值（默认超时）：作者可调',
        ),
        T(
            'parameters',
            '2',
            '背包确认读取次数，默认 2',
            '工具参数的初始值（确认读取次数）：作者可调',
        ),
        T(
            'parameters',
            '2',
            '间隔 ≥2 tick',
            '确认读取的间隔：作者自定',
        ),
        T(
            'verification',
            '2',
            '间隔 ≥2 tick 的两次读取结果一致',
            '确认读取的间隔：作者自定',
        ),
        T(
            'verification',
            '2',
            '间隔 ≥2 tick',
            '两次读取的最小间隔：作者自定的确认等待步长',
        ),
    ],
    "tool_combat_engage_retreat": [
        T(
            'preconditions',
            '12',
            '生命 ≥ 12',
            '开战的最低生命线：作者自定',
        ),
        T(
            'preconditions',
            '10',
            '武器耐久 > 10%',
            '开战的最低武器耐久线：作者自定',
        ),
        T(
            'success_condition',
            '8',
            '与最近敌对实体距离 > 8',
            '判定已脱离的交战距离：作者自定',
        ),
        T(
            'success_condition',
            '5',
            '5 秒内未受伤',
            '确认已脱离的观察窗口：作者自定',
        ),
        T(
            'abort_condition',
            '10',
            '生命 < 撤退阈值（默认 10',
            '撤退生命阈值：作者自定',
        ),
        T(
            'abort_condition',
            '12',
            '10~12 区间不得重新开战',
            '滞回带的上界：与开战生命线一致，作者自定',
        ),
        T(
            'abort_condition',
            '20',
            '护甲耐久 < 20%',
            '撤退的护甲耐久线：作者自定',
        ),
        T(
            'abort_condition',
            '3',
            '被 3 个以上敌对实体包围',
            '判定被包围的敌对实体数：作者自定',
        ),
        T(
            'abort_condition',
            '15000',
            '默认 15000',
            '工具参数的初始值（交战超时）：作者可调',
        ),
        T(
            'parameters',
            '10',
            '撤退生命阈值，默认 10',
            '工具参数的初始值：作者可调',
        ),
        T(
            'parameters',
            '8',
            '最大追击距离，默认 8',
            '工具参数的初始值：作者可调',
        ),
        T(
            'parameters',
            '15000',
            '默认 15000',
            '工具参数的初始值：作者可调',
        ),
        T(
            'verification',
            '8',
            '最近敌对实体距离 > 8',
            '判定已脱离的交战距离：作者自定',
        ),
    ],
    "tool_craft_item": [
        T(
            'risk_notes',
            '2',
            '背包空位 < 2 时不要合成多产物配方',
            '合成所需的最小空位：作者自定',
        ),
        T(
            'parameters',
            '5000',
            '默认 5000',
            '工具参数的初始值（合成超时）：作者可调',
        ),
    ],
    "tool_eat_recover": [
        T(
            'abort_condition',
            '4000',
            '默认 4000',
            '工具参数的初始值（进食超时）：作者可调',
        ),
        T(
            'parameters',
            '4000',
            '默认 4000',
            '工具参数的初始值：作者可调',
        ),
        T(
            'success_condition',
            '1',
            '食物计数 -1',
            '进食一次使食物计数减 1，是动作自身的相对变化量，非外部事实',
        ),
        T(
            'verification',
            '1',
            '食物物品计数 -1',
            '同上：进食一次使计数减 1',
        ),
        T(
            'verification',
            '0',
            '进食窗口内受伤事件数为 0',
            '「进食期间未受伤」的相对判据：受伤事件数为 0 即全程安全，是相对量',
        ),
        T(
            'expected_effects',
            '1',
            '食物计数 -1',
            '同上：进食一次使食物计数减 1',
        ),
    ],
    "tool_inventory_deposit": [
        T(
            'parameters',
            '6000',
            '默认 6000',
            '工具参数的初始值（存取超时）：作者可调',
        ),
    ],
    "tool_mine_block": [
        T(
            'preconditions',
            '8',
            '8 格内无敌对实体',
            '挖掘作业的安全半径：作者自定',
        ),
        T(
            'abort_condition',
            '1.5',
            'digTime×1.5',
            '挖穿超时相对 digTime 的冗余系数：作者自定',
        ),
        T(
            'abort_condition',
            '8',
            '生命 < 8 或食物 < 6',
            '放弃挖掘的生命阈值：作者自定',
        ),
        T(
            'parameters',
            '1.5',
            'digTime×1.5',
            '工具参数的初始值：作者可调',
        ),
        T(
            'preconditions',
            '1',
            '剩余耐久 ≥ 1',
            '「工具仍可使用」的相对判据：剩余耐久至少 1 点即可挖，是相对量（每点耐久的实际价值见 src_wiki_tool_durability_uses）',
        ),
        T(
            'preconditions',
            '1',
            '背包至少 1 个空位',
            '「有地方放掉落物」的相对判据：至少 1 个空位即可，是相对量（槽位总数见 src_wiki_inventory_slots）',
        ),
        T(
            'expected_effects',
            '1',
            '每块 1 点',
            '每次破坏方块扣 1 点耐久：由 Durability 页的「N uses」以「次」为单位计数得出，见 src_wiki_tool_durability_uses 的 derived_values',
        ),
    ],
    "tool_pathfind_goto": [
        T(
            'preconditions',
            '12',
            '生命 ≥ 12',
            '长距离移动的最低生命线：作者自定',
        ),
        T(
            'preconditions',
            '8',
            '食物 ≥ 8',
            '长距离移动的最低食物线：作者自定',
        ),
        T(
            'risk_notes',
            '12',
            '生命 < 12',
            '禁止最大速度路线的生命线：作者自定',
        ),
        T(
            'parameters',
            '1',
            '到达判定容差（格），默认 1',
            '工具参数的初始值（到达容差）：作者可调',
        ),
        T(
            'verification',
            '0.1',
            '净位移 > 0.1 格',
            '排除路径抖动所需的最小位移：作者自定',
        ),
    ],
    "tool_smelt_item": [
        T(
            'parameters',
            '2000',
            '单件冶炼时间 + 2000',
            '工具参数的初始值（冶炼超时余量）：作者可调',
        ),
        T(
            'verification',
            '2',
            '间隔 ≥2 tick 两次读取',
            '确认读取的间隔：作者自定',
        ),
        T(
            'verification',
            '0',
            'furnace.fuel 处于 [0,1]',
            '熔炉 fuel 进度值域 [0,1] 是相对量（0 = 尚未开始、1 = 冶炼完成），由熔炉当前进度自洽推出，不是外部事实',
        ),
    ],
}


def main() -> int:
    changed = 0
    for p in sorted((ROOT / "knowledge").glob("*/*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        k = d["id"]
        touched = False

        adds = SOURCE_ADDS.get(k, [])
        if adds:
            refs = list(d.get("source_refs", []))
            for a in adds:
                if a not in refs:
                    refs.append(a)
                    touched = True
            d["source_refs"] = refs

        tunes = TUNABLES.get(k)
        if tunes:
            existing = d.get("tunable_thresholds") or []
            seen = {(x.get("field"), x.get("value"), x.get("context")) for x in existing}
            merged = list(existing)
            for t in tunes:
                key = (t["field"], t["value"], t["context"])
                if key in seen:
                    continue
                seen.add(key)
                merged.append(t)
            if len(merged) != len(existing):
                d["tunable_thresholds"] = merged
                touched = True

        if touched:
            p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            changed += 1
    print(f"共更新 {changed} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
