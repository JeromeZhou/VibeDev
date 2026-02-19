"""GPU-Insight PPHI 排名计算模块 — v2 支持 PainInsight 结构"""

import json
import math
import re
from datetime import datetime
from pathlib import Path
from src.utils.config import get_pphi_weights

MAX_RANKINGS = 50  # 排名上限


def calculate_pphi(insights: list[dict], config: dict) -> list[dict]:
    """计算 PPHI 指数并生成排名（累积历史 + 当轮新增）"""
    weights = get_pphi_weights(config)
    decay_rate = config.get("pphi", {}).get("decay_rate_per_day", 0.05)
    source_scores = {
        "chiphell": 1.0, "reddit": 0.9, "videocardz": 0.85,
        "techpowerup": 0.85, "nga": 0.8, "guru3d": 0.8,
        "bilibili": 0.75, "mydrivers": 0.75, "v2ex": 0.7,
        "rog": 0.7, "tieba": 0.6, "twitter": 0.5,
    }

    # 加载历史痛点 + 当轮新增，合并后统一排名
    all_insights = _load_historical_insights() + (insights or [])
    if not all_insights:
        return []

    # 聚合同类痛点（规则层：同义词组 + 子串匹配）
    aggregated = _aggregate(all_insights)

    # LLM 跨轮语义去重（对聚合后的痛点名称做二次合并）
    if len(aggregated) > 5:
        aggregated = _llm_dedup_aggregated(aggregated, config)

    # 计算 PPHI（改进版：增强区分度）
    rankings = []
    for pain_point, data in aggregated.items():
        # 用关联帖子数作为频率指标（比痛点文本匹配更准确）
        mention_count = max(data["count"], len(data.get("source_urls", [])))
        sources = data["sources"]
        avg_source_score = sum(source_scores.get(s, 0.5) for s in sources) / max(len(sources), 1)
        interaction = data.get("avg_interaction", 0)
        days_old = min(data.get("days_old", 0), 30)  # 封顶30天，避免过度衰减

        # 1. Frequency 对数缩放（1条=20, 2条=40, 4条=60, 8条=80）
        frequency_score = math.log2(mention_count + 1) * 20

        # 2. Source Quality 降权改为加成（避免基础分趋同）
        source_quality_score = avg_source_score * 50

        # 3. Interaction 对数缩放（避免大部分为0时无区分度）
        interaction_score = math.log2(interaction + 1) * 15

        # 4. Cross-Platform 跨平台加成（多论坛出现更重要）
        cross_platform_score = min(len(sources), 4) / 4 * 100

        # 5. Freshness 新鲜度加成（7天内有额外分数，替代 time_decay）
        freshness_score = max(0, (7 - days_old) / 7) * 100

        # 新权重从配置读取（5 维模型）
        w_freq = weights.get("frequency", 0.30)
        w_src = weights.get("source_quality", 0.20)
        w_int = weights.get("interaction", 0.15)
        w_cross = weights.get("cross_platform", 0.15)
        w_fresh = weights.get("freshness", 0.20)
        pphi = (
            w_freq * frequency_score
            + w_src * source_quality_score
            + w_int * interaction_score
            + w_cross * cross_platform_score
            + w_fresh * freshness_score
        )
        pphi = max(0, round(pphi, 1))

        rankings.append({
            "pain_point": pain_point,
            "pphi_score": pphi,
            "mentions": mention_count,
            "sources": list(sources),
            "source_urls": data.get("source_urls", []),
            "gpu_tags": data.get("gpu_tags", {}),
            "hidden_need": data.get("hidden_need", ""),
            "confidence": data.get("avg_confidence", 0),
            "category": data.get("category", ""),
            "affected_users": data.get("affected_users", ""),
            "evidence": data.get("evidence", ""),
            "trend": _detect_trend(pain_point, pphi),
            "inferred_need": data.get("inferred_need_obj"),  # 完整的推理对象
            "total_replies": data.get("total_replies", 0),
            "total_likes": data.get("total_likes", 0),
            # Munger 质量加权
            "munger_quality": data.get("munger_quality", "unknown"),
            "needs_verification": data.get("needs_verification", False),
            "quality_tier": _classify_quality_tier(data),
        })

    # 排序：PPHI 降序，相同分数时按 mentions 降序（二级排序）
    rankings.sort(key=lambda x: (x["pphi_score"], x["mentions"]), reverse=True)

    # 排名上限：只保留 Top N，低分痛点自然淘汰（旧数据在 pain_points 表永久保留）
    if len(rankings) > MAX_RANKINGS:
        print(f"  排名上限: {len(rankings)} → {MAX_RANKINGS}（淘汰 {len(rankings) - MAX_RANKINGS} 个低分项）")
        rankings = rankings[:MAX_RANKINGS]

    for i, r in enumerate(rankings):
        r["rank"] = i + 1

    _save_rankings(rankings, config)
    return rankings


