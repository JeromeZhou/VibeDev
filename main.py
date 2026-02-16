#!/usr/bin/env python3
"""
GPU-Insight 主入口
支持 Agent Teams 和串行模式
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(Path(__file__).parent / ".env")

from src.utils.config import load_config
from src.utils.llm_client import LLMClient
from src.utils.cost_tracker import CostTracker


def check_agent_teams_available() -> bool:
    """检测 Agent Teams 是否可用"""
    return os.getenv("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS") == "1"


def run_with_agent_teams(config: dict):
    """模式 A：使用 Agent Teams（并行执行）"""
    print("🚀 启动 Agent Teams 模式（并行执行）")
    print("   由 auto-loop.sh 触发 Claude Code Agent Teams")
    # Agent Teams 模式下，由 Claude Code 协调各 Agent
    # 此函数作为入口标记，实际执行由 .claude/agents/ 定义驱动


def run_without_agent_teams(config: dict):
    """模式 B：串行模式（不依赖 Agent Teams）"""
    print("🐢 启动串行模式（Agent Teams 未启用）")
    print(f"   时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()

    llm = LLMClient(config)
    cost_tracker = CostTracker(config)

    # 0. 检查预算
    budget = cost_tracker.check_budget()
    print(f"💰 预算状态：${budget['monthly_cost']:.2f} / ${budget['budget']} ({budget['status']})")
    if budget["status"] in ("stop", "pause"):
        print("🛑 预算不足，暂停运行")
        return
    print()

    # 1. 抓取数据
    from src.scrapers import scrape_all_forums
    print("📥 [阶段1] 数据采集...")
    raw_posts = scrape_all_forums(config)
    print(f"   获取 {len(raw_posts)} 条讨论")
    if not raw_posts:
        print("   ⚠️ 未获取到数据，跳过本轮")
        return
    print()

    # 2. 清洗数据
    from src.cleaners import clean_data
    print("🧹 [阶段2] 数据清洗...")
    cleaned = clean_data(raw_posts, config)
    print(f"   去重后剩余 {len(cleaned)} 条")
    print()

    # 3. 痛点提取
    from src.analyzers import analyze_pain_points
    print("🔍 [阶段3] 痛点提取...")
    pain_points = analyze_pain_points(cleaned, config, llm)
    print(f"   提取 {len(pain_points)} 个痛点")
    print()

    # 4. 隐藏需求推导
    from src.analyzers import infer_hidden_needs
    print("💡 [阶段4] 隐藏需求推导...")
    insights = infer_hidden_needs(pain_points, config, llm)
    print(f"   推导 {len(insights)} 个隐藏需求")
    print()

    # 5. Expert Council 评审
    from src.analyzers import council_review
    print("👥 [阶段5] Expert Council 评审...")
    reviewed = council_review(insights, config, llm)
    print(f"   通过 {len(reviewed)} 个高置信度需求")
    print()

    # 6. PPHI 排名
    from src.rankers import calculate_pphi
    print("📊 [阶段6] PPHI 排名计算...")
    rankings = calculate_pphi(reviewed, config)
    print(f"   生成 {len(rankings)} 个排名")
    print()

    # 7. 生成报告
    from src.reporters import generate_report
    print("📝 [阶段7] 生成报告...")
    report_path = generate_report(rankings, config)
    print(f"   报告：{report_path}")
    print()

    # 8. 成本核算
    budget = cost_tracker.check_budget()
    print(f"💰 本轮成本：${llm.total_cost:.4f} | 月度累计：${budget['monthly_cost']:.2f} / ${budget['budget']}")
    print()
    print("✅ 本轮循环完成！")


def main():
    """主函数"""
    print("=" * 50)
    print("  GPU-Insight 显卡用户痛点智能分析系统")
    print("=" * 50)
    print()

    # 加载配置
    try:
        config = load_config("config/config.yaml")
    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)

    # 检查运行模式
    agent_teams_enabled = config.get("agent_teams", {}).get("enabled", False)
    agent_teams_available = check_agent_teams_available()

    if agent_teams_enabled and agent_teams_available:
        run_with_agent_teams(config)
    else:
        if agent_teams_enabled and not agent_teams_available:
            print("⚠️  Agent Teams 已配置但不可用，降级为串行模式")
            print()
        run_without_agent_teams(config)


if __name__ == "__main__":
    main()
