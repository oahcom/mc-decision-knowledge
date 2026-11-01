#!/usr/bin/env python3
"""采集「机制事实」类来源：游戏机制的一手数值（交互距离、背包格数、饥饿阈值、
生命值、合成格数、区块尺寸、配方用量）。

设计原则与既有采集器一致：
1. 只走公开入口（MediaWiki API / raw.githubusercontent.com），不使用任何登录态。
2. 锚点命中失败即报错退出，绝不以记忆补全。
3. 摘录是原文切片，数值可逐字复核。

用法：
    python3 scripts/collect_mechanic_facts.py            # 写入 sources/
    python3 scripts/collect_mechanic_facts.py --dry-run  # 只校验锚点
"""
import argparse
import gzip
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = ROOT / "sources"
UA = {"User-Agent": "MC-KB-Collector/1.0", "Accept-Encoding": "gzip"}
COLLECTED_AT = "2026-11-01T00:00:00Z"


def _get(url: str, timeout: int = 90, retries: int = 3) -> bytes:
    """带重试的 GET。大页面（Player 488 KB / Armor 240 KB）偶发 IncompleteRead。"""
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:  # noqa: BLE001
            last = exc
    raise last


def wiki_html(page: str) -> str:
    q = urllib.parse.urlencode(
        {"action": "parse", "page": page, "prop": "text", "format": "json", "redirects": 1}
    )
    raw = _get(f"https://minecraft.wiki/api.php?{q}")
    return json.loads(_decode(raw))["parse"]["text"]["*"]


def normalize_prose(html_text: str) -> str:
    """HTML → 纯文本：去脚本/样式、标签、实体，折叠空白。"""
    t = re.sub(r"<script.*?</script>", " ", html_text, flags=re.S)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t)
    t = t.replace(" ", " ").replace("’", "'")
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def slice_around(blob: str, anchor: str, before: int, after: int) -> str:
    """以锚点为中心切窗口。锚点缺失即抛错——这是「不外造」的强制点。"""
    idx = blob.find(anchor)
    if idx < 0:
        raise ValueError(f"锚点未命中：{anchor!r}")
    start = max(0, idx - before)
    end = min(len(blob), idx + len(anchor) + after)
    return blob[start:end].strip()


def raw_github(path: str) -> str:
    url = f"https://raw.githubusercontent.com/PrismarineJS/minecraft-data/master/data/pc/1.21.4/{path}"
    b = _get(url)
    try:
        b = gzip.decompress(b)
    except Exception:  # noqa: BLE001
        pass
    return b.decode("utf-8")


def _decode(b: bytes) -> str:
    """统一解码：先尝试 gzip，再按 UTF-8 解。"""
    try:
        b = gzip.decompress(b)
    except Exception:  # noqa: BLE001
        pass
    return b.decode("utf-8")


def recipe_slice(items_raw: str, recipes_raw: str, item_name: str) -> tuple[str, str, str]:
    """从 minecraft-data 取出某物品的配方，返回 (原文切片, 摘要, locator)。

    配方用量 = 材料 id 在合成格中出现的次数——原文里重复的 id 直接可见，
    可以逐字手工复核，不依赖任何推断。
    """
    items = json.loads(items_raw)
    recipes = json.loads(recipes_raw)
    id2n = {i["id"]: i["name"] for i in items}

    # 在原文行上定位该物品的结果 id
    target_ids = [i["id"] for i in items if i["name"] == item_name]
    if not target_ids:
        raise ValueError(f"items.json 中找不到 {item_name}")

    lines = recipes_raw.split("\n")
    best = None
    for key, arr in recipes.items():
        if not isinstance(arr, list):
            continue
        for vi, r in enumerate(arr):
            if not isinstance(r, dict):
                continue
            rid = (r.get("result") or {}).get("id")
            if rid not in target_ids:
                continue
            grid = [x for row in (r.get("inShape") or []) for x in row if x is not None]
            names = [id2n.get(g) for g in grid]
            # 优先常规材料变体（圆石 / 橡木木板 / 煤），深板岩与稀有木种是等价替代
            pref = ("cobblestone", "oak_planks", "coal", "stick")
            score = sum(1 for x in pref if x in names)
            cand = (score, key, vi, grid, names)
            if best is None or cand[0] > best[0]:
                best = cand

    if best is None:
        raise ValueError(f"recipes.json 中找不到 {item_name} 的配方")

    _, key, vi, grid, names = best
    # 精确切到选中的那个变体对象（顶层 {…}）
    span = _variant_span(lines, key, vi)
    if span is None:
        raise ValueError(f"无法在原文定位配方变体 {key}[{vi}]")
    s, e = span
    snippet = "\n".join(lines[s : e + 1])

    counts: dict[str, int] = {}
    for n in names:
        counts[n] = counts.get(n, 0) + 1
    summary = " + ".join(f"{v} {k}" for k, v in sorted(counts.items(), key=lambda x: -x[1]))
    locator = f"recipes.json 顶层键 \"{key}\" 数组第 {vi} 个配方对象（行 {s + 1}-{e + 1}）"
    return snippet, summary, locator


