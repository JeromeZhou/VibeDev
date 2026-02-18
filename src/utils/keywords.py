"""GPU-Insight 关键词管理 — 统一加载 + 热词发现 + 衰减机制"""

import math
import re
import yaml
from datetime import datetime
from pathlib import Path
from collections import Counter

KEYWORDS_PATH = Path("config/keywords.yaml")

# 中英文停用词（过滤热词发现中的无意义词）
STOPWORDS_ZH = {
    "这个", "那个", "什么", "怎么", "如何", "为什么", "可以", "应该", "已经",
    "但是", "而且", "或者", "因为", "所以", "虽然", "不过", "然后", "就是",
    "大家", "感觉", "觉得", "知道", "看看", "一下", "一个", "没有", "不是",
    "真的", "其实", "现在", "今天", "昨天", "明天", "时候", "问题", "东西",
    "自己", "他们", "我们", "你们", "还是", "比较", "非常", "特别", "一直",
    "终于", "居然", "竟然", "到底", "是不是", "有没有", "能不能", "会不会",
    "视频", "评测", "开箱", "分享", "推荐", "教程", "合集", "盘点", "对比",
}
STOPWORDS_EN = {
    "this", "that", "what", "which", "where", "when", "with", "from", "have",
    "been", "will", "would", "could", "should", "about", "their", "there",
    "they", "them", "than", "then", "just", "also", "very", "much", "more",
    "some", "like", "into", "over", "after", "before", "between", "under",
    "here", "your", "does", "nvidia", "radeon", "geforce",  # 品牌词不算热词
}

# 热词容量上限
MAX_DISCOVERED_ZH = 12
MAX_DISCOVERED_EN = 8
# 衰减参数
DECAY_MAX_DAYS = 14  # 14天未出现归零
DECAY_MIN_MENTIONS = 3  # 低于3次且7天未出现则删除


