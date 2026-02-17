#!/usr/bin/env python3
"""召回率测试脚本 - 分析漏斗过滤效果"""

import json
import sys
from pathlib import Path
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

def analyze_recall():
    """分析漏斗召回率"""

    # 1. 读取清洗后数据
    cleaned_file = Path("data/processed/cleaned_2026-02-17.jsonl")
    posts = []
    with open(cleaned_file, 'r', encoding='utf-8') as f:
        for line in f:
            posts.append(json.loads(line))

    print(f"=== 输入数据 ===")
    print(f"总帖子数: {len(posts)}")

    # 2. 模拟 L1 本地过滤
    from src.analyzers.funnel import l1_local_filter, PAIN_SIGNALS, EXCLUDE_PATTERNS

    posts_l1 = l1_local_filter(posts)

    pain_posts = [p for p in posts_l1 if p.get("_pain_signals", 0) > 0]
    excluded_posts = [p for p in posts_l1 if p.get("_excluded", False)]

    print(f"\n=== L1 本地信号过滤 ===")
    print(f"有痛点信号: {len(pain_posts)} ({len(pain_posts)/len(posts)*100:.1f}%)")
    print(f"被排除模式匹配: {len(excluded_posts)} ({len(excluded_posts)/len(posts)*100:.1f}%)")

    # 信号词分布
    signal_counts = Counter()
    for p in posts_l1:
        text = (p.get("title", "") + " " + (p.get("content", "") or "")).lower()
        for signal in PAIN_SIGNALS:
            if signal in text:
                signal_counts[signal] += 1

    print(f"\n=== L1 信号词命中 Top 20 ===")
    for word, count in signal_counts.most_common(20):
        print(f"  {word}: {count}")

    # 3. 抽样检查被排除的帖子
    print(f"\n=== 被排除帖子样本 (前15条) ===")
    for i, p in enumerate(excluded_posts[:15], 1):
        title = p.get("title", "")[:80]
        source = p.get("_source", "")
        pain_score = p.get("_pain_signal_score", 0)
        print(f"{i}. [{source}] {title}")
        print(f"   分数: {pain_score:.1f}")

    # 4. 抽样检查无信号但可能有价值的帖子
    no_signal_posts = [p for p in posts_l1 if p.get("_pain_signals", 0) == 0 and not p.get("_excluded", False)]
    print(f"\n=== 无信号帖子样本 (前20条) - 可能遗漏 ===")
    for i, p in enumerate(no_signal_posts[:20], 1):
        title = p.get("title", "")[:80]
        source = p.get("_source", "")
        print(f"{i}. [{source}] {title}")

    # 5. 读取最终输出
    with open("outputs/pphi_rankings/latest.json", 'r', encoding='utf-8') as f:
        rankings = json.load(f)

    print(f"\n=== 最终输出 ===")
    print(f"痛点数量: {rankings['total_pain_points']}")
    print(f"转化率: {rankings['total_pain_points']}/{len(posts)} = {rankings['total_pain_points']/len(posts)*100:.2f}%")

    # 6. L1 信号词覆盖度评估
    print(f"\n=== L1 信号词覆盖度评估 ===")
    print(f"当前信号词数量: {len(PAIN_SIGNALS)}")
    print(f"  中文: {sum(1 for w in PAIN_SIGNALS if any('\\u4e00' <= c <= '\\u9fff' for c in w))}")
    print(f"  英文: {sum(1 for w in PAIN_SIGNALS if all(ord(c) < 128 for c in w))}")

    # 检查可能遗漏的关键词
    potential_missing = [
        # 英文
        "throttle", "downclock", "unstable", "driver issue", "compatibility",
        "screen tearing", "microstutter", "fps drop", "memory leak",
        "power limit", "thermal throttle", "fan curve", "vrm", "pcie",
        # 中文
        "降频", "不稳定", "兼容性", "画面卡顿", "掉驱动", "温度墙",
        "功耗墙", "供电", "PCIe", "显存颗粒", "体质", "翻车率"
    ]

    print(f"\n=== 潜在遗漏信号词 ===")
    for word in potential_missing:
        if word.lower() not in [s.lower() for s in PAIN_SIGNALS]:
            # 检查是否在数据中出现
            count = sum(1 for p in posts if word.lower() in (p.get("title", "") + " " + (p.get("content", "") or "")).lower())
            if count > 0:
                print(f"  {word}: 出现 {count} 次 (未在信号词列表)")

if __name__ == "__main__":
    analyze_recall()
