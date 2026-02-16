"""GPU-Insight PPHI 排名计算模块"""

import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from src.utils.config import get_pphi_weights


def calculate_pphi(reviewed: list[dict], config: dict) -> list[dict]:
    """计算 PPHI 指数并生成排名"""
    if not reviewed:
        return []

    weights = get_pphi_weights(config)
    decay_rate = config.get("pphi", {}).get("decay_rate_per_day", 0.05)
    source_scores = {
        "chiphell": 1.0, "reddit": 0.9, "nga": 0.8,
        "guru3d": 0.8, "rog": 0.7, "tieba": 0.6, "twitter": 0.5,
    }

    # 聚合同类痛点
    aggregated = _aggregate_pain_points(reviewed)

    # 计算 PPHI
    rankings = []
    for pain_point, data in aggregated.items():
        mention_count = data["count"]
        sources = data["sources"]
        avg_source_score = sum(source_scores.get(s, 0.5) for s in sources) / max(len(sources), 1)
        interaction = data.get("avg_interaction", 0)
        days_old = data.get("days_old", 0)

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
            "hidden_need": data.get("hidden_need", ""),
            "confidence": data.get("avg_confidence", 0),
            "trend": _detect_trend(pain_point, pphi),
        })

    # 排序
    rankings.sort(key=lambda x: x["pphi_score"], reverse=True)
    for i, r in enumerate(rankings):
        r["rank"] = i + 1

    # 保存
    _save_rankings(rankings, config)
    return rankings


def _aggregate_pain_points(reviewed: list[dict]) -> dict:
    """聚合同类痛点"""
    agg = {}
    for item in reviewed:
        pp = item.get("pain_point", item.get("hidden_need", "未知"))
        if pp not in agg:
            agg[pp] = {"count": 0, "sources": set(), "confidences": [], "hidden_need": ""}
        agg[pp]["count"] += 1
        source = item.get("_source", "unknown")
        agg[pp]["sources"].add(source)
        agg[pp]["confidences"].append(item.get("adjusted_confidence", item.get("confidence", 0.5)))
        if item.get("hidden_need"):
            agg[pp]["hidden_need"] = item["hidden_need"]

    for pp, data in agg.items():
        data["avg_confidence"] = sum(data["confidences"]) / max(len(data["confidences"]), 1)
        data["days_old"] = 0  # TODO: 从首次发现时间计算
        del data["confidences"]

    return agg


def _detect_trend(pain_point: str, current_score: float) -> str:
    """检测趋势（简化版：首次运行都是 new）"""
    # TODO: 对比历史数据
    return "new"


def _save_rankings(rankings: list[dict], config: dict):
    """保存排名结果"""
    output_dir = Path(config.get("paths", {}).get("rankings", "outputs/pphi_rankings"))
    output_dir.mkdir(parents=True, exist_ok=True)

    # 保存 latest.json
    output = {
        "timestamp": datetime.now().isoformat(),
        "total_pain_points": len(rankings),
        "rankings": rankings[:20],  # Top 20
    }
    latest_file = output_dir / "latest.json"
    with open(latest_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 保存历史
    date_str = datetime.now().strftime("%Y-%m-%d_%H%M")
    history_file = output_dir / f"rankings_{date_str}.json"
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
