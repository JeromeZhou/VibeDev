"""GPU-Insight PPHI 排名计算模块 — v2 支持 PainInsight 结构"""

import json
from datetime import datetime
from pathlib import Path
from src.utils.config import get_pphi_weights


def calculate_pphi(insights: list[dict], config: dict) -> list[dict]:
    """计算 PPHI 指数并生成排名（累积历史 + 当轮新增）"""
    weights = get_pphi_weights(config)
    decay_rate = config.get("pphi", {}).get("decay_rate_per_day", 0.05)
    source_scores = {
        "chiphell": 1.0, "reddit": 0.9, "videocardz": 0.85,
        "nga": 0.8, "guru3d": 0.8, "rog": 0.7, "tieba": 0.6, "twitter": 0.5,
    }

    # 加载历史痛点 + 当轮新增，合并后统一排名
    all_insights = _load_historical_insights() + (insights or [])
    if not all_insights:
        return []

    # 聚合同类痛点
    aggregated = _aggregate(all_insights)

    # 计算 PPHI
    rankings = []
    for pain_point, data in aggregated.items():
        # 用关联帖子数作为频率指标（比痛点文本匹配更准确）
        mention_count = max(data["count"], len(data.get("source_urls", [])))
        sources = data["sources"]
        avg_source_score = sum(source_scores.get(s, 0.5) for s in sources) / max(len(sources), 1)
        interaction = data.get("avg_interaction", 0)
        days_old = min(data.get("days_old", 0), 30)  # 封顶30天，避免过度衰减

        pphi = (
            weights.get("frequency", 0.3) * min(mention_count / 10, 10) * 10
            + weights.get("source_quality", 0.4) * avg_source_score * 100
            + weights.get("interaction", 0.2) * min(interaction / 100, 1) * 100
            - weights.get("time_decay", 0.1) * days_old * decay_rate * 100
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
        })

    rankings.sort(key=lambda x: x["pphi_score"], reverse=True)
    for i, r in enumerate(rankings):
        r["rank"] = i + 1

    _save_rankings(rankings, config)
    return rankings


def _load_historical_insights() -> list[dict]:
    """从 DB 加载历史痛点，转换为 insights 格式供聚合"""
    try:
        from src.utils.db import get_db
        conn = get_db()
        rows = conn.execute(
            """SELECT pain_point, category, mentions, sources, gpu_tags,
                      source_urls, evidence, hidden_need, confidence, pphi_score
               FROM pain_points
               ORDER BY run_date DESC"""
        ).fetchall()
        conn.close()

        insights = []
        for r in rows:
            sources_list = json.loads(r["sources"]) if r["sources"] else []
            gpu_tags = json.loads(r["gpu_tags"]) if r["gpu_tags"] else {}
            source_urls = json.loads(r["source_urls"]) if r["source_urls"] else []

            # 构造 source_post_ids（从 source_urls 推断来源）
            source_post_ids = []
            for url in source_urls:
                if "reddit" in url:
                    source_post_ids.append(f"reddit_{url.split('/')[-1]}")
                elif "nga" in url:
                    source_post_ids.append(f"nga_{url.split('tid=')[-1]}")
                elif "videocardz" in url:
                    source_post_ids.append(f"videocardz_{url.split('/')[-1]}")
                else:
                    source_post_ids.append(f"unknown_{url[-20:]}")

            hidden_need_obj = None
            if r["hidden_need"]:
                hidden_need_obj = {
                    "hidden_need": r["hidden_need"],
                    "confidence": r["confidence"] or 0.5,
                }

            insights.append({
                "pain_point": r["pain_point"],
                "category": r["category"] or "",
                "affected_users": "",
                "evidence": r["evidence"] or "",
                "source_post_ids": source_post_ids,
                "source_urls": source_urls,
                "gpu_tags": gpu_tags,
                "inferred_need": hidden_need_obj,
                "total_replies": 0,
                "total_likes": 0,
                "earliest_timestamp": "",
            })
        return insights
    except Exception as e:
        print(f"  [!] 加载历史痛点失败: {e}")
        return []


