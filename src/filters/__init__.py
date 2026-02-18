"""GPU-Insight AI 相关性过滤器 — 在 GPU Tagger 之后、漏斗之前执行

分两层判断帖子是否与 PC 显卡/GPU 相关：
  Layer 1: 标题批量分类（30条/批，~1,300 token）
  Layer 2: 内容+评论深度判断（仅对"不确定"的帖子，10条/批）

快速通道（跳过 LLM）：
  - 专业显卡媒体（videocardz, techpowerup, guru3d, chiphell）
  - GPU tagger 已识别到型号/品牌/系列的帖子

Shadow Mode: 初期只标记不删除，验证准确率后再启用硬过滤
"""

import re
from src.utils.llm_client import LLMClient

# 专业显卡源，直接保留
AUTO_KEEP_SOURCES = {"videocardz", "techpowerup", "guru3d", "chiphell"}


def filter_gpu_relevant(posts: list[dict], llm: LLMClient, shadow: bool = True) -> list[dict]:
    """AI 相关性过滤主入口

    Args:
        posts: GPU tagger 处理后的帖子列表（已有 _gpu_tags）
        llm: 共享的 LLMClient 实例
        shadow: True=只标记不删除（shadow mode），False=硬过滤

    Returns:
        过滤/标记后的帖子列表
    """
    if not posts:
        return []

    # 快速通道分流
    auto_keep = []
    need_check = []

    for p in posts:
        source = p.get("_source", p.get("source", ""))
        gpu_tags = p.get("_gpu_tags", {})
        has_tags = bool(gpu_tags.get("models") or gpu_tags.get("brands") or gpu_tags.get("series"))

        if source in AUTO_KEEP_SOURCES or has_tags:
            p["_relevance_class"] = 2  # 自动保留
            p["_relevance_reason"] = "fast_pass"
            auto_keep.append(p)
        else:
            need_check.append(p)

    if not need_check:
        print(f"  AI 过滤: {len(auto_keep)} 条全部快速通道（专业源/已打标）")
        return auto_keep

    # Layer 1: 标题批量分类
    certain_keep, uncertain, certain_drop = _layer1_title_classify(need_check, llm)

    # Layer 2: 对不确定的帖子做内容深度判断
    l2_keep, l2_drop = _layer2_content_classify(uncertain, llm)

    # 合并结果
    kept = auto_keep + certain_keep + l2_keep
    dropped = certain_drop + l2_drop

    # 统计
    print(f"  AI 过滤: {len(posts)} 条 → 快速通道 {len(auto_keep)} | "
          f"L1保留 {len(certain_keep)} | L2保留 {len(l2_keep)} | "
          f"排除 {len(dropped)} 条非显卡内容")

    if shadow:
        # Shadow mode: 标记但不删除，全部返回
        for p in dropped:
            p["_relevance_shadow_drop"] = True
        return kept + dropped
    else:
        return kept


def _layer1_title_classify(posts: list[dict], llm: LLMClient,
                           batch_size: int = 30) -> tuple[list, list, list]:
    """Layer 1: 标题批量分类

    输出三类：
      2 = 明确与 PC 显卡/GPU 相关 → certain_keep
      1 = 不确定 → uncertain（送 Layer 2）
      0 = 明确不相关 → certain_drop

    Returns: (certain_keep, uncertain, certain_drop)
    """
    system = """你是一个内容分类器。判断每条帖子标题是否与"PC 显卡/GPU"相关。

相关(2)：显卡驱动、RTX/RX/Arc 型号、游戏帧数、GPU温度、显存、4K游戏、光追、DLSS、FSR、装机配显卡、矿卡、显卡价格、GPU渲染
不确定(1)：可能相关但标题不够明确，如"电脑卡顿"、"游戏优化"、"装机推荐"
不相关(0)：手机、iPhone、iPad、路由器、耳机、骁龙、天玑、平板、智能手表、手机游戏、充电器、手机壳

对每条标题输出一个数字(0/1/2)，每行一个，不要其他内容。"""

    certain_keep, uncertain, certain_drop = [], [], []

    for i in range(0, len(posts), batch_size):
        batch = posts[i:i + batch_size]
        titles = "\n".join(
            f"{j+1}. [{p.get('source','')}] {p.get('title','')[:80]}"
            for j, p in enumerate(batch)
        )

        try:
            response = llm.call_simple(
                f"请分类以下 {len(batch)} 条帖子标题:\n{titles}",
                system
            )
            numbers = re.findall(r'[012]', response)

            for j, post in enumerate(batch):
                cls = int(numbers[j]) if j < len(numbers) else 1
                post["_relevance_class"] = cls

                if cls == 2:
                    post["_relevance_reason"] = "L1_relevant"
                    certain_keep.append(post)
                elif cls == 0:
                    post["_relevance_reason"] = "L1_irrelevant"
                    certain_drop.append(post)
                else:
                    post["_relevance_reason"] = "L1_uncertain"
                    uncertain.append(post)

        except Exception as e:
            print(f"  [!] L1 标题分类失败({e})，默认保留")
            for post in batch:
                post["_relevance_class"] = 1
                post["_relevance_reason"] = "L1_error"
                uncertain.append(post)

    return certain_keep, uncertain, certain_drop


