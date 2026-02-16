"""GPU-Insight 真实 LLM Pipeline 测试 — 用模拟数据 + GLM-5 做真实 AI 分析"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

# UTF-8 输出
sys.stdout.reconfigure(encoding='utf-8')

# 加载 .env
from dotenv import load_dotenv
load_dotenv()

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.mock_data import generate_mock_data
from src.utils.config import load_config
from src.utils.llm_client import LLMClient
from src.utils.cost_tracker import CostTracker
from src.cleaners import clean_data
from src.analyzers import analyze_pain_points, infer_hidden_needs, council_review
from src.rankers import calculate_pphi
from src.reporters import generate_report


def main():
    print("=" * 60)
    print("  GPU-Insight 真实 LLM Pipeline（GLM-5 via SiliconFlow）")
    print("=" * 60)
    print()

    config = load_config("config/config.yaml")
    llm = LLMClient(config)
    cost = CostTracker(config)

    # 1. 模拟数据
    print("[阶段1] 生成模拟数据...")
    raw = generate_mock_data()
    print(f"  生成 {len(raw)} 条讨论")
    print()

    # 2. 清洗
    print("[阶段2] 数据清洗...")
    cleaned = clean_data(raw, config)
    print(f"  去重后 {len(cleaned)} 条")
    print()

    # 3. 痛点提取（真实 LLM）
    print("[阶段3] 痛点提取（GLM-5 真实分析）...")
    pain_points = analyze_pain_points(cleaned, config, llm)
    print(f"  提取 {len(pain_points)} 个痛点")
    for pp in pain_points[:5]:
        print(f"    [{pp.get('category','?')}] {pp.get('pain_point','?')}")
    if len(pain_points) > 5:
        print(f"    ... 还有 {len(pain_points)-5} 个")
    print()

    # 4. 隐藏需求推导（真实 LLM）
    print("[阶段4] 隐藏需求推导（GLM-5 深度推理）...")
    insights = infer_hidden_needs(pain_points[:5], config, llm)  # 限制 5 个，控制成本
    print(f"  推导 {len(insights)} 个隐藏需求")
    for ins in insights:
        chain = ins.get('reasoning_chain', [])
        print(f"    {ins.get('pain_point','?')}")
        print(f"      -> {ins.get('hidden_need','?')} (置信度: {ins.get('confidence',0):.0%})")
        if chain:
            print(f"      推理链: {' -> '.join(chain[:3])}")
    print()

    # 5. Council 评审（真实 LLM）
    print("[阶段5] Expert Council 评审（GLM-5 多视角）...")
    reviewed = council_review(insights, config, llm)
    print(f"  通过 {len(reviewed)} / {len(insights)} 个")
    print()

    # 6. PPHI 排名
    print("[阶段6] PPHI 排名...")
    rankings = calculate_pphi(reviewed if reviewed else insights, config)
    for r in rankings[:10]:
        print(f"    #{r['rank']} {r['pain_point']} — PPHI: {r['pphi_score']}")
    print()

    # 7. 报告
    print("[阶段7] 生成报告...")
    report = generate_report(rankings, config)
    print(f"  报告: {report}")
    print()

    # 成本
    budget = cost.check_budget()
    print(f"[成本] 本轮: ${llm.total_cost:.4f} | Token: {llm.total_tokens}")
    print(f"[成本] 月度: ${budget['monthly_cost']:.4f} / ${budget['budget']}")
    print()
    print("Pipeline 完成!")


if __name__ == "__main__":
    main()