def _load_keywords_config() -> dict:
    """加载 keywords.yaml"""
    if not KEYWORDS_PATH.exists():
        return {}
    with open(KEYWORDS_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_search_keywords(lang: str = "zh", category: str = "pain") -> list[str]:
    """获取搜索关键词"""
    config = _load_keywords_config()
    search = config.get("search", {}).get(lang, {})

    if category == "all":
        keywords = []
        for cat in ("pain", "models", "brands"):
            keywords.extend(search.get(cat, []))
        # 加上活跃热词
        for item in _get_active_discovered(config, lang):
            keywords.append(item["word"])
        return list(dict.fromkeys(keywords))

    return search.get(category, [])


def get_pain_signals() -> list[str]:
    """获取所有痛点信号词（中英文合并）"""
    config = _load_keywords_config()
    signals = config.get("signals", {})
    all_signals = signals.get("en", []) + signals.get("zh", [])
    return list(dict.fromkeys(all_signals))


def get_bilibili_keywords(max_count: int = 6) -> list[str]:
    """Bilibili: 只用 pain + models，不用热词（避免 412 限流）"""
    pain = get_search_keywords("zh", "pain")
    models = get_search_keywords("zh", "models")
    keywords = pain[:4] + models[:max_count - 4]
    return keywords[:max_count]


def get_reddit_queries() -> list[str]:
    """Reddit: 只用英文 pain 词"""
    return get_search_keywords("en", "pain")[:6]


def get_v2ex_keywords() -> list[str]:
    """V2EX: brands + 全部中文热词（零成本本地筛选）"""
    brands = get_search_keywords("zh", "brands")
    config = _load_keywords_config()
    hot_words = [item["word"] for item in _get_active_discovered(config, "zh")]
    return list(dict.fromkeys(brands + hot_words))


def get_discovered_stats() -> dict:
    """获取热词发现统计（供 admin 页面使用）"""
    config = _load_keywords_config()
    discovered = config.get("discovered", {})
    zh_items = discovered.get("zh", [])
    en_items = discovered.get("en", [])

    # 兼容旧格式（纯字符串列表）
    if zh_items and isinstance(zh_items[0], str):
        zh_items = []
    if en_items and isinstance(en_items[0], str):
        en_items = []

    return {
        "zh": zh_items,
        "en": en_items,
        "zh_count": len(zh_items),
        "en_count": len(en_items),
        "zh_capacity": MAX_DISCOVERED_ZH,
        "en_capacity": MAX_DISCOVERED_EN,
        "last_updated": discovered.get("last_updated"),
    }


def _get_active_discovered(config: dict, lang: str) -> list[dict]:
    """获取活跃的热词（decay_score > 0.3）"""
    discovered = config.get("discovered", {}).get(lang, [])
    if not discovered or not isinstance(discovered[0], dict):
        return []
    return [item for item in discovered if item.get("decay_score", 0) > 0.3]


def _calc_decay_score(item: dict) -> float:
    """计算热词衰减分数"""
    today = datetime.now()
    last_seen = item.get("last_seen", "")
    total_mentions = item.get("total_mentions", 1)

    if not last_seen:
        return 0.0

    try:
        last_dt = datetime.strptime(last_seen, "%Y-%m-%d")
        days_inactive = (today - last_dt).days
    except (ValueError, TypeError):
        days_inactive = DECAY_MAX_DAYS

    # freshness: 14天线性衰减到0
    freshness = max(0, 1 - days_inactive / DECAY_MAX_DAYS)

    # frequency: 出现越多越耐衰减
    frequency = min(1.0, math.log2(total_mentions + 1) / 5)

    return round(freshness * (0.5 + 0.5 * frequency), 3)


def discover_hot_words(posts: list[dict], min_freq: int = 2) -> dict:
    """从帖子标题中发现高频新词（带停用词过滤）"""
    existing = set()
    config = _load_keywords_config()
    for lang in ("zh", "en"):
        for cat in ("pain", "models", "brands"):
            existing.update(w.lower() for w in config.get("search", {}).get(lang, {}).get(cat, []))
        existing.update(w.lower() for w in config.get("signals", {}).get(lang, []))

    zh_counter = Counter()
    en_counter = Counter()

    for post in posts:
        title = post.get("title", "")
        comments = post.get("comments", "")
        text = f"{title} {comments}"

        # 中文：2-4 字连续中文，过滤停用词
        zh_words = re.findall(r'[\u4e00-\u9fff]{2,4}', text)
        for w in zh_words:
            if w not in STOPWORDS_ZH and w.lower() not in existing:
                zh_counter[w] += 1

        # 英文：有意义的词组，过滤停用词
        en_words = re.findall(r'[a-zA-Z][a-zA-Z\s]{3,20}', text)
        for w in en_words:
            w = w.strip().lower()
            if w not in STOPWORDS_EN and w not in existing and len(w) > 3:
                en_counter[w] += 1

    new_zh = [w for w, c in zh_counter.most_common(MAX_DISCOVERED_ZH) if c >= min_freq]
    new_en = [w for w, c in en_counter.most_common(MAX_DISCOVERED_EN) if c >= min_freq]

    return {"zh": new_zh, "en": new_en}


def update_discovered_keywords(new_words: dict):
    """更新热词 + 衰减计算 + 容量控制"""
    today_str = datetime.now().strftime("%Y-%m-%d")
    config = _load_keywords_config()
    discovered = config.get("discovered", {"zh": [], "en": [], "last_updated": None})

    # 每天只更新一次
    last_updated = discovered.get("last_updated", "")
    if last_updated and last_updated.startswith(today_str):
        return

    for lang, max_cap in [("zh", MAX_DISCOVERED_ZH), ("en", MAX_DISCOVERED_EN)]:
        items = discovered.get(lang, [])

        # 兼容旧格式（纯字符串列表 → 转为 dict）
        if items and isinstance(items[0], str):
            items = [{"word": w, "first_seen": today_str, "last_seen": today_str,
                       "total_mentions": 1, "decay_score": 1.0} for w in items]

        # 建立 word → item 映射
        word_map = {item["word"]: item for item in items if isinstance(item, dict)}

        # 更新已有词的 last_seen + total_mentions
        for new_word in new_words.get(lang, []):
            if new_word in word_map:
                word_map[new_word]["last_seen"] = today_str
                word_map[new_word]["total_mentions"] = word_map[new_word].get("total_mentions", 0) + 1
            else:
                word_map[new_word] = {
                    "word": new_word,
                    "first_seen": today_str,
                    "last_seen": today_str,
                    "total_mentions": 1,
                    "decay_score": 1.0,
                }

        # 计算衰减分数
        for item in word_map.values():
            item["decay_score"] = _calc_decay_score(item)

        # 移除：decay_score <= 0 或 (mentions < 3 且 7天未出现)
        active = []
        for item in word_map.values():
            if item["decay_score"] <= 0:
                continue
            mentions = item.get("total_mentions", 0)
            try:
                last_dt = datetime.strptime(item.get("last_seen", ""), "%Y-%m-%d")
                days = (datetime.now() - last_dt).days
            except (ValueError, TypeError):
                days = DECAY_MAX_DAYS
            if mentions < DECAY_MIN_MENTIONS and days > 7:
                continue
            active.append(item)

        # 按 decay_score 降序，容量控制
        active.sort(key=lambda x: x.get("decay_score", 0), reverse=True)
        discovered[lang] = active[:max_cap]

    discovered["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    config["discovered"] = discovered

    with open(KEYWORDS_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    zh_count = len(discovered.get("zh", []))
    en_count = len(discovered.get("en", []))
    print(f"  热词库: {zh_count}/{MAX_DISCOVERED_ZH} 中文, {en_count}/{MAX_DISCOVERED_EN} 英文")