def _load_historical_insights() -> list[dict]:
    """从 DB 加载历史痛点（从 pphi_history 最新一轮的累积数据）

    关键设计：pphi_history 存的是每轮聚合后的结果（GPU 标签已合并），
    而 pain_points 存的是每轮原始提取结果（标签未合并）。
    所以必须从 pphi_history 加载，才能实现跨轮次的标签累积。
    """
    try:
        from src.utils.db import get_db
        with get_db() as conn:

            # 取最新一轮的累积排名数据（已包含历史合并的 GPU 标签）
            latest_run = conn.execute(
                "SELECT MAX(run_date) as rd FROM pphi_history"
            ).fetchone()
            if not latest_run or not latest_run["rd"]:
                return []

            latest_date = latest_run["rd"]
            rows = conn.execute(
                """SELECT pain_point, pphi_score, mentions, gpu_tags,
                          source_urls, hidden_need, total_replies, total_likes,
                          inferred_need_json, category, affected_users
                   FROM pphi_history
                   WHERE run_date = ?
                   ORDER BY rank ASC""",
                (latest_date,)
            ).fetchall()

            insights = []
            for r in rows:
                gpu_tags = json.loads(r["gpu_tags"]) if r["gpu_tags"] else {}
                source_urls = json.loads(r["source_urls"]) if r["source_urls"] else []

                # 从 source_urls 推断来源，构造 source_post_ids
                source_post_ids = []
                for url in source_urls:
                    if "reddit" in url:
                        slug = url.rstrip("/").split("/")[-1]
                        source_post_ids.append(f"reddit_{slug}")
                    elif "nga" in url:
                        tid = url.split("tid=")[-1].split("&")[0] if "tid=" in url else ""
                        if tid:
                            source_post_ids.append(f"nga_{tid}")
                    elif "bilibili" in url:
                        bv = url.rstrip("/").split("/")[-1]
                        source_post_ids.append(f"bilibili_{bv}")
                    elif "v2ex" in url:
                        tid = url.rstrip("/").split("/")[-1]
                        source_post_ids.append(f"v2ex_{tid}")
                    elif "mydrivers" in url:
                        slug = url.rstrip("/").split("/")[-1]
                        source_post_ids.append(f"mydrivers_{slug}")
                    elif "techpowerup" in url:
                        slug = url.rstrip("/").split("/")[-1]
                        source_post_ids.append(f"techpowerup_{slug}")
                    elif "videocardz" in url:
                        slug = url.rstrip("/").split("/")[-1]
                        source_post_ids.append(f"videocardz_{slug}")
                    else:
                        source_post_ids.append(f"unknown_{url[-20:]}")

                # 互动数据：优先用 pphi_history 存储的累积值，fallback 到 posts 表查询
                total_replies = r["total_replies"] or 0
                total_likes = r["total_likes"] or 0
                earliest_timestamp = ""
                if total_replies == 0 and total_likes == 0 and source_post_ids:
                    placeholders = ",".join("?" * len(source_post_ids))
                    post_rows = conn.execute(
                        f"""SELECT replies, likes, timestamp FROM posts
                            WHERE id IN ({placeholders})""",
                        source_post_ids
                    ).fetchall()
                    total_replies = sum(row["replies"] or 0 for row in post_rows)
                    total_likes = sum(row["likes"] or 0 for row in post_rows)
                    timestamps = [row["timestamp"] for row in post_rows if row["timestamp"]]
                    if timestamps:
                        earliest_timestamp = min(timestamps)

                hidden_need_obj = None
                # 优先从完整 JSON 加载（含 reasoning_chain + munger_review）
                inferred_json = r["inferred_need_json"] if "inferred_need_json" in r.keys() else None
                if inferred_json:
                    try:
                        hidden_need_obj = json.loads(inferred_json)
                    except (json.JSONDecodeError, TypeError):
                        pass
                # fallback: 只有 hidden_need 文本
                if not hidden_need_obj and r["hidden_need"]:
                    hidden_need_obj = {
                        "hidden_need": r["hidden_need"],
                        "confidence": 0,
                        "reasoning_chain": [],
                        "munger_review": None,
                        "_is_fallback": True,
                    }

                insights.append({
                    "pain_point": r["pain_point"],
                    "category": r["category"] if "category" in r.keys() and r["category"] else "",
                    "affected_users": r["affected_users"] if "affected_users" in r.keys() and r["affected_users"] else "",
                    "evidence": "",
                    "source_post_ids": source_post_ids,
                    "source_urls": source_urls,
                    "gpu_tags": gpu_tags,
                    "inferred_need": hidden_need_obj,
                    "total_replies": total_replies,
                    "total_likes": total_likes,
                    "earliest_timestamp": earliest_timestamp,
                    "_hist_mentions": r["mentions"] or 0,  # 历史累积的 mentions 数
                })

        print(f"  [历史] 从 pphi_history 加载 {len(insights)} 个累积痛点 (run: {latest_date})")
        return insights
    except Exception as e:
        print(f"  [!] 加载历史痛点失败: {e}")
        return []


