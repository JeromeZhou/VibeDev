#!/usr/bin/env python3
"""测试 Devil's Advocate 审查机制"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.config import load_config
from src.utils.llm_client import LLMClient
from src.analyzers import devils_advocate_review

def test_devils_advocate():
    """测试 Munger 审查功能"""
    print("=" * 60)
    print("  Devil's Advocate 审查机制测试")
    print("=" * 60)
    print()

    # 加载配置
    config = load_config("config/config.yaml")
    llm = LLMClient(config)

    # 模拟隐藏需求数据
    test_hidden_needs = [
        {
            "pain_point": "RTX 4090 功耗过高",
            "hidden_need": "用户需要更节能的高性能显卡",
            "reasoning_chain": [
                "RTX 4090 TDP 达到 450W",
                "高功耗导致电费增加和散热压力",
                "用户希望在保持性能的同时降低功耗"
            ],
            "confidence": 0.85,
            "category": "功能需求"
        },
        {
            "pain_point": "显卡价格太贵",
            "hidden_need": "用户渴望获得社会认同和炫耀资本",
            "reasoning_chain": [
                "用户抱怨价格高",
                "但仍然购买高端显卡",
                "说明真正需求是炫耀而非性价比"
            ],
            "confidence": 0.7,
            "category": "社会需求"
        },
        {
            "pain_point": "驱动更新频繁出问题",
            "hidden_need": "用户需要更稳定的驱动版本",
            "reasoning_chain": [
                "用户反馈驱动更新后游戏崩溃",
                "回滚到旧版本才能正常使用",
                "用户需要经过充分测试的稳定驱动"
            ],
            "confidence": 0.9,
            "category": "功能需求"
        },
        {
            "pain_point": "光追性能不足",
            "hidden_need": "用户需要更强大的 RT Core",
            "reasoning_chain": [
                "开启光追后帧率下降明显",
                "用户希望在光追开启时保持流畅"
            ],
            "confidence": 0.65,
            "category": "功能需求"
        }
    ]

    print(f"测试数据: {len(test_hidden_needs)} 个隐藏需求")
    print()

    # 执行 Munger 审查
    print("开始 Devil's Advocate 审查...")
    print("-" * 60)
    reviewed = devils_advocate_review(test_hidden_needs, llm)
    print("-" * 60)
    print()

    # 输出结果
    print("审查结果:")
    print("=" * 60)
    for i, need in enumerate(reviewed, 1):
        print(f"\n[{i}] {need['pain_point']}")
        print(f"    推导需求: {need['hidden_need']}")
        print(f"    原始置信度: {need.get('confidence', 0):.2f}")

        munger = need.get('munger_review')
        if munger:
            approved = munger.get('approved', False)
            status = "✅ 通过" if approved else "❌ 否决"
            print(f"    Munger 审查: {status}")
            if munger.get('adjusted_confidence'):
                print(f"    调整后置信度: {munger['adjusted_confidence']:.2f}")
            if munger.get('rejection_reason'):
                print(f"    否决原因: {munger['rejection_reason']}")
            if munger.get('comment'):
                print(f"    评价: {munger['comment']}")
        else:
            print(f"    Munger 审查: 跳过（置信度 < 0.6）")

        if need.get('munger_rejected'):
            print(f"    ⚠️  已标记为被否决")

    print()
    print("=" * 60)
    print(f"总成本: ${llm.total_cost:.4f} | Token: {llm.total_tokens}")
    print()

if __name__ == "__main__":
    test_devils_advocate()
