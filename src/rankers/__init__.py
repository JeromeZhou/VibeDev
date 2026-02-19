"""GPU-Insight PPHI 排名计算模块 — v2 支持 PainInsight 结构"""

import json
import math
from datetime import datetime
from pathlib import Path
from src.utils.config import get_pphi_weights


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

    # 聚合同类痛点
    aggregated = _aggregate(all_insights)

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


def _aggregate(insights: list[dict]) -> dict:
    """聚合同类痛点，合并 GPU 标签和 URL（支持语义去重）"""
    agg = {}
    name_mapping = {}  # 规范化名称 -> 最佳展示名称

    for item in insights:
        pp = item.get("pain_point", "未知")
        normalized_pp, original_pp = _normalize_pain_point(pp)

        # 使用规范化名称作为聚合 key
        if normalized_pp not in agg:
            # 选择最具描述性的名称作为展示名（优先选择带"显卡"前缀的完整名称）
            name_mapping[normalized_pp] = original_pp
            agg[normalized_pp] = {
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
            # 如果新名称更具描述性（更长或带"显卡"前缀），则更新展示名
            current_display = name_mapping[normalized_pp]
            if len(original_pp) > len(current_display) or (original_pp.startswith("显卡") and not current_display.startswith("显卡")):
                name_mapping[normalized_pp] = original_pp

        # count: 如果 insight 来自历史累积（已有 mentions），用 mentions；否则 +1
        hist_mentions = item.get("_hist_mentions", 0)
        agg[normalized_pp]["count"] += hist_mentions if hist_mentions > 0 else 1

        # 来源
        for pid in item.get("source_post_ids", []):
            src = pid.split("_")[0] if "_" in pid else "unknown"
            agg[normalized_pp]["sources"].add(src)

        # URL
        for url in item.get("source_urls", []):
            if url and url not in agg[normalized_pp]["source_urls"]:
                agg[normalized_pp]["source_urls"].append(url)

        # GPU 标签合并
        tags = item.get("gpu_tags", {})
        for key in ("brands", "models", "series", "manufacturers"):
            agg[normalized_pp]["gpu_tags"][key].update(tags.get(key, []))

        # 互动数据累加
        agg[normalized_pp]["total_replies"] += item.get("total_replies", 0)
        agg[normalized_pp]["total_likes"] += item.get("total_likes", 0)

        # 时间戳收集
        ts = item.get("earliest_timestamp", "")
        if ts:
            agg[normalized_pp]["timestamps"].append(ts)

        # 推理需求
        need = item.get("inferred_need")
        if need and need.get("hidden_need"):
            agg[normalized_pp]["hidden_need"] = need["hidden_need"]
            agg[normalized_pp]["confidences"].append(need.get("confidence", 0.5))
            # 保存完整的推理对象（包含 reasoning_chain 和 munger_review）
            agg[normalized_pp]["inferred_need_obj"] = need
            # 提取 Munger 质量评级
            munger_review = need.get("munger_review", {})
            if munger_review:
                agg[normalized_pp]["munger_quality"] = munger_review.get("quality_level", "unknown")
                agg[normalized_pp]["needs_verification"] = need.get("_needs_verification", False)

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
    """聚合层名称守卫：检测笼统名称，用 evidence 替代

    注意：不使用 hidden_need 替代，因为那是"需求"不是"痛点"
    """
    clean = name.strip()
    for prefix in ("显卡", "GPU"):
        if clean.startswith(prefix):
            clean = clean[len(prefix):]
    for suffix in ("问题", "不足", "困难", "不好"):
        if clean.endswith(suffix):
            clean = clean[:-len(suffix)].strip()

    if clean not in _CATEGORY_NAMES_R and len(clean) >= 3:
        return name  # 名称足够具体，不需要修正

    # 尝试用 evidence 替代
    evidence = data.get("evidence", "")
    if evidence and len(evidence) >= 4:
        short_ev = evidence[:40].split("。")[0].split(",")[0].split("，")[0].strip()
        if len(short_ev) >= 4:
            return short_ev

    # 无 evidence 时，尝试从 source_urls 推断上下文
    # 对于历史数据，保留原名但加标记（下轮新数据进来时会自然替换）
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
