"""GPU-Insight 关键词管理 — 统一加载 + 热词发现"""

import yaml
from pathlib import Path
from collections import Counter

KEYWORDS_PATH = Path("config/keywords.yaml")


def _load_keywords_config() -> dict:
    """加载 keywords.yaml"""
    if not KEYWORDS_PATH.exists():
        return {}
    with open(KEYWORDS_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_search_keywords(lang: str = "zh", category: str = "pain") -> list[str]:
    """获取搜索关键词

    Args:
        lang: "zh" 或 "en"
        category: "pain" | "models" | "brands" | "all"
    Returns:
        关键词列表
    """
    config = _load_keywords_config()
    search = config.get("search", {}).get(lang, {})

    if category == "all":
        keywords = []
        for cat in ("pain", "models", "brands"):
            keywords.extend(search.get(cat, []))
        # 加上自动发现的热词
        discovered = config.get("discovered", {}).get(lang, [])
        if isinstance(discovered, list):
            keywords.extend(discovered)
        return list(dict.fromkeys(keywords))  # 去重保序

    return search.get(category, [])


def get_pain_signals() -> list[str]:
    """获取所有痛点信号词（中英文合并）"""
    config = _load_keywords_config()
    signals = config.get("signals", {})
    all_signals = signals.get("en", []) + signals.get("zh", [])
    return list(dict.fromkeys(all_signals))


def get_bilibili_keywords(max_count: int = 8) -> list[str]:
    """获取 Bilibili 搜索关键词（痛点词 + 热门型号，控制数量避免 412）"""
    pain = get_search_keywords("zh", "pain")
    models = get_search_keywords("zh", "models")
    # 痛点词优先，型号词补充
    keywords = pain[:5] + models[:max_count - 5]
    return keywords[:max_count]


def get_reddit_queries() -> list[str]:
    """获取 Reddit 搜索关键词"""
    return get_search_keywords("en", "pain")[:6]


def get_v2ex_keywords() -> list[str]:
    """获取 V2EX 热帖筛选关键词"""
    return get_search_keywords("zh", "brands")


def discover_hot_words(posts: list[dict], min_freq: int = 3) -> dict:
    """从帖子标题中发现高频新词

    在 pipeline 结束后调用，自动发现新的热词。
    只提取不在现有关键词/信号词中的新词。

    Returns:
        {"zh": [...], "en": [...]} 新发现的热词
    """
    import re

    existing = set()
    config = _load_keywords_config()
    for lang in ("zh", "en"):
        for cat in ("pain", "models", "brands"):
            existing.update(w.lower() for w in config.get("search", {}).get(lang, {}).get(cat, []))
        existing.update(w.lower() for w in config.get("signals", {}).get(lang, []))

    # 提取中文 2-4 字词组 + 英文单词
    zh_counter = Counter()
    en_counter = Counter()

    for post in posts:
        title = post.get("title", "")
        # 中文：提取 2-4 字连续中文
        zh_words = re.findall(r'[\u4e00-\u9fff]{2,4}', title)
        for w in zh_words:
            if w.lower() not in existing:
                zh_counter[w] += 1

        # 英文：提取有意义的词组
        en_words = re.findall(r'[a-zA-Z][a-zA-Z\s]{3,20}', title)
        for w in en_words:
            w = w.strip().lower()
            if w not in existing and len(w) > 3:
                en_counter[w] += 1

    # 只保留出现 >= min_freq 次的新词
    new_zh = [w for w, c in zh_counter.most_common(20) if c >= min_freq]
    new_en = [w for w, c in en_counter.most_common(20) if c >= min_freq]

    return {"zh": new_zh, "en": new_en}


def update_discovered_keywords(new_words: dict):
    """将发现的热词写入 keywords.yaml 的 discovered 区域"""
    from datetime import datetime

    config = _load_keywords_config()
    discovered = config.get("discovered", {"zh": [], "en": [], "last_updated": None})

    # 合并新词（去重）
    existing_zh = set(discovered.get("zh", []) if isinstance(discovered.get("zh"), list) else [])
    existing_en = set(discovered.get("en", []) if isinstance(discovered.get("en"), list) else [])

    existing_zh.update(new_words.get("zh", []))
    existing_en.update(new_words.get("en", []))

    # 最多保留 50 个热词（防止无限增长）
    discovered["zh"] = sorted(existing_zh)[:50]
    discovered["en"] = sorted(existing_en)[:50]
    discovered["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    config["discovered"] = discovered

    with open(KEYWORDS_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