def _layer2_content_classify(posts: list[dict], llm: LLMClient,
                             batch_size: int = 10) -> tuple[list, list]:
    """Layer 2: 内容+评论深度判断（仅对 L1 不确定的帖子）

    送标题+内容+评论给 LLM，判断是否与 PC 显卡相关。
    同时输出简要理由，方便调试。

    Returns: (kept, dropped)
    """
    if not posts:
        return [], []

    system = """你是 PC 显卡/GPU 内容分类专家。根据帖子的标题、正文和评论，判断是否与 PC 显卡/GPU 相关。

判断标准：
- 相关(1)：讨论 PC 独立显卡、集成显卡、GPU驱动、游戏画面设置、显卡温度/功耗、显存、光追、DLSS/FSR、挖矿显卡、显卡价格走势、装机配显卡
- 不相关(0)：手机GPU(骁龙/天玑/苹果芯片)、手机游戏、平板、路由器、耳机、与PC显卡完全无关的话题

对每条帖子输出格式：
数字|理由
例如：1|讨论RTX 4090温度问题
或：0|手机骁龙处理器评测

每行一条，不要其他内容。"""

    kept, dropped = [], []

    for i in range(0, len(posts), batch_size):
        batch = posts[i:i + batch_size]
        entries = []
        for j, p in enumerate(batch):
            title = p.get("title", "")[:80]
            content = (p.get("content", "") or "")[:200]
            comments = (p.get("comments", "") or "")[:200]
            entry = f"{j+1}. 标题: {title}"
            if content and content != title:
                entry += f"\n   正文: {content}"
            if comments:
                entry += f"\n   评论: {comments}"
            entries.append(entry)

        prompt_text = "\n\n".join(entries)

        try:
            response = llm.call_simple(
                f"请判断以下 {len(batch)} 条帖子是否与 PC 显卡/GPU 相关:\n\n{prompt_text}",
                system
            )

            lines = [l.strip() for l in response.strip().split("\n") if l.strip()]

            for j, post in enumerate(batch):
                if j < len(lines):
                    parts = lines[j].split("|", 1)
                    nums = re.findall(r'[01]', parts[0])
                    cls = int(nums[0]) if nums else 1
                    reason = parts[1].strip() if len(parts) > 1 else ""
                else:
                    cls = 1  # 解析不到默认保留
                    reason = "parse_miss"

                if cls == 1:
                    post["_relevance_class"] = 2  # L2 确认相关 → 提升到 class 2
                    post["_relevance_reason"] = f"L2_relevant: {reason}"
                    kept.append(post)
                else:
                    post["_relevance_class"] = 0
                    post["_relevance_reason"] = f"L2_irrelevant: {reason}"
                    dropped.append(post)

        except Exception as e:
            print(f"  [!] L2 内容分类失败({e})，默认保留")
            for post in batch:
                post["_relevance_class"] = 1
                post["_relevance_reason"] = "L2_error"
                kept.append(post)

    return kept, dropped