def _normalize_pain_point(pain_point: str) -> tuple[str, str]:
    """规范化痛点名称，返回 (规范化名称, 原始名称)

    规则：
    1. 去掉括号内的分类标签，如 "(散热)"、"(驱动)"、"(生态)"
    2. 去掉 "显卡" 前缀（如果去掉后仍有意义，即剩余长度 >= 2）
    3. 去掉常见后缀 "问题"、"不足"、"困难"（如果去掉后仍有意义）
    4. 统一为最短有意义的名称
    """
    import re

    normalized = pain_point.strip()

    # 1. 去掉括号内容（包括中英文括号）
    normalized = re.sub(r'[（(][^）)]*[）)]', '', normalized).strip()

    # 2. 去掉 "显卡" 前缀（如果剩余长度 >= 2）
    if normalized.startswith("显卡") and len(normalized) > 3:
        normalized = normalized[2:]

    # 3. 去掉常见后缀（如果去掉后剩余长度 >= 2）
    for suffix in ["问题", "不足", "困难", "不好"]:
        if normalized.endswith(suffix) and len(normalized) - len(suffix) >= 2:
            normalized = normalized[:-len(suffix)]
            break

    # 4. 去掉多余空格
    normalized = re.sub(r'\s+', '', normalized)

    return normalized, pain_point


# 同义词组：组内任意两个痛点应合并（跨轮语义去重）
_SYNONYM_GROUPS = [
    {"价格昂贵", "价格过高", "价格太贵", "太贵", "过贵"},
    {"性价比低", "性价比差"},
    {"噪音大", "风扇噪音大", "风扇高转速噪音大", "噪音过大"},
    {"核心温度过高", "温度过高", "过热"},
    {"功耗过高", "功耗太高", "功耗大"},
    {"性能不足", "性能差", "性能不够"},
    {"驱动崩溃", "驱动闪退"},
]


def _find_synonym_key(normalized: str, existing_keys: dict) -> str | None:
    """在已有聚合 key 中查找同义词匹配

    策略（保守优先，宁可不合并也不能错合并）：
    1. 精确匹配同义词组（手动维护的确定同义词）
    2. 核心子串匹配（一个是另一个的子串，且短串 >= 5 字符，避免误合并）
    """
    # 策略1: 同义词组精确匹配
    for group in _SYNONYM_GROUPS:
        if normalized in group:
            for existing_key in existing_keys:
                if existing_key in group:
                    return existing_key

    # 策略2: 核心子串匹配（短串是长串的子串，门槛 >= 5 字符）
    for existing_key in existing_keys:
        short, long_s = (normalized, existing_key) if len(normalized) <= len(existing_key) else (existing_key, normalized)
        if len(short) >= 5 and short in long_s:
            return existing_key

    return None


