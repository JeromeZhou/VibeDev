"""GPU-Insight 离线 Pipeline 测试 — 不依赖 LLM API，用规则模拟分析"""

import sys
import json
import re
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.mock_data import generate_mock_data
from src.utils.config import load_config
from src.cleaners import clean_data
from src.rankers import calculate_pphi
from src.reporters import generate_report


# ============================================================
# 规则引擎：不调用 LLM，用关键词匹配模拟痛点提取和需求推导
# ============================================================

PAIN_RULES = [
    {"keywords": ["显存", "VRAM", "爆显存", "显存不够"], "pain": "显存容量不足", "category": "显存", "intensity": 0.85},
    {"keywords": ["功耗", "功耗墙", "power", "散热压不住"], "pain": "功耗与散热失控", "category": "功耗", "intensity": 0.75},
    {"keywords": ["driver", "驱动", "crash", "TDR", "黑屏"], "pain": "驱动稳定性差", "category": "驱动", "intensity": 0.80},
    {"keywords": ["价格", "加价", "买不到", "玩不起"], "pain": "显卡价格过高", "category": "价格", "intensity": 0.90},
    {"keywords": ["FSR", "DLSS", "画质", "模糊", "鬼影"], "pain": "AI 超分画质不佳", "category": "生态", "intensity": 0.65},
    {"keywords": ["矿卡", "翻新", "二手"], "pain": "二手市场信任危机", "category": "其他", "intensity": 0.60},
    {"keywords": ["4K", "120Hz", "144Hz", "高刷"], "pain": "中端卡无法满足 4K 高刷", "category": "性能", "intensity": 0.70},
    {"keywords": ["Linux", "Wayland", "开源驱动"], "pain": "Linux 驱动体验差", "category": "驱动", "intensity": 0.70},
    {"keywords": ["噪音", "风扇", "分贝", "rpm"], "pain": "散热噪音过大", "category": "散热", "intensity": 0.65},
    {"keywords": ["LLM", "大模型", "本地跑", "48G", "AI"], "pain": "消费级显卡无法运行本地大模型", "category": "显存", "intensity": 0.88},
    {"keywords": ["HDMI", "DP", "接口", "带宽"], "pain": "显示接口标准混乱", "category": "生态", "intensity": 0.55},
    {"keywords": ["机箱", "放不下", "太大", "长度"], "pain": "显卡体积过大", "category": "散热", "intensity": 0.60},
]

NEED_MAP = {
    "显存容量不足": {
        "need": "平价显卡的本地 AI 算力平权",
        "chain": ["用户需要在本地运行 AI 应用", "当前中端卡显存不足", "用户无法承担高端卡价格", "隐藏需求：平价 AI 算力平权"],
        "confidence": 0.82,
    },
    "功耗与散热失控": {
        "need": "高性能低功耗的芯片架构",
        "chain": ["功耗墙限制了性能释放", "散热方案跟不上功耗增长", "用户希望安静高效的使用体验", "隐藏需求：能效比革命"],
        "confidence": 0.75,
    },
    "驱动稳定性差": {
        "need": "开箱即用的稳定驱动体验",
        "chain": ["驱动更新频繁引入 bug", "用户被迫回滚驱动", "影响工作和游戏体验", "隐藏需求：驱动质量 > 功能堆叠"],
        "confidence": 0.78,
    },
    "显卡价格过高": {
        "need": "合理的性价比定价策略",
        "chain": ["显卡价格逐代上涨", "中端卡价格接近上代高端", "普通玩家被挤出市场", "隐藏需求：重建中端市场性价比"],
        "confidence": 0.90,
    },
    "消费级显卡无法运行本地大模型": {
        "need": "消费级 AI 推理专用显卡",
        "chain": ["AI 应用爆发式增长", "本地推理需要大显存", "消费级最大 24G 远不够", "隐藏需求：面向 AI 的消费级产品线"],
        "confidence": 0.85,
    },
}


