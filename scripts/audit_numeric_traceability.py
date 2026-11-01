#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数值溯源审计：知识条目里的每个数字都必须有明确归属。

判定规则
--------
对条目承载事实断言的每个字段中的每个数字，按以下顺序判定：

1. **机制事实** —— 能作为独立数值出现在**所引来源的摘录**里（按数值边界匹配，
   避免 "5" 命中 "500"）。成立。
2. **推导事实** —— 出现在**所引来源的 derived_values** 里（value 匹配，
   basis 写明推导依据）。成立。
3. **作者自定阈值** —— 作者自定的策略参数（观察窗口、安全半径、撤退线、重试上限……）。
   它不对应任何外部事实，因此**不可能**在来源里找到；但正因如此，它必须在条目的
   `tunable_thresholds` 里显式声明（字段 / 字面值 / 原文片段 / 理由），
   否则下游无法区分「机制如此」与「作者如此决定」。

三者都不满足 → 报告发现。

声明的匹配是**按上下文精确匹配**的：一条声明的 context 必须出现在它所声明的
那一段文本里。这样同一个数字在同一字段里出现多次（含义不同）可以各自声明，
而不会互相顶替。

另外三类问题同样报出：
- 声明的 context 在该字段里根本不存在 → 声明与正文脱节；
- 声明的 context 存在但那一段里没有对应数字 → 声明悬空；
- 同一 (字段, 字面值, context) 有多条声明 → 重复声明。

关于「声明多余」：只有当字面值**足够独特**（≥3 位整数或含小数点）时，
它在摘录里出现才说明它可能本该走机制事实路径。对 1/2/3/12 这类小数字，
它们出现在任何一段长摘录里都是偶然的，据此报「多余」只会制造假阳性。
独特数字若确实出现在所引摘录里 → 报告发现。

用法:
    python3 scripts/audit_numeric_traceability.py [--root .] [--verbose]
退出码: 0 = 全部数字归属清楚, 1 = 存在未归属或错误归属的数字
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CLAIM_FIELDS = [
    "title", "summary", "trigger", "actions", "preconditions", "success_condition",
    "abort_condition", "risk_notes", "decision_rule", "model_guidance",
    "alternative_comparison", "anti_patterns", "stage", "diagnostics",
    "symptoms", "parameters", "verification", "recovery_steps", "possible_causes",
    "expected_effects", "failure_modes", "continue_condition", "exit_condition",
    "checklist", "scenario", "success_criteria",
]

NUM_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w])")
WORD_NUM = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
    "seven": "7", "eight": "8", "nine": "9", "ten": "10", "eleven": "11",
    "twelve": "12", "twenty": "20", "thirty": "30", "forty": "40", "fifty": "50",
    "sixty": "60", "hundred": "100", "thousand": "1000",
}


def strip_thousands(s: str) -> str:
    return re.sub(r"(?<=\d),(?=\d)", "", s)


def numbers_in(text: str) -> set[str]:
    text = re.sub(r"(?:src|mc|kb)_[a-z0-9_]+", " ", text)
    text = re.sub(r"\d{4}-\d{2}-\d{2}", " ", text)
    out = {m.group(1) for m in NUM_RE.finditer(text)}
    low = text.lower()
    for w, d in WORD_NUM.items():
        if re.search(rf"(?<![\w]){w}(?![\w])", low):
            out.add(d)
    return out


def present(token: str, excerpts: list[str]) -> bool:
    """token 是否作为**独立数值**出现在任一摘录里（按数值边界匹配）。"""
    pat = re.compile(r"(?<![\w.])" + re.escape(token) + r"(?![\w.])")
    for ex in excerpts:
        e = strip_thousands(ex)
        if pat.search(e):
            return True
        for w, d in WORD_NUM.items():
            if d == token and re.search(rf"(?<![\w]){w}(?![\w])", ex.lower()):
                return True
    return False


def is_distinctive(token: str) -> bool:
    """字面值是否足够独特，值得怀疑「本该引用来源」。

    小数字（1/2/3/12…）出现在任何一段长摘录里都是偶然的；只有多位数或
    带小数的值，其出现才构成「它可能是从来源抄来的」这一信号。
    """
    if "." in token:
        return True
    try:
        return int(token) >= 100
    except ValueError:
        return False