def _llm_dedup_aggregated(aggregated: dict, config: dict) -> dict:
    """LLM 跨轮语义去重 — 消费电子分析师 review 痛点名单，判断合并

    输入：聚合后的 {痛点名: 数据} 字典
    输出：合并后的字典（数据累加）
    """
    try:
        from src.utils.llm_client import LLMClient
        llm = LLMClient(config)
    except Exception:
        return aggregated

    names = list(aggregated.keys())
    if len(names) <= 5:
        return aggregated

    # 构建编号列表
    name_list = "\n".join(f"{i+1}. {n}" for i, n in enumerate(names))

    system_prompt = """你是消费电子行业分析师，专注 GPU/显卡领域。
你的任务是审查一份显卡用户痛点列表，找出语义重复的痛点并建议合并。

合并规则（保守优先）：
- 只合并描述同一个具体问题的痛点（如"价格昂贵"和"价格过高"是同一个问题）
- 不要合并同一大类但不同具体问题的痛点（如"显存温度过高"和"显存容量不足"是不同问题）
- 不要合并不同硬件部件的问题（如"散热"和"噪音"虽然相关但是不同痛点）
- 如果不确定，不要合并

输出 JSON 数组，每个元素是一组应合并的编号：
{"merge_groups": [[1, 5], [3, 8, 12]]}

如果没有需要合并的，输出：{"merge_groups": []}
只输出 JSON，不要其他内容。"""

    prompt = f"以下是 {len(names)} 个显卡用户痛点，请找出语义重复的组：\n\n{name_list}"

    try:
        response = llm.call_reasoning(prompt, system_prompt)
        # 解析 JSON
        import re as _re
        text = _re.sub(r'```json\s*', '', response)
        text = _re.sub(r'```\s*', '', text)
        parsed = json.loads(text)
        merge_groups = parsed.get("merge_groups", [])

        if not merge_groups:
            return aggregated

        # 执行合并
        merged_count = 0
        merged_indices = set()
        for group in merge_groups:
            if not isinstance(group, list) or len(group) < 2:
                continue
            # 验证索引有效
            valid = [idx - 1 for idx in group if isinstance(idx, int) and 1 <= idx <= len(names)]
            if len(valid) < 2:
                continue

            # 选择 PPHI 最高的（count 最大的）作为主条目
            primary_idx = max(valid, key=lambda i: aggregated[names[i]]["count"])
            primary_name = names[primary_idx]

            for idx in valid:
                if idx == primary_idx or idx in merged_indices:
                    continue
                merge_name = names[idx]
                if merge_name not in aggregated:
                    continue
                if primary_name not in aggregated:
                    break

                # 安全网：category 不同的不合并
                primary_cat = aggregated[primary_name].get("category", "")
                merge_cat = aggregated[merge_name].get("category", "")
                if primary_cat and merge_cat and primary_cat != merge_cat:
                    print(f"    [LLM去重-跳过] category 不同: '{primary_name[:20]}'({primary_cat}) vs '{merge_name[:20]}'({merge_cat})")
                    continue

                # 安全网2：名称字符重叠率太低的不合并（防止 LLM 误判不相关痛点）
                n1 = set(primary_name.replace(" ", ""))
                n2 = set(merge_name.replace(" ", ""))
                overlap = len(n1 & n2) / max(len(n1), len(n2)) if max(len(n1), len(n2)) > 0 else 0
                if overlap < 0.2:
                    print(f"    [LLM去重-跳过] 名称重叠率过低({overlap:.0%}): '{primary_name[:20]}' vs '{merge_name[:20]}'")
                    continue

                # 合并日志
                print(f"    [LLM去重-合并] '{merge_name}' → '{primary_name}'")

                # 合并数据到主条目
                src_data = aggregated[merge_name]
                dst_data = aggregated[primary_name]
                dst_data["count"] += src_data["count"]
                # sources 可能是 set 或 list
                if isinstance(dst_data["sources"], set):
                    dst_data["sources"].update(src_data.get("sources", set()))
                else:
                    for s in src_data.get("sources", []):
                        if s not in dst_data["sources"]:
                            dst_data["sources"].append(s)
                for url in src_data.get("source_urls", []):
                    if url and url not in dst_data["source_urls"]:
                        dst_data["source_urls"].append(url)
                # gpu_tags 可能是 set 或 list
                for key in ("brands", "models", "series", "manufacturers"):
                    dst_tags = dst_data["gpu_tags"].get(key, [])
                    src_tags = src_data["gpu_tags"].get(key, [])
                    if isinstance(dst_tags, set):
                        dst_tags.update(src_tags)
                    else:
                        merged = list(dict.fromkeys(list(dst_tags) + list(src_tags)))
                        dst_data["gpu_tags"][key] = merged
                dst_data["total_replies"] += src_data.get("total_replies", 0)
                dst_data["total_likes"] += src_data.get("total_likes", 0)
                if src_data.get("timestamps"):
                    dst_data.setdefault("timestamps", []).extend(src_data["timestamps"])
                # 推理需求：保留有完整推理链的版本
                if not dst_data.get("inferred_need_obj") and src_data.get("inferred_need_obj"):
                    dst_data["inferred_need_obj"] = src_data["inferred_need_obj"]
                    dst_data["hidden_need"] = src_data.get("hidden_need", "")

                del aggregated[merge_name]
                merged_indices.add(idx)
                merged_count += 1

        if merged_count > 0:
            print(f"  [LLM去重] 合并 {merged_count} 个重复痛点（{len(aggregated)} 个剩余）")

        return aggregated

    except Exception as e:
        print(f"  [!] LLM 去重失败(不影响运行): {e}")
        return aggregated


