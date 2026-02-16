"""GPU-Insight 三层漏斗筛选器 — 团队共识方案"""

import re
import json
from src.utils.llm_client import LLMClient


# L1 排除模式（本地规则，0 token）
EXCLUDE_PATTERNS = [
    r"(?i)^(just (got|bought|ordered|upgraded)|my new|unboxing|look what)",  # 晒单
    r"(?i)^(which|what|should i|help me choose|recommend)",  # 购买建议
    r"(?i)^(nvidia announces|amd reveals|official|press release)",  # 新闻
    r"(?i)^(giveaway|sale|deal|discount|coupon)",  # 促销
    r"(?i)^(meme|funny|lol|haha)",  # 娱乐
]

# L1 负面/痛点情绪词（加分）
PAIN_SIGNALS = [
    "problem", "issue", "crash", "bug", "broken", "bad", "worst", "hate",
    "disappointed", "regret", "overheat", "loud", "noise", "expensive",
    "rip", "dead", "fail", "error", "freeze", "stutter", "lag", "artifact",
    "coil whine", "black screen", "blue screen", "bsod", "rma", "refund",
    "waste", "scam", "overpriced", "underpowered", "bottleneck",
    # 中文
    "爆显存", "崩溃", "黑屏", "花屏", "噪音", "发热", "功耗", "太贵",
    "后悔", "翻车", "缩水", "虚标", "矿卡", "售后", "卡顿", "掉帧",
]


def l1_local_filter(posts: list[dict]) -> list[dict]:
    """L1: 本地信号分数排序（不丢弃任何帖子，只排序）

    返回所有帖子，按 pain_signal_score 降序排列。
    score > 0 的优先处理，score = 0 的降优先级。
    """
    for post in posts:
        title = post.get("title", "").lower()
        content = (post.get("content", "") or "").lower()
        text = title + " " + content

        # 排除模式匹配 → 降低分数但不丢弃
        excluded = any(re.search(pat, title) for pat in EXCLUDE_PATTERNS)

        # 痛点信号词计数
        pain_count = sum(1 for w in PAIN_SIGNALS if w in text)

        # 信号分数
        base_score = post.get("_signal_score", 0)
        pain_bonus = pain_count * 3.0
        exclude_penalty = -20.0 if excluded else 0.0

        post["_pain_signal_score"] = round(base_score + pain_bonus + exclude_penalty, 2)
        post["_pain_signals"] = pain_count
        post["_excluded"] = excluded

    posts.sort(key=lambda x: x["_pain_signal_score"], reverse=True)
    return posts


def l2_batch_classify(posts: list[dict], llm: LLMClient, batch_size: int = 30) -> list[dict]:
    """L2: LLM 批量标题分类（极低 token 消耗）

    对每条帖子标记 0/1/2:
      0 = 明确无关
      1 = 可能相关
      2 = 明确是痛点
    """
    import time

    system = """你是显卡用户痛点分类器。对每条帖子标题判断是否包含显卡用户痛点。
输出格式：每行一个数字，对应每条标题。
0 = 明确无关（晒单、新闻、购买建议、无关话题）
1 = 可能相关（提问、讨论、不确定）
2 = 明确是痛点（抱怨、吐槽、报错、质量问题）
只输出数字，每行一个，不要其他内容。"""

    total_batches = (len(posts) + batch_size - 1) // batch_size
    for i in range(0, len(posts), batch_size):
        batch = posts[i:i + batch_size]
        batch_num = i // batch_size + 1
        titles = "\n".join(f"{j+1}. {p.get('title', '')[:80]}" for j, p in enumerate(batch))

        success = False
        for attempt in range(2):  # 最多重试 1 次
            try:
                print(f"  L2 批次 {batch_num}/{total_batches}（{len(batch)} 条）...", end=" ")
                response = llm.call_simple(f"请分类以下 {len(batch)} 条标题:\n{titles}", system)
                numbers = re.findall(r'[012]', response)
                for j, post in enumerate(batch):
                    if j < len(numbers):
                        post["_l2_class"] = int(numbers[j])
                    else:
                        post["_l2_class"] = 1
                c2 = sum(1 for p in batch if p.get("_l2_class") == 2)
                c1 = sum(1 for p in batch if p.get("_l2_class") == 1)
                c0 = sum(1 for p in batch if p.get("_l2_class") == 0)
                print(f"完成 (2:{c2} 1:{c1} 0:{c0})")
                success = True
                break
            except Exception as e:
                print(f"失败: {e}")
                if attempt == 0:
                    print(f"  重试中...")
                    time.sleep(3)

        if not success:
            print(f"  L2 批次 {batch_num} 跳过，默认标记为 1")
            for post in batch:
                post["_l2_class"] = 1

    return posts


def l3_select(posts: list[dict], max_deep: int = 30, max_light: int = 20) -> tuple[list[dict], list[dict]]:
    """L3: 选择深度分析和轻度分析的帖子

    返回 (deep_list, light_list):
      deep_list: _l2_class == 2 的帖子，最多 max_deep 条
      light_list: _l2_class == 1 的帖子，最多 max_light 条
    """
    deep = [p for p in posts if p.get("_l2_class") == 2][:max_deep]
    light = [p for p in posts if p.get("_l2_class") == 1][:max_light]
    excluded = [p for p in posts if p.get("_l2_class") == 0]

    print(f"  L3 分流: 深度分析 {len(deep)} 条 | 轻度分析 {len(light)} 条 | 排除 {len(excluded)} 条")
    return deep, light


def run_funnel(posts: list[dict], llm: LLMClient) -> tuple[list[dict], list[dict]]:
    """执行完整三层漏斗，返回 (deep_list, light_list)"""
    print(f"  漏斗输入: {len(posts)} 条")

    # L1
    posts = l1_local_filter(posts)
    pain_posts = [p for p in posts if p.get("_pain_signals", 0) > 0]
    print(f"  L1 信号排序: {len(pain_posts)} 条有痛点信号, {len(posts) - len(pain_posts)} 条无信号")

    # L2
    posts = l2_batch_classify(posts, llm)

    # L3
    deep, light = l3_select(posts)

    return deep, light