def field_texts(item: dict, field: str) -> list[str]:
    v = item.get(field)
    out: list[str] = []

    def walk(x):
        if isinstance(x, str):
            out.append(x)
        elif isinstance(x, list):
            for e in x:
                walk(e)
        elif isinstance(x, dict):
            for val in x.values():
                walk(val)

    walk(v)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    root = Path(args.root)

    sources = {}
    for p in sorted((root / "sources").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        sources[d["source_id"]] = d

    findings: list[str] = []
    n_items = n_numbers = n_tunable = n_derived = n_direct = 0

    for p in sorted((root / "knowledge").glob("*/*.json")):
        item = json.loads(p.read_text(encoding="utf-8"))
        n_items += 1
        cited_ids = [r for r in item.get("source_refs", []) if r in sources]
        excerpts = [sources[r]["content_excerpt"] for r in cited_ids]
        derived_vals = set()
        # derived_subject[value] = 该值所描述对象在中文文本中的可能说法
        derived_subject: dict[str, set[str]] = {}
        for r in cited_ids:
            for dv in sources[r].get("derived_values", []) or []:
                val = str(dv.get("value"))
                derived_vals.add(val)
                for t in dv.get("subject_terms", []) or []:
                    derived_subject.setdefault(val, set()).add(t)

        decls = item.get("tunable_thresholds") or []

        # ---- 声明自身的完整性 ----
        seen_key: dict[tuple[str, str, str], int] = {}
        used: set[int] = set()
        for idx, d in enumerate(decls):
            field, val, ctx = d.get("field", ""), d.get("value", ""), d.get("context", "")
            key = (field, val, ctx)
            if key in seen_key:
                findings.append(
                    f"[声明重复] {item['id']}: 字段 {field} 的数值 {val} 有多条相同声明"
                    f"（第 {seen_key[key] + 1} 条与第 {seen_key[key] + 2} 条）"
                )
            else:
                seen_key[key] = idx
            texts = field_texts(item, field)
            hit_texts = [t for t in texts if ctx in t]
            if not hit_texts:
                findings.append(
                    f"[声明脱节] {item['id']}: 声明称 {field} 中出现 '{val}'（片段 {ctx!r}），"
                    f"但该字段里找不到这段原文"
                )
                continue
            # 声明悬空：context 在，但那一段里没有该数字
            if not any(val in numbers_in(t) for t in hit_texts):
                findings.append(
                    f"[声明悬空] {item['id']}: 声明 {field}/{val} 的片段 {ctx!r} 存在，"
                    f"但那段文本里没有数字 {val}"
                )
                continue
            if is_distinctive(val) and present(val, excerpts):
                findings.append(
                    f"[声明多余] {item['id']}: {field} 的阈值 '{val}' 能在所引来源摘录里找到，"
                    f"它应当按机制事实引用来源，而不是声明为可调阈值"
                )
            # reason 必须自足：不得用「同上」指代前一条声明
            if d.get("reason", "").startswith("同上"):
                findings.append(
                    f"[理由不独立] {item['id']}: 声明 {field}/{val} 的理由以「同上」开头，"
                    f"必须写成本条自足的说明——条目被单独引用时读者无从判断它说的是什么"
                )
            # 与来源推导冲突：同一件事被同时说成「机制事实」与「作者自定」
            terms = derived_subject.get(val) or set()
            if terms and any(t in ctx for t in terms):
                findings.append(
                    f"[声明冲突] {item['id']}: {field} 的阈值 '{val}'（片段 {ctx!r}）"
                    f"所描述的对象（{'/'.join(sorted(terms)[:3])}）已被所引来源的 "
                    f"derived_values 明确推出，它应当按机制事实处理，不能声明为可调阈值"
                )

        # ---- 逐字段检查数字 ----
        for field in CLAIM_FIELDS:
            if field not in item:
                continue
            for text in field_texts(item, field):
                cleaned = re.sub(r"\d{4}-\d{2}-\d{2}|\d{2}:\d{2}", " ", text)
                for tok in sorted(numbers_in(cleaned), key=lambda x: -len(x)):
                    n_numbers += 1
                    if present(tok, excerpts):
                        n_direct += 1
                        continue
                    if tok in derived_vals:
                        n_derived += 1
                        continue
                    # 按上下文精确匹配声明
                    hit = None
                    for idx, d in enumerate(decls):
                        if d.get("field") != field or d.get("value") != tok:
                            continue
                        if d.get("context") and d["context"] in text:
                            hit = idx
                            break
                    if hit is None:
                        findings.append(
                            f"[无归属] {item['id']}: {field} 中的数值 {tok} 既不在所引来源摘录里，"
                            f"也不能从来源推导得出，还没有在 tunable_thresholds 中声明"
                            f"（原文：{text[:70]}）"
                        )
                    else:
                        used.add(hit)
                        n_tunable += 1

    print(f"条目 {n_items} 条，检查数值 {n_numbers} 个")
    print(f"  来源直接支撑 {n_direct} 个 | 来源可推导 {n_derived} 个 | 作者自定阈值 {n_tunable} 个")
    print(f"Findings: {len(findings)}")
    for f in findings:
        print("FINDING", f)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