def _aggregate(insights: list[dict]) -> dict:
    """聚合同类痛点，合并 GPU 标签和 URL（支持跨轮语义去重）"""
    agg = {}
    name_mapping = {}  # 规范化名称 -> 最佳展示名称

    for item in insights:
        pp = item.get("pain_point", "未知")
        normalized_pp, original_pp = _normalize_pain_point(pp)

        # 跨轮语义去重：先查同义词匹配
        matched_key = None
        if normalized_pp in agg:
            matched_key = normalized_pp
        else:
            matched_key = _find_synonym_key(normalized_pp, agg)

        # 使用规范化名称作为聚合 key
        if matched_key is None:
            # 新痛点，创建新条目
            matched_key = normalized_pp
            name_mapping[matched_key] = original_pp
            agg[matched_key] = {
                "count": 0,
                "sources": set(),
                "source_urls": [],
                "gpu_tags": {"brands": set(), "models": set(), "series": set(), "manufacturers": set()},
                "confidences": [],
                "hidden_need": "",
                "inferred_need_obj": None,  # 完整的推理对象
                "category": item.get("category", ""),
                "affected_users": item.get("affected_users", ""),
                "evidence": item.get("evidence", ""),
                "total_replies": 0,
                "total_likes": 0,
                "timestamps": [],
            }
        else:
            # 匹配到已有条目（精确匹配或同义词匹配），更新展示名
            current_display = name_mapping[matched_key]
            if len(original_pp) > len(current_display) or (original_pp.startswith("显卡") and not current_display.startswith("显卡")):
                name_mapping[matched_key] = original_pp

        # count: 如果 insight 来自历史累积（已有 mentions），用 mentions；否则 +1
        hist_mentions = item.get("_hist_mentions", 0)
        agg[matched_key]["count"] += hist_mentions if hist_mentions > 0 else 1

        # 来源
        for pid in item.get("source_post_ids", []):
            src = pid.split("_")[0] if "_" in pid else "unknown"
            agg[matched_key]["sources"].add(src)

        # URL
        for url in item.get("source_urls", []):
            if url and url not in agg[matched_key]["source_urls"]:
                agg[matched_key]["source_urls"].append(url)

        # GPU 标签合并
        tags = item.get("gpu_tags", {})
        for key in ("brands", "models", "series", "manufacturers"):
            agg[matched_key]["gpu_tags"][key].update(tags.get(key, []))

        # 互动数据累加
        agg[matched_key]["total_replies"] += item.get("total_replies", 0)
        agg[matched_key]["total_likes"] += item.get("total_likes", 0)

        # 时间戳收集
        ts = item.get("earliest_timestamp", "")
        if ts:
            agg[matched_key]["timestamps"].append(ts)

        # 推理需求（优先保留有完整推理链的版本）
        need = item.get("inferred_need")
        if need and need.get("hidden_need"):
            existing_need = agg[matched_key].get("inferred_need_obj")
            # 优先保留有 reasoning_chain 的版本
            if not existing_need or not existing_need.get("reasoning_chain"):
                agg[matched_key]["hidden_need"] = need["hidden_need"]
                agg[matched_key]["inferred_need_obj"] = need
            agg[matched_key]["confidences"].append(need.get("confidence", 0.5))
            # 提取 Munger 质量评级
            munger_review = need.get("munger_review", {})
            if munger_review:
                agg[matched_key]["munger_quality"] = munger_review.get("quality_level", "unknown")
                agg[matched_key]["needs_verification"] = need.get("_needs_verification", False)

    # 后处理：用最佳展示名替换规范化名称
    final_agg = {}
    now = datetime.now()
    for normalized_pp, data in agg.items():
        display_name = name_mapping[normalized_pp]
        data["avg_confidence"] = sum(data["confidences"]) / max(len(data["confidences"]), 1) if data["confidences"] else 0
        # 计算互动分 = replies + likes
        data["avg_interaction"] = data["total_replies"] + data["total_likes"]
        # 从最早时间戳计算 days_old
        data["days_old"] = 0
        if data["timestamps"]:
            try:
                earliest = min(data["timestamps"])
                # 去掉时区后缀，统一按本地时间比较
                clean_ts = earliest.replace("Z", "").replace("+00:00", "").replace("+08:00", "")
                # 截断微秒部分（如果有）
                if "." in clean_ts:
                    clean_ts = clean_ts.split(".")[0]
                earliest_dt = datetime.fromisoformat(clean_ts)
                data["days_old"] = max(0, (now - earliest_dt).days)
            except (ValueError, TypeError):
                data["days_old"] = 0
        data["gpu_tags"] = {k: sorted(v) for k, v in data["gpu_tags"].items()}
        del data["confidences"]
        del data["timestamps"]

        # 聚合层守卫：检测笼统名称，尝试用 evidence 替代
        display_name = _guard_display_name(display_name, data)

        # 使用展示名作为最终 key
        final_agg[display_name] = data

    return final_agg


