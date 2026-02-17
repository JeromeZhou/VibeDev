#!/usr/bin/env python3
"""GPU-Insight 断点续跑 — 跳过数据采集，从已有帖子开始分析"""

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
from src.utils.llm_client import LLMClient
from src.utils.cost_tracker import CostTracker

def main():
    print("=" * 50)
    print("  GPU-Insight 断点续跑（跳过数据采集）")
    print("=" * 50)
    print()

    config = load_config("config/config.yaml")
    llm = LLMClient(config)
    cost_tracker = CostTracker(config)

    budget = cost_tracker.check_budget()
    print(f"[预算] ${budget['monthly_cost']:.2f} / ${budget['budget']} ({budget['status']})")
    print()

    # 从 DB 加载已有帖子
    from src.utils.db import get_db
    conn = get_db()
    rows = conn.execute("SELECT id, source, title, url, replies, likes, gpu_tags, timestamp FROM posts ORDER BY id").fetchall()
    conn.close()

    posts = []
    for r in rows:
        gpu_tags = {}
        if r["gpu_tags"]:
            try:
                gpu_tags = json.loads(r["gpu_tags"])
            except Exception:
                pass
        posts.append({
            "id": r["id"],
            "source": r["source"],
            "_source": r["source"],
            "title": r["title"] or "",
            "content": r["title"] or "",  # DB 没存 content，用 title
            "url": r["url"] or "",
            "replies": r["replies"] or 0,
            "likes": r["likes"] or 0,
            "timestamp": r["timestamp"] or "",
            "_gpu_tags": gpu_tags,
        })

    print(f"[1] 从 DB 加载 {len(posts)} 条帖子（跳过抓取）")
    print()

    # 3. GPU 标签
    from src.utils.gpu_tagger import tag_posts
    print("[3] GPU 产品标签...")
    posts = tag_posts(posts)
    tagged_count = sum(1 for p in posts if p.get("_gpu_tags", {}).get("models"))
    print(f"  识别到具体型号: {tagged_count} 条 | 识别到品牌: {sum(1 for p in posts if p.get('_gpu_tags', {}).get('brands'))} 条")
    print()

    # 4. 三层漏斗
    from src.analyzers.funnel import run_funnel
    print("[4] 三层漏斗筛选...")
    deep_posts, light_posts = run_funnel(posts, llm)
    print()

    # 5. 痛点提取
    from src.analyzers import analyze_pain_points, infer_hidden_needs, merge_pain_insights
    print(f"[5] 痛点提取（深度 {len(deep_posts)} + 轻度 {len(light_posts)} 条）...")
    all_posts = deep_posts + light_posts
    pain_points = analyze_pain_points(all_posts, config, llm)
    print(f"  提取 {len(pain_points)} 个痛点")
    print()

    # 6. 隐藏需求推导
    deep_ids = set(p.get("id") for p in deep_posts)
    deep_pains = [pp for pp in pain_points if any(pid in deep_ids for pid in pp.get("source_post_ids", []))]
    light_pains = [pp for pp in pain_points if pp not in deep_pains]
    pains_for_inference = (deep_pains + light_pains)[:5]
    print(f"[6] 隐藏需求推导（{len(pains_for_inference)} 个痛点）...")
    hidden_needs = infer_hidden_needs(pains_for_inference, config, llm)
    print(f"  推导 {len(hidden_needs)} 个隐藏需求")
    print()

    # 6.5 Munger 审查
    from src.analyzers import devils_advocate_review
    if hidden_needs:
        print("[6.5] Devil's Advocate 审查...")
        hidden_needs = devils_advocate_review(hidden_needs, llm)
        print()

    # 7. 合并
    print("[7] 合并 PainInsight...")
    insights = merge_pain_insights(pain_points, hidden_needs)
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

    # 10. 更新共识
    from src.reporters import update_consensus
    print("[10] 更新共识...")
    cost_info = {
        "round_cost": llm.total_cost,
        "round_tokens": llm.total_tokens,
        "monthly_cost": cost_tracker.get_monthly_cost(),
        "budget": cost_tracker.budget,
    }
    update_consensus(rankings, cost_info, config)
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
        print(f"  #{r['rank']:2d} {trend} [PPHI {r['pphi_score']:5.1f}] {r['pain_point']}")
        print(f"       GPU: {models}")
        if need:
            print(f"       需求: {need}")
        print()

    print(f"[成本] 本轮: ${llm.total_cost:.4f} | Token: {llm.total_tokens}")
    print("本轮完成")

if __name__ == "__main__":
    main()
