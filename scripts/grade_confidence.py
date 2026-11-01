#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按证据构成计算两个正交的等级，并校验已写入的值与计算结果一致。

为什么是两个字段而不是一个
--------------------------
`project.json` 的 knowledge_policy 明确声明：
    "allowed_high_confidence_only_after": "replay_verified"

也就是说 confidence 在本项目里是**信任等级**——它被评审进度闸门约束。
把它重新定义为「证据强度」会让 34 条 draft 条目拿到 high，直接违反项目策略。

因此把两个维度拆开：

- **confidence**（信任等级）= 评审进度闸门 × 证据强度：
    过闸门（replay_verified / human_verified）→ 由证据强度定档；
    未过闸门 → 最高只能 medium，证据最弱的为 low。
- **evidence_strength**（证据强度）= 纯由来源构成推导，不受评审进度影响。

原状态是 60 条 confidence 全为 medium——零方差字段不区分任何条目，
下游读成「都已评估过、结论都是中等可信」，实际上什么都没说。
区分度现在由 evidence_strength 承担，confidence 则严格守住项目策略。

评分规则
--------
证据类型基分（entry 的主证据强度）:
    official_document 3 | code_behavior 3 | community_consensus 2
    expert_heuristic 1 | ai_synthesis 0

来源构成加分（每类至多 +1，反映「有��种独立支撑」）:
    official_document 来源 +1
    source_code / github_repository / issue_or_pr 来源 +1
    community_wiki 来源 +1
    research_paper / benchmark 来源 +1

来源可靠性扣分（取所引来源里最低的一档）:
    全部 A +0 | 最低 B −1 | 最低 C −2 | 最低 D −3

内���设计依赖扣分:
    若 source_refs 里含 internal_design 且不含任何 community_wiki 来源 −1
    （内部设计本���是方法论骨架，没有社区/官方事实交叉时不可独立支撑结论）

evidence_strength 分档: ≥5 → high | 3–4 → medium | ≤2 → low

confidence 分档（在 evidence_strength 之上叠加项目策略闸门）:
    validation_status ∈ {replay_verified, human_verified} → 同 evidence_strength
    否则                                        → 最高 medium；证据最弱者为 low

用法:
    python3 scripts/grade_confidence.py [--apply] [--root .]
    --apply  把算出的 confidence / evidence_strength 写回条目
退出码: 0 = 全部条目已写入且与计算一致, 1 = 存在不一致
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TYPE_BASE = {
    "official_document": 3,
    "code_behavior": 3,
    "community_consensus": 2,
    "expert_heuristic": 1,
    "ai_synthesis": 0,
}

FACT_SOURCE_TYPES = {"official_document"}
CODE_SOURCE_TYPES = {"source_code", "github_repository", "issue_or_pr"}
WIKI_SOURCE_TYPES = {"community_wiki"}
PAPER_SOURCE_TYPES = {"research_paper", "benchmark"}
INTERNAL_SOURCE_TYPES = {"internal_design"}

REL_PENALTY = {"A": 0, "B": -1, "C": -2, "D": -3}


def grade(item: dict, sources: dict[str, dict]) -> tuple[str, str, int, list[str]]:
    """返回 (confidence, evidence_strength, 分数, 评分明细)。"""
    notes: list[str] = []
    et = item.get("evidence_type", "ai_synthesis")
    score = TYPE_BASE.get(et, 0)
    notes.append(f"证据类型 {et} 基分 {score}")

    cited = [sources[r] for r in item.get("source_refs", []) if r in sources]
    types = {s["source_type"] for s in cited}

    def bonus(group: set[str], label: str) -> None:
        nonlocal score
        if types & group:
            score += 1
            notes.append(f"有 {label} 来源 +1")

    bonus(FACT_SOURCE_TYPES, "官方文档")
    bonus(CODE_SOURCE_TYPES, "代码/issue")
    bonus(WIKI_SOURCE_TYPES, "社区 wiki")
    bonus(PAPER_SOURCE_TYPES, "论文/基准")

    if cited:
        worst = min(s.get("reliability", "C") for s in cited)
        pen = REL_PENALTY.get(worst, -2)
        score += pen
        notes.append(f"最低来源可靠性 {worst} {pen:+d}")

    if types & INTERNAL_SOURCE_TYPES and not (types & WIKI_SOURCE_TYPES):
        score -= 1
        notes.append("依赖内部设计且无社区 wiki 交叉 −1")

    strength = "high" if score >= 5 else "medium" if score >= 3 else "low"

    # 项目策略闸门：confidence 是信任等级，high 只有过评审闸门才允许
    reviewed = item.get("validation_status") in ("replay_verified", "human_verified")
    if reviewed:
        conf = strength
    elif strength == "low":
        conf = "low"
    else:
        conf = "medium"
    notes.append(
        f"confidence {conf}（评审状态 {item.get('validation_status')}，"
        f"{'已过闸门' if reviewed else '未过 replay_verified 闸门，最高 medium'}）"
    )
    return conf, strength, score, notes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    root = Path(args.root)

    sources = {}
    for p in sorted((root / "sources").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        sources[d["source_id"]] = d

    mismatches = []
    dist: dict[str, int] = {}
    sdist: dict[str, int] = {}
    for p in sorted((root / "knowledge").glob("*/*.json")):
        item = json.loads(p.read_text(encoding="utf-8"))
        conf, strength, score, notes = grade(item, sources)
        dist[conf] = dist.get(conf, 0) + 1
        sdist[strength] = sdist.get(strength, 0) + 1
        cur_conf = item.get("confidence")
        cur_str = item.get("evidence_strength")
        bad = []
        if cur_conf != conf:
            bad.append(("confidence", cur_conf, conf))
        if cur_str != strength:
            bad.append(("evidence_strength", cur_str, strength))
        if bad:
            mismatches.append((p, item["id"], bad, score, notes))
            if args.apply:
                item["confidence"] = conf
                item["evidence_strength"] = strength
                p.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"条目 {sum(dist.values())} 条")
    print(f"  confidence（信任等级，受 replay_verified 闸门约束）: {dist}")
    print(f"  evidence_strength（证据强度，由来源构成推导）: {sdist}")
    if mismatches:
        print(f"不一致 {len(mismatches)} 条：")
        for p, iid, bad, score, notes in mismatches:
            desc = "; ".join(f"{f}: 现值={c!r} 应为={e!r}" for f, c, e in bad)
            print(f"  [{iid}] {desc}（分数 {score}）")
            if args.verbose:
                for n in notes:
                    print(f"       - {n}")
    else:
        print("全部条目的 confidence / evidence_strength 与推导一致。")
    return 1 if mismatches and not args.apply else 0


if __name__ == "__main__":
    sys.exit(main())