def _aggregate(insights: list[dict]) -> dict:
    """聚合同类痛点，合并 GPU 标签和 URL"""
    agg = {}
    for item in insights:
        pp = item.get("pain_point", "未知")
        if pp not in agg:
            agg[pp] = {
                "count": 0,
                "sources": set(),
                "source_urls": [],
                "gpu_tags": {"brands": set(), "models": set(), "series": set(), "manufacturers": set()},
                "confidences": [],
                "hidden_need": "",
                "category": item.get("category", ""),
                "affected_users": item.get("affected_users", ""),
                "evidence": item.get("evidence", ""),
                "total_replies": 0,
                "total_likes": 0,
                "timestamps": [],
            }

        agg[pp]["count"] += 1

        # 来源
        for pid in item.get("source_post_ids", []):
            src = pid.split("_")[0] if "_" in pid else "unknown"
            agg[pp]["sources"].add(src)

        # URL
        for url in item.get("source_urls", []):
            if url and url not in agg[pp]["source_urls"]:
                agg[pp]["source_urls"].append(url)

        # GPU 标签合并
        tags = item.get("gpu_tags", {})
        for key in ("brands", "models", "series", "manufacturers"):
            agg[pp]["gpu_tags"][key].update(tags.get(key, []))

        # 互动数据累加
        agg[pp]["total_replies"] += item.get("total_replies", 0)
        agg[pp]["total_likes"] += item.get("total_likes", 0)

        # 时间戳收集
        ts = item.get("earliest_timestamp", "")
        if ts:
            agg[pp]["timestamps"].append(ts)

        # 推理需求
        need = item.get("inferred_need")
        if need and need.get("hidden_need"):
            agg[pp]["hidden_need"] = need["hidden_need"]
            agg[pp]["confidences"].append(need.get("confidence", 0.5))

    # 后处理
    now = datetime.now()
    for pp, data in agg.items():
        data["avg_confidence"] = sum(data["confidences"]) / max(len(data["confidences"]), 1) if data["confidences"] else 0
        # 计算互动分 = replies + likes
        data["avg_interaction"] = data["total_replies"] + data["total_likes"]
        # 从最早时间戳计算 days_old
        data["days_old"] = 0
        if data["timestamps"]:
            try:
                earliest = min(data["timestamps"])
                earliest_dt = datetime.fromisoformat(earliest.replace("Z", "+00:00").replace("+00:00", ""))
                data["days_old"] = max(0, (now - earliest_dt).days)
            except (ValueError, TypeError):
                data["days_old"] = 0
        data["gpu_tags"] = {k: sorted(v) for k, v in data["gpu_tags"].items()}
        del data["confidences"]
        del data["timestamps"]

    return agg


def _detect_trend(pain_point: str, current_score: float) -> str:
    """检测趋势：对比上一轮 PPHI 历史数据"""
    try:
        from src.utils.db import get_db
        conn = get_db()
        # 获取最近一次运行的数据（排除当前运行）
        rows = conn.execute(
            """SELECT DISTINCT run_date FROM pphi_history
               ORDER BY run_date DESC LIMIT 2"""
        ).fetchall()
        if len(rows) < 2:
            conn.close()
            return "new"

        prev_date = rows[1]["run_date"]  # 上一轮的日期
        prev_points = conn.execute(
            """SELECT pain_point, pphi_score FROM pphi_history
               WHERE run_date = ?""",
            (prev_date,)
        ).fetchall()
        conn.close()

        if not prev_points:
            return "new"

        # 模糊匹配：找包含相同关键词的痛点
        best_match_score = None
        pp_lower = pain_point.lower()
        for row in prev_points:
            prev_pp = row["pain_point"].lower()
            # 简单关键词重叠检测
            pp_chars = set(pp_lower)
            prev_chars = set(prev_pp)
            overlap = len(pp_chars & prev_chars) / max(len(pp_chars | prev_chars), 1)
            if overlap > 0.5:
                best_match_score = row["pphi_score"]
                break

        if best_match_score is None:
            return "new"

        diff = current_score - best_match_score
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
        "rankings": rankings[:20],
    }
    latest_file = output_dir / "latest.json"
    with open(latest_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    date_str = datetime.now().strftime("%Y-%m-%d_%H%M")
    history_file = output_dir / f"rankings_{date_str}.json"
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
