#!/usr/bin/env python3
"""GPU-Insight 快速完成 — 从已有痛点直接跑 PPHI 排名（跳过 LLM 调用）"""

import os
import sys
import json
import builtins
import functools
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
builtins.print = functools.partial(builtins.print, flush=True)
load_dotenv(Path(__file__).parent / ".env")

from src.utils.config import load_config


def main():
    print("=" * 50)
    print("  GPU-Insight 快速完成（跳过 LLM 调用）")
    print("=" * 50)
    print()

    config = load_config("config/config.yaml")

    # 从 jsonl 加载最新的痛点（取最后 30 条，即最新一轮）
    pain_file = Path("data/processed/pain_points_2026-02-17.jsonl")
    all_pains = []
    with open(pain_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    all_pains.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    # 取最后一轮的痛点（最后 24 条，因为上一轮提取了 24 个）
    pain_points = all_pains[-24:]
    print(f"[加载] 从 jsonl 加载 {len(pain_points)} 个痛点")
    for pp in pain_points[:5]:
        print(f"  - {pp.get('pain_point', '?')[:60]}")
    print(f"  ... 共 {len(pain_points)} 个")
    print()

    # 构造 insights（无隐藏需求，跳过 step 6/6.5）
    insights = []
    for pp in pain_points:
        insights.append({
            "pain_point": pp.get("pain_point", ""),
            "category": pp.get("category", "其他"),
            "emotion_intensity": pp.get("emotion_intensity", 0.0),
            "affected_users": pp.get("affected_users", ""),
            "evidence": pp.get("evidence", ""),
            "gpu_tags": pp.get("gpu_tags", {}),
            "source_post_ids": pp.get("source_post_ids", []),
            "source_urls": pp.get("source_urls", []),
            "total_replies": pp.get("total_replies", 0),
            "total_likes": pp.get("total_likes", 0),
            "earliest_timestamp": pp.get("earliest_timestamp", ""),
            "inferred_need": None,  # 晚上跳过，白天补
        })

    print(f"[7] 合并 PainInsight（无隐藏需求）...")
    print(f"  生成 {len(insights)} 个 PainInsight")
    print()

    # 8. PPHI 排名
    from src.rankers import calculate_pphi
    print("[8] PPHI 排名计算...")
    rankings = calculate_pphi(insights, config)
    print(f"  生成 {len(rankings)} 个排名")

    # 保存到 DB
    try:
        from src.utils.db import save_rankings, save_pain_points, get_post_count
        save_rankings(rankings)
        save_pain_points(insights)
        stats = get_post_count()
        print(f"  [DB] 累计帖子: {stats['total']} | 来源: {stats['by_source']}")
    except Exception as e:
        print(f"  [!] DB 保存失败: {e}")
    print()

    # 9. 报告
    from src.reporters import generate_report
    print("[9] 生成报告...")
    report_path = generate_report(rankings, config)
    print(f"  报告：{report_path}")
    print()

    # Top 10
    trend_icons = {"rising": "↑", "falling": "↓", "stable": "→", "new": "★"}
    print("=" * 70)
    print("  GPU-Insight Top 10 痛点排名")
    print("=" * 70)
    print()
    for r in rankings[:10]:
        gpu = r.get("gpu_tags", {})
        models = ", ".join(gpu.get("models", [])) or "-"
        need = r.get("hidden_need", "")
        trend = trend_icons.get(r.get("trend", "new"), "★")
        munger = r.get("munger_quality", "")
        munger_str = f" [{munger}]" if munger and munger != "unknown" else ""
        print(f"  #{r['rank']:2d} {trend} [PPHI {r['pphi_score']:5.1f}] {r['pain_point']}{munger_str}")
        print(f"       GPU: {models}")
        print(f"       mentions: {r['mentions']} | replies: {r.get('total_replies',0)} | likes: {r.get('total_likes',0)}")
        if need:
            print(f"       需求: {need}")
        print()

    print("本轮完成（隐藏需求推导跳过，白天补充）")


if __name__ == "__main__":
    main()