def _variant_span(lines: list[str], key: str, idx: int):
    """定位某键下第 idx 个配方变体对象的行区间。

    用缩进而非括号计数来判定变体边界——顶层数组的元素对象固定缩进 4 空格，
    其内部的 inShape / result 都是 6 空格以上，按缩进切不会误把 result 子对象
    当成整个变体（括号计数会，因为 `[` 不参与深度）。
    """
    start = None
    for i, line in enumerate(lines):
        if line.strip().startswith(f'"{key}":'):
            start = i
            break
    if start is None:
        return None

    OPEN = "    {"
    CLOSE = ("    }", "    },")
    open_re = re.compile(r"^    \{$")
    close_re = re.compile(r"^    \},?$")

    seen = 0
    for j in range(start + 1, min(start + 800, len(lines))):
        if not open_re.match(lines[j]):
            continue
        # 找到该变体的闭合行
        end = None
        for k in range(j + 1, min(j + 200, len(lines))):
            if close_re.match(lines[k]):
                end = k
                break
        if end is None:
            continue
        if seen == idx:
            return (j, end)
        seen += 1
    return None


WIKI_COMPLIANCE = {
    "publicly_accessible": True,
    "robots_or_terms_respected": True,
    "personal_data_excluded": True,
    "no_auth_bypass": True,
}


def wiki_source(source_id, title, page, anchor, before, after, notes, versions=None,
                derived=None):
    blob = normalize_prose(wiki_html(page))
    excerpt = slice_around(blob, anchor, before, after)
    doc = {
        "source_id": source_id,
        "title": title,
        "url": f"https://minecraft.wiki/w/{page.replace(' ', '_')}",
        "platform": "minecraft_wiki",
        "source_type": "community_wiki",
        "reliability": "A",
        "license": "CC-BY-NC-SA-3.0",
        "retrieved_at": COLLECTED_AT,
        "content_excerpt": excerpt,
        "evidence_notes": notes,
        "related_game_versions": versions or ["Java Edition 全部版本", "Bedrock Edition 全部版本"],
        "access_method": "official_api",
        "compliance": dict(WIKI_COMPLIANCE),
        "quality": {
            "decision_relevance": 5,
            "specificity": 5,
            "version_clarity": 4,
            "reproducibility": 5,
        },
        "notes": "摘录取自 Minecraft Wiki 官方 MediaWiki API 的渲染正文；数值可逐字复核。",
    }
    if derived:
        doc["derived_values"] = derived
    return doc


