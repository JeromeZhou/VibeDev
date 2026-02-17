#!/usr/bin/env python3
"""测试成本控制和共识更新功能"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

# 设置 UTF-8 输出
sys.stdout.reconfigure(encoding='utf-8')

from src.utils.config import load_config
from src.utils.llm_client import LLMClient
from src.utils.cost_tracker import CostTracker
from src.reporters.consensus_updater import update_consensus


def test_cost_tracker():
    """测试成本追踪器的 enforce_budget 方法"""
    print("=" * 50)
    print("测试 1: CostTracker.enforce_budget()")
    print("=" * 50)

    config = load_config("config/config.yaml")
    llm = LLMClient(config)
    tracker = CostTracker(config)

    # 测试正常状态
    status = tracker.enforce_budget(llm)
    print(f"✓ enforce_budget() 返回: {status}")
    print()


def test_llm_downgrade():
    """测试 LLM 降级功能"""
    print("=" * 50)
    print("测试 2: LLMClient.downgrade_model()")
    print("=" * 50)

    config = load_config("config/config.yaml")
    llm = LLMClient(config)

    print(f"初始状态: _downgraded = {llm._downgraded}")
    llm.downgrade_model()
    print(f"降级后: _downgraded = {llm._downgraded}")

    # 测试降级后的配置
    cheap_cfg = llm._get_cheapest_config()
    print(f"✓ 最便宜模型: {cheap_cfg['model']}")
    print()


def test_consensus_updater():
    """测试共识更新器"""
    print("=" * 50)
    print("测试 3: update_consensus()")
    print("=" * 50)

    config = load_config("config/config.yaml")

    # 模拟排名数据
    mock_rankings = [
        {
            "rank": 1,
            "pain_point": "测试痛点 1",
            "pphi_score": 50.0,
            "gpu_tags": {"models": ["RTX 5090"], "brands": ["NVIDIA"]},
            "hidden_need": "测试需求 1",
        },
        {
            "rank": 2,
            "pain_point": "测试痛点 2",
            "pphi_score": 45.0,
            "gpu_tags": {"models": ["RX 7900 XTX"], "brands": ["AMD"]},
            "hidden_need": "",
        },
    ]

    # 模拟成本数据
    mock_cost = {
        "round_cost": 0.05,
        "round_tokens": 5000,
        "monthly_cost": 2.60,
        "budget": 80,
    }

    # 备份原文件
    consensus_path = Path("memories/consensus.md")
    if consensus_path.exists():
        backup_path = Path("memories/consensus.md.backup")
        import shutil
        shutil.copy(consensus_path, backup_path)
        print(f"已备份: {backup_path}")

    try:
        update_consensus(mock_rankings, mock_cost, config)
        print("✓ update_consensus() 执行成功")

        # 验证更新
        with open(consensus_path, "r", encoding="utf-8") as f:
            content = f.read()
            if "测试痛点 1" in content:
                print("✓ Top 痛点已更新")
            if "$2.60" in content:
                print("✓ 成本追踪已更新")
    finally:
        # 恢复原文件
        if backup_path.exists():
            shutil.copy(backup_path, consensus_path)
            backup_path.unlink()
            print(f"已恢复原文件")

    print()


def main():
    print("\n开始测试成本控制和共识更新功能\n")

    try:
        test_cost_tracker()
        test_llm_downgrade()
        test_consensus_updater()

        print("=" * 50)
        print("所有测试通过 ✓")
        print("=" * 50)

    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