def rule_based_extract(posts: list[dict]) -> list[dict]:
    """基于规则的痛点提取"""
    results = []
    for post in posts:
        text = (post.get("title", "") + " " + post.get("content", "")).lower()
        for rule in PAIN_RULES:
            if any(kw.lower() in text for kw in rule["keywords"]):
                results.append({
                    "pain_point": rule["pain"],
                    "category": rule["category"],
                    "emotion_intensity": rule["intensity"],
                    "summary": post.get("title", ""),
                    "_source": post.get("_source", post.get("source", "unknown")),
                    "_post_id": post.get("id", ""),
                })
                break  # 每条讨论只匹配第一个规则
    return results


def rule_based_infer(pain_points: list[dict]) -> list[dict]:
    """基于规则的隐藏需求推导"""
    results = []
    seen = set()
    for pp in pain_points:
        pain = pp["pain_point"]
        if pain in seen:
            continue
        seen.add(pain)
        mapping = NEED_MAP.get(pain)
        if mapping:
            results.append({
                "pain_point": pain,
                "hidden_need": mapping["need"],
                "reasoning_chain": mapping["chain"],
                "confidence": mapping["confidence"],
                "approved": True,
                "adjusted_confidence": mapping["confidence"] * 0.9,
                "_source": pp.get("_source", "unknown"),
            })
        else:
            results.append({
                "pain_point": pain,
                "hidden_need": f"需要进一步分析: {pain}",
                "reasoning_chain": ["规则库未覆盖", "需要 LLM 深度分析"],
                "confidence": 0.4,
                "approved": False,
                "adjusted_confidence": 0.3,
                "_source": pp.get("_source", "unknown"),
            })
    return results


def main():
    print("=" * 55)
    print("  GPU-Insight Pipeline 测试（离线模式 / 规则引擎）")
    print("=" * 55)
    print()

    # 加载配置
    config = load_config("config/config.yaml")

    # 1. 生成模拟数据
    print("📥 [阶段1] 生成模拟数据...")
    raw_posts = generate_mock_data()
    print(f"   生成 {len(raw_posts)} 条讨论")
    print()

    # 2. 清洗
    print("🧹 [阶段2] 数据清洗...")
    cleaned = clean_data(raw_posts, config)
    print(f"   去重后剩余 {len(cleaned)} 条")
    print()

    # 3. 痛点提取（规则引擎）
    print("🔍 [阶段3] 痛点提取（规则引擎）...")
    pain_points = rule_based_extract(cleaned)
    print(f"   提取 {len(pain_points)} 个痛点")
    for pp in pain_points:
        print(f"     [{pp['category']}] {pp['pain_point']} (强度: {pp['emotion_intensity']})")
    print()

    # 4. 隐藏需求推导（规则引擎）
    print("💡 [阶段4] 隐藏需求推导（规则引擎）...")
    insights = rule_based_infer(pain_points)
    approved = [i for i in insights if i.get("approved")]
    print(f"   推导 {len(insights)} 个需求，通过 {len(approved)} 个")
    for ins in insights:
        status = "✅" if ins["approved"] else "❌"
        print(f"     {status} {ins['pain_point']} → {ins['hidden_need']} ({ins['confidence']:.0%})")
    print()

    # 5. PPHI 排名
    print("📊 [阶段5] PPHI 排名计算...")
    rankings = calculate_pphi(approved, config)
    print(f"   生成 {len(rankings)} 个排名")
    for r in rankings[:10]:
        print(f"     #{r['rank']} {r['pain_point']} — PPHI: {r['pphi_score']}")
    print()

    # 6. 生成报告
    print("📝 [阶段6] 生成报告...")
    report_path = generate_report(rankings, config)
    print(f"   报告：{report_path}")
    print()

    print("✅ Pipeline 测试完成！")
    print()

    # 输出统计
    print("📊 统计摘要：")
    print(f"   原始数据：{len(raw_posts)} 条")
    print(f"   清洗后：{len(cleaned)} 条")
    print(f"   痛点：{len(pain_points)} 个")
    print(f"   隐藏需求（通过）：{len(approved)} 个")
    print(f"   PPHI 排名：{len(rankings)} 个")


if __name__ == "__main__":
    main()