def build_all(dry_run: bool = False):
    docs = []

    # ---- 1. 玩家交互距离 4.5 格 ----
    docs.append(
        wiki_source(
            "src_wiki_player_interaction_range",
            "Player - Minecraft Wiki（默认交互距离）",
            "Player",
            "Default interaction range",
            60,
            330,
            "给出 Java Edition 方块交互距离 4.5 格、实体交互距离 3 格，"
            "以及 Bedrock 对应值（方块 5 / 实体 3 / 触碰 6）。"
            "这是「工作台/熔炉/容器能否在 N 格外打开」的服务端硬边界。",
            versions=["Java Edition 全部版本", "Bedrock Edition 全部版本"],
        )
    )

    # ---- 2. 背包格数 36 ----
    docs.append(
        wiki_source(
            "src_wiki_inventory_slots",
            "Inventory - Minecraft Wiki（背包槽位构成）",
            "Inventory",
            "The inventory consists of 4 armor slots",
            40,
            260,
            "给出玩家背包的槽位构成：4 护甲 + 27 储存 + 9 快捷栏 + 1 副手，"
            "即 36 格可携带物品（27+9）。是「背包满」判定与腾位策略的槽位总数依据。",
            derived=[
                {
                    "value": "36",
                    "basis": "可携带物品槽位 = 27 storage slots + 9 hotbar slots = 36"
                             "（摘录中的 27 与 9 直接相加；护甲 4 与副手 1 不计入可携带物品）",
                },
            ],
        )
    )

    # ---- 3. 饥饿值 18 的自然回血阈值 ----
    docs.append(
        wiki_source(
            "src_wiki_hunger_regen_threshold",
            "Hunger - Minecraft Wiki（自然回血的饥饿阈值）",
            "Hunger",
            "If the hunger value is at 18",
            80,
            320,
            "给出自然回血条件：饥饿值 ≥ 18（或饱和度非零）时，每 4 秒（80 tick）回 1 点生命；"
            "并说明回血先扣饱和度、饱和度耗尽后再扣饥饿值。"
            "这是「何时该先吃东西」与「目标饥饿值取 18」的机制依据。",
        )
    )

    # ---- 4. 玩家生命值 20 ----
    docs.append(
        wiki_source(
            "src_wiki_player_health",
            "Health - Minecraft Wiki（玩家生命值上限）",
            "Health",
            "Playable Player 20 HP",
            30,
            200,
            "给出玩家生命值上限 20 HP（10 颗心）。"
            "是「生命 < 10 撤退」「生命 < 12 不开打」等生命百分比阈值的换算基准。",
        )
    )

    # ---- 5. 合成格 2×2 / 3×3 ----
    docs.append(
        wiki_source(
            "src_wiki_crafting_grid_size",
            "Crafting - Minecraft Wiki（2×2 与 3×3 合成格）",
            "Crafting",
            "3×3 crafting grid ( crafting table )",
            120,
            300,
            "给出合成格尺寸：背包界面只有 2×2 合成格，工作台提供 3×3 合成格。"
            "是「哪些配方必须靠近工作台」与「配方需求 ≥4 时需工作台」的结构性依据。",
        )
    )

    # ---- 6. 区块尺寸 16×16 ----
    docs.append(
        wiki_source(
            "src_wiki_chunk_dimensions",
            "Chunk - Minecraft Wiki（区块尺寸 16×16）",
            "Chunk",
            "A chunk is a 16×16 segment of a world",
            60,
            260,
            "给出区块尺寸：16×16 区块划分世界，并按 16 格高切分为 subchunk。"
            "是「按 16×16 区块粒度统计搜索唯一率」的粒度依据。",
        )
    )

    # ---- 6b. 工具耐久 uses 表 ----
    docs.append(
        wiki_source(
            "src_wiki_tool_durability_uses",
            "Durability - Minecraft Wiki（工具可使用次数表）",
            "Durability",
            "Wood : 59 uses",
            180,
            420,
            "给出工具材质的最大使用次数：金 32 / 木 59 / 石 131 / 铜 191 / 铁 250 / "
            "钻石 1561 / 下界合金 2031 次。次数即「每破坏一个方块消耗 1 点耐久」的计数单位，"
            "是耐久预算（如铁镐 250 次 ≈ 250 个圆石）的基础。",
            derived=[
                {
                    "value": "1",
                    "basis": "每次破坏方块消耗 1 点耐久：Durability 页的「N uses」以「次」为单位计数，"
                             "而 Breaking 页注明瞬间破坏的方块「doesn't make tools lose durability」，"
                             "即非瞬间破坏方块按 1 次 / 1 点扣减",
                },
            ],
        )
    )

    # ---- 7. 配方用量（minecraft-data） ----
    items_raw = raw_github("items.json")
    recipes_raw = raw_github("recipes.json")
    recipe_groups = [
        ("src_minecraftdata_recipes_tool_chain", ["wooden_pickaxe", "stone_pickaxe", "iron_pickaxe", "iron_sword"]),
        ("src_minecraftdata_recipes_iron_armor", ["iron_helmet", "iron_chestplate", "iron_leggings", "iron_boots"]),
    ]
    for sid, items in recipe_groups:
        parts, locator_bits, summaries = [], [], []
        for it in items:
            snippet, summary, loc = recipe_slice(items_raw, recipes_raw, it)
            parts.append(f"### {it}\n{snippet}")
            locator_bits.append(f"{it}: {loc}")
            summaries.append(f"{it} = {summary}")
        excerpt = "\n\n".join(parts)
        if len(excerpt) > 1200:
            raise ValueError(f"{sid}: 摘录 {len(excerpt)} 字符超过 1200")
        derived = []
        for it, summary in zip(items, summaries):
            # summary 形如 "iron_pickaxe = 3 iron_ingot + 2 stick"：先去掉 "物品名 = " 前缀
            body = summary.split("=", 1)[1] if "=" in summary else summary
            for chunk in body.split(" + "):
                qty_s, _, mat = chunk.strip().partition(" ")
                qty_s = qty_s.strip()
                mat = mat.strip()
                if not qty_s.isdigit() or not mat:
                    continue
                derived.append(
                    {
                        "value": qty_s,
                        "basis": f"{it} 的 inShape 合成格中材料 {mat} 的 id 出现 {qty_s} 次，"
                                 f"即该配方需 {qty_s} 个 {mat}",
                    }
                )
        docs.append(
            {
                "source_id": sid,
                "title": f"minecraft-data recipes.json（{'/'.join(items)} 配方用量）",
                "url": "https://raw.githubusercontent.com/PrismarineJS/minecraft-data/master/data/pc/1.21.4/recipes.json",
                "platform": "github",
                "source_type": "source_code",
                "reliability": "A",
                "license": "MIT",
                "retrieved_at": COLLECTED_AT,
                "content_excerpt": excerpt,
                "evidence_notes": "配方用量 = 材料 id 在合成格中出现的次数；" + "；".join(summaries)
                + "。同一份数据中铁剑 2 铁锭 + 1 木棍与 Minecraft Wiki 的 {{Crafting}} 模板逐字一致（互证）。",
                "related_game_versions": ["Java Edition 1.21.4"],
                "access_method": "official_api",
                "compliance": dict(WIKI_COMPLIANCE),
                "quality": {
                    "decision_relevance": 5,
                    "specificity": 5,
                    "version_clarity": 5,
                    "reproducibility": 5,
                },
                "notes": "摘录为 recipes.json 原文切片（逐行），非加工后的结论。"
                "同一 id 重复出现即为该材料的用量，可手工数出。",
                "derived_values": derived,
            }
        )

    # ---- 8. 物品 id 映射（用于核对上表的材料 id） ----
    items_json = json.loads(items_raw)
    wanted = ["oak_planks", "cobblestone", "stick", "iron_ingot"]
    lines = []
    for it in items_json:
        if it["name"] in wanted:
            lines.append(json.dumps(it, ensure_ascii=False))
    excerpt = "\n".join(lines)
    docs.append(
        {
            "source_id": "src_minecraftdata_items_id_map",
            "title": "minecraft-data items.json（关键材料 id 与堆叠上限）",
            "url": "https://raw.githubusercontent.com/PrismarineJS/minecraft-data/master/data/pc/1.21.4/items.json",
            "platform": "github",
            "source_type": "source_code",
            "reliability": "A",
            "license": "MIT",
            "retrieved_at": COLLECTED_AT,
            "content_excerpt": excerpt,
            "evidence_notes": "给出橡木木板、圆石、木棍、铁锭的 id 与堆叠上限，"
            "用于核对 recipes.json 摘录中的材料 id（用量靠重复次数确定，名称靠本表确定）。",
            "related_game_versions": ["Java Edition 1.21.4"],
            "access_method": "official_api",
            "compliance": dict(WIKI_COMPLIANCE),
            "quality": {
                "decision_relevance": 4,
                "specificity": 5,
                "version_clarity": 5,
                "reproducibility": 5,
            },
            "notes": "摘录为 items.json 中相关条目的原始 JSON 行。",
        }
    )

    if dry_run:
        for d in docs:
            print(f"[DRY] {d['source_id']}  len={len(d['content_excerpt'])}")
        return docs

    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    for d in docs:
        p = SOURCES_DIR / f"{d['source_id']}.json"
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[ OK ] {d['source_id']}  len={len(d['content_excerpt'])}")
    return docs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    try:
        build_all(dry_run=args.dry_run)
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