# 分类名集合（与 analyzer 一致）
_CATEGORY_NAMES_R = {"性能", "价格", "散热", "噪音", "驱动", "兼容性", "显存", "功耗", "供货", "质量", "生态", "其他"}


def _guard_display_name(name: str, data: dict) -> str:
    """聚合层名称守卫：检测笼统/口语化/非GPU名称，用 evidence 或 hidden_need 摘要替代

    注意：不直接使用 hidden_need 替代，因为那是"需求"不是"痛点"
    """
    clean = name.strip()
    is_bad = False

    for prefix in ("显卡", "GPU"):
        if clean.startswith(prefix):
            clean = clean[len(prefix):]
    for suffix in ("显卡", "问题", "不足", "困难", "不好"):
        if clean.endswith(suffix):
            clean = clean[:-len(suffix)].strip()

    # 检查1: 笼统分类名 或 纯型号名（如 "9070显卡" → clean="9070"）
    if clean in _CATEGORY_NAMES_R or len(clean) < 3:
        is_bad = True
    # 纯数字/型号（去掉显卡后只剩型号号码）
    if not is_bad and re.match(r'^[\dA-Za-z\s\-\.]+$', clean):
        is_bad = True

    # 检查2: 口语化语气词（原始帖子标题直接当痛点名）
    _COLLOQUIAL = {"我建议", "我觉得", "我感觉", "建议大家", "大家觉得", "有没有人",
                   "求助", "请问", "怎么办", "哈哈", "估计", "竟",
                   "救命", "崩溃了", "无语", "离谱", "绝了", "真的是", "没希望"}
    if not is_bad:
        for marker in _COLLOQUIAL:
            if marker in name:
                is_bad = True
                break

    # 检查3: 叙事性标点（感叹号、省略号 = 原始标题）
    if not is_bad and re.search(r'[！!…]{1,}', name):
        is_bad = True

    # 检查4: 非 GPU 范畴
    _NON_GPU = {"显示器", "键盘", "鼠标", "耳机", "用眼", "护眼", "视力", "颈椎"}
    if not is_bad:
        has_non_gpu = any(kw in name for kw in _NON_GPU)
        has_gpu = any(kw in name.lower() for kw in ("gpu", "显卡", "rtx", "rx ", "gtx", "驱动", "显存", "vram", "帧"))
        if has_non_gpu and not has_gpu:
            is_bad = True

    # 检查5: "品类+焦虑/不足" 笼统模式（如 "显存焦虑"）
    _VAGUE_SUFFIXES = {"焦虑", "恐惧", "担忧"}
    if not is_bad:
        for suffix in _VAGUE_SUFFIXES:
            if clean.endswith(suffix) and len(clean) - len(suffix) <= 4:
                is_bad = True
                break

    # 检查6: 非痛点内容（测试/评测/对比）
    _NOT_PAIN = {"性能测试", "性能对比", "评测", "开箱", "拆解", "跑分"}
    if not is_bad:
        for kw in _NOT_PAIN:
            if kw in name:
                is_bad = True
                break

    if not is_bad:
        return name

    # 尝试用 evidence 替代
    evidence = data.get("evidence", "")
    if evidence and len(evidence) >= 4:
        short_ev = evidence[:40].split("。")[0].split(",")[0].split("，")[0].strip()
        if len(short_ev) >= 4:
            return short_ev

    return name  # 无法改善，保持原样


