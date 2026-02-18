#!/usr/bin/env python3
"""
GPU-Insight 主入口 — v2 三层漏斗 + GPU 标签 + PainInsight
"""

import os
import sys
import builtins
import functools
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
# 全局覆盖 print，确保所有模块都 flush
builtins.print = functools.partial(builtins.print, flush=True)
load_dotenv(Path(__file__).parent / ".env")

from src.utils.config import load_config
from src.utils.llm_client import LLMClient
from src.utils.cost_tracker import CostTracker


def check_agent_teams_available() -> bool:
    return os.getenv("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS") == "1"


def run_with_agent_teams(config: dict):
    print("启动 Agent Teams 模式（并行执行）")


def run_pipeline(config: dict):
    """完整 pipeline：抓取 → 清洗 → GPU标签 → 三层漏斗 → 痛点提取 → 推理需求 → PPHI → 报告"""
    print("启动串行模式")
    print(f"  时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()

    llm = LLMClient(config)
    cost_tracker = CostTracker(config)

    # 0. 预算检查
    budget = cost_tracker.check_budget()
    print(f"[预算] ${budget['monthly_cost']:.2f} / ${budget['budget']} ({budget['status']})")
    if budget["status"] in ("stop", "pause"):
        print("  预算不足，暂停运行")
        return
    print()

    # 1. 抓取
    from src.scrapers import scrape_all_forums
    print("[1] 数据采集...")
    raw_posts = scrape_all_forums(config)
    print(f"  获取 {len(raw_posts)} 条新讨论")
    if not raw_posts:
        print("  本轮无新数据，使用上轮排名")
        return
    print()

    # 2. 清洗
    from src.cleaners import clean_data
    print("[2] 数据清洗...")
    cleaned = clean_data(raw_posts, config)
    print(f"  去重后 {len(cleaned)} 条")
    print()

    # 3. GPU 产品标签（L0 本地，零 token）
    from src.utils.gpu_tagger import tag_posts
    print("[3] GPU 产品标签...")
    cleaned = tag_posts(cleaned)
    tagged_count = sum(1 for p in cleaned if p.get("_gpu_tags", {}).get("models"))
    print(f"  识别到具体型号: {tagged_count} 条 | 识别到品牌: {sum(1 for p in cleaned if p.get('_gpu_tags', {}).get('brands'))} 条")
    print()

    # 4. 三层漏斗
    from src.analyzers.funnel import run_funnel
    print("[4] 三层漏斗筛选...")
    deep_posts, light_posts = run_funnel(cleaned, llm)
    print()

    # 5. 痛点提取（对 deep + light 分别处理）
    from src.analyzers import analyze_pain_points, infer_hidden_needs, merge_pain_insights
    print(f"[5] 痛点提取（深度 {len(deep_posts)} + 轻度 {len(light_posts)} 条）...")
    status = cost_tracker.enforce_budget(llm)
    if status in ("stop", "pause"):
        print("  预算不足，跳过后续步骤")
        return
    all_posts_for_analysis = deep_posts + light_posts
    pain_points = analyze_pain_points(all_posts_for_analysis, config, llm)
    print(f"  提取 {len(pain_points)} 个痛点")
    print()

    # 6. 推理需求（对所有痛点做推理，优先 deep，控制数量）
    # 优先 deep_posts 来源的痛点，不足时补充 light_posts 来源的
    deep_ids = set(p.get("id") for p in deep_posts)
    deep_pains = [pp for pp in pain_points
                  if any(pid in deep_ids for pid in pp.get("source_post_ids", []))]
    light_pains = [pp for pp in pain_points if pp not in deep_pains]
    # 最多推导 5 个（deep 优先，不足用 light 补）
    pains_for_inference = (deep_pains + light_pains)[:5]
    print(f"[6] 隐藏需求推导（{len(pains_for_inference)} 个痛点：{len(deep_pains)} 深度 + {len(light_pains)} 轻度）...")
    status = cost_tracker.enforce_budget(llm)
    if status == "pause":
        print("  预算不足，跳过隐藏需求推导")
        hidden_needs = []
    elif status == "stop":
        print("  预算不足，停止运行")
        return
    else:
        hidden_needs = infer_hidden_needs(pains_for_inference, config, llm)
        print(f"  推导 {len(hidden_needs)} 个隐藏需求")
    print()

    # 6.5 Devil's Advocate 审查（防幻觉机制）
    from src.analyzers import devils_advocate_review
    if hidden_needs:
        print("[6.5] Devil's Advocate 审查（Munger 反向论证）...")
        status = cost_tracker.enforce_budget(llm)
        if status == "pause":
            print("  预算不足，跳过 Devil's Advocate 审查")
        elif status == "stop":
            print("  预算不足，停止运行")
            return
        else:
            hidden_needs = devils_advocate_review(hidden_needs, llm)
        print()

    # 7. 合并为 PainInsight
    print("[7] 合并 PainInsight...")
    insights = merge_pain_insights(pain_points, hidden_needs)
    print(f"  生成 {len(insights)} 个 PainInsight")
    print()

    # 8. PPHI 排名
    from src.rankers import calculate_pphi
    print("[8] PPHI 排名计算...")
    rankings = calculate_pphi(insights, config)
    print(f"  生成 {len(rankings)} 个排名")

    # 持久化：保存排名和痛点到 SQLite
    try:
        from src.utils.db import save_rankings, save_pain_points, get_post_count
        save_rankings(rankings)
        save_pain_points(insights)
        stats = get_post_count()
        print(f"  [DB] 累计帖子: {stats['total']} | 来源: {stats['by_source']}")
    except Exception as e:
        print(f"  [!] DB 保存失败(不影响运行): {e}")
    print()

    # 9. 生成报告
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

    # 10.5 热词自动发现（从 AI 分析结果 + 原始帖子 + DB 历史数据中提取）
    try:
        from src.utils.keywords import discover_hot_words, discover_from_db, update_discovered_keywords
        # 从当轮 AI 输出 + 原始帖子提取
        new_words = discover_hot_words(raw_posts, min_freq=2, insights=insights)
        # 从 DB 历史数据补充
        db_words = discover_from_db(min_mentions=2)
        # 合并（去重）
        merged_zh = list(dict.fromkeys((new_words.get("zh", []) + db_words.get("zh", []))))
        merged_en = list(dict.fromkeys((new_words.get("en", []) + db_words.get("en", []))))
        merged = {"zh": merged_zh, "en": merged_en}
        if merged["zh"] or merged["en"]:
            update_discovered_keywords(merged)
            print(f"[10.5] 热词发现: +{len(merged['zh'])} 中文, +{len(merged['en'])} 英文")
            if db_words.get("model_ranks"):
                print(f"  型号热度 Top5: {', '.join(db_words['model_ranks'][:5])}")
            print()
    except Exception as e:
        print(f"  [!] 热词发现失败(不影响运行): {e}")
        print()

    # 11. 输出 Top 10
    trend_icons = {"rising": "↑", "falling": "↓", "stable": "→", "new": "★"}
    print("=" * 70)
    print("  GPU-Insight Top 10 痛点排名")
    print("=" * 70)
    print()
    for r in rankings[:10]:
        gpu = r.get("gpu_tags", {})
        models = ", ".join(gpu.get("models", [])) or "-"
        mfrs = ", ".join(gpu.get("manufacturers", [])) or "-"
        urls = r.get("source_urls", [])
        url_str = urls[0][:60] if urls else "-"
        need = r.get("hidden_need", "")
        trend = trend_icons.get(r.get("trend", "new"), "★")
        print(f"  #{r['rank']:2d} {trend} [PPHI {r['pphi_score']:5.1f}] {r['pain_point']}")
        print(f"       GPU: {models} | 厂商: {mfrs}")
        print(f"       来源: {url_str}")
        if need:
            print(f"       需求: {need}")
        print()

    # 成本
    budget = cost_tracker.check_budget()
    print(f"[成本] 本轮: ${llm.total_cost:.4f} | Token: {llm.total_tokens} | 月度: ${budget['monthly_cost']:.2f} / ${budget['budget']}")
    print()
    print("本轮完成")


def main():
    print("=" * 50)
    print("  GPU-Insight 显卡用户痛点智能分析系统")
    print("=" * 50)
    print()

    try:
        config = load_config("config/config.yaml")
    except FileNotFoundError as e:
        print(f"错误: {e}")
        sys.exit(1)

    # 定时模式：python main.py --loop
    if "--loop" in sys.argv:
        import time
        interval = config.get("runtime", {}).get("cycle_interval_hours", 4) * 3600
        print(f"定时模式：每 {interval/3600:.0f} 小时运行一轮")
        print()
        while True:
            try:
                run_pipeline(config)
            except Exception as e:
                print(f"\n[!] Pipeline 异常: {e}")
            next_run = datetime.now().strftime('%H:%M')
            print(f"\n下一轮: {interval/3600:.0f}h 后")
            print("-" * 50)
            time.sleep(interval)
        return

    agent_teams_enabled = config.get("agent_teams", {}).get("enabled", False)
    agent_teams_available = check_agent_teams_available()

    if agent_teams_enabled and agent_teams_available:
        run_with_agent_teams(config)
    else:
        if agent_teams_enabled and not agent_teams_available:
            print("Agent Teams 已配置但不可用，降级为串行模式")
            print()
        run_pipeline(config)


if __name__ == "__main__":
    main()