def _classify_quality_tier(data: dict) -> str:
    """根据推理链 + Munger 审查结果分层：gold / silver / bronze

    - gold: 有推理链 + Munger 审查通过（strong/moderate）
    - silver: 有隐藏需求但 Munger 弱/缺失
    - bronze: 无隐藏需求或无推理数据
    """
    inferred = data.get("inferred_need_obj")
    if not inferred or not isinstance(inferred, dict):
        return "bronze"

    hidden_need = inferred.get("hidden_need", "")
    reasoning_chain = inferred.get("reasoning_chain", [])
    munger = inferred.get("munger_review")

    if not hidden_need:
        return "bronze"

    if reasoning_chain and munger and isinstance(munger, dict):
        quality = munger.get("quality_level", "")
        if quality in ("strong", "moderate"):
            return "gold"

    return "silver"


def _detect_trend(pain_point: str, current_score: float) -> str:
    """检测趋势：对比最近 3 轮 PPHI 历史数据（规范化名称匹配）

    返回: "hot" | "rising" | "falling" | "stable" | "new"
    - hot: 连续 3 轮上升（PPHI 每轮增长 > 2）
    - rising: 比上一轮上升 > 3
    - falling: 比上一轮下降 > 3
    - stable: 变化 <= 3
    - new: 历史中未找到匹配
    """
    try:
        from src.utils.db import get_db
        normalized_current, _ = _normalize_pain_point(pain_point)

        with get_db() as conn:
            # 获取最近 5 轮（第 1 轮是当前轮，2-5 是历史）
            rows = conn.execute(
                """SELECT DISTINCT run_date FROM pphi_history
                   ORDER BY run_date DESC LIMIT 5"""
            ).fetchall()
            if len(rows) < 2:
                return "new"

            # 从第 2 轮开始查找匹配（跳过当前轮）
            prev_dates = [r["run_date"] for r in rows[1:]]
            placeholders = ",".join("?" * len(prev_dates))
            prev_points = conn.execute(
                f"""SELECT pain_point, pphi_score, run_date FROM pphi_history
                    WHERE run_date IN ({placeholders})
                    ORDER BY run_date DESC""",
                prev_dates
            ).fetchall()

        if not prev_points:
            return "new"

        # 收集该痛点在各轮的分数（按时间倒序）
        scores_by_date = {}
        for row in prev_points:
            normalized_prev, _ = _normalize_pain_point(row["pain_point"])
            if normalized_current == normalized_prev:
                scores_by_date[row["run_date"]] = row["pphi_score"]

        if not scores_by_date:
            return "new"

        # 按时间倒序排列历史分数
        sorted_dates = sorted(scores_by_date.keys(), reverse=True)
        prev_score = scores_by_date[sorted_dates[0]]

        # 检测连续上升（hot）：当前 > 上轮 > 上上轮 > 上上上轮，每轮增长 > 2
        if len(sorted_dates) >= 3:
            scores = [current_score] + [scores_by_date[d] for d in sorted_dates[:3]]
            consecutive_rises = all(scores[i] - scores[i + 1] > 2 for i in range(3))
            if consecutive_rises:
                return "hot"

        diff = current_score - prev_score
        if diff > 3:
            return "rising"
        elif diff < -3:
            return "falling"
        else:
            return "stable"
    except Exception:
        return "new"


def _save_rankings(rankings: list[dict], config: dict):
    """保存排名结果"""
    output_dir = Path(config.get("paths", {}).get("rankings", "outputs/pphi_rankings"))
    output_dir.mkdir(parents=True, exist_ok=True)

    output = {
        "timestamp": datetime.now().isoformat(),
        "total_pain_points": len(rankings),
        "rankings": rankings,
    }
    latest_file = output_dir / "latest.json"
    tmp_file = output_dir / "latest.json.tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    tmp_file.replace(latest_file)  # 原子替换

    date_str = datetime.now().strftime("%Y-%m-%d_%H%M")
    history_file = output_dir / f"rankings_{date_str}.json"
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
