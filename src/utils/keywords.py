"""GPU-Insight 关键词管理 — 统一加载 + 热词发现 + 衰减机制 + 型号自动同步"""

import math
import os
import re
import sys
import yaml
from datetime import datetime
from pathlib import Path
from collections import Counter
from contextlib import contextmanager

KEYWORDS_PATH = Path("config/keywords.yaml")
GPU_PRODUCTS_PATH = Path("config/gpu_products.yaml")


# ── 跨平台文件锁 ──────────────────────────────────────────
@contextmanager
def _file_lock(path: Path):
    """跨平台文件锁（写 keywords.yaml 时防并发损坏）"""
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_fd = open(lock_path, "w")
    try:
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    except (OSError, IOError):
        # 锁获取失败，跳过本次写入（下轮再写）
        print("  [!] keywords.yaml 写锁获取失败，跳过本次更新")
        yield
    finally:
        try:
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
        except Exception:
            pass
        lock_fd.close()
        try:
            lock_path.unlink(missing_ok=True)
        except Exception:
            pass

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
    # 论坛模板词
    "reply", "post", "topic", "comment", "thread", "edit", "deleted",
    "removed", "submitted", "score", "points", "permalink", "save",
    "report", "hide", "load", "more", "comments", "share", "best",
    "controversial", "gilded", "wiki", "flair", "self", "link",
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


def _load_gpu_products() -> dict:
    """加载 gpu_products.yaml"""
    if not GPU_PRODUCTS_PATH.exists():
        return {}
    with open(GPU_PRODUCTS_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _get_hot_models_from_products(top_n: int = 7) -> list[str]:
    """从 gpu_products.yaml 提取最新热门型号（最新系列优先）

    策略：每个品牌取最新系列的前几个型号，总计 top_n 个。
    NVIDIA 最新系列权重最高（市场关注度），AMD 次之，Intel 补充。
    """
    products = _load_gpu_products()
    brands = products.get("brands", {})
    models = []

    # 分配名额：NVIDIA 4, AMD 2, Intel 1
    allocation = {"nvidia": 4, "amd": 2, "intel": 1}

    for brand_key, count in allocation.items():
        brand = brands.get(brand_key, {})
        series_list = brand.get("series", [])
        if not series_list:
            continue
        # 取第一个系列（yaml 中最新系列排最前）
        latest = series_list[0].get("models", [])
        models.extend(latest[:count])

    return models[:top_n]


def get_search_keywords(lang: str = "zh", category: str = "pain") -> list[str]:
    """获取搜索关键词（models 类别自动合并 gpu_products.yaml 最新型号）"""
    config = _load_keywords_config()
    search = config.get("search", {}).get(lang, {})

    if category == "all":
        keywords = []
        for cat in ("pain", "models", "brands"):
            if cat == "models":
                # 合并 yaml 手动配置 + gpu_products 自动提取
                manual = search.get("models", [])
                auto = _get_hot_models_from_products()
                keywords.extend(list(dict.fromkeys(manual + auto)))
            else:
                keywords.extend(search.get(cat, []))
        # 加上活跃热词
        for item in _get_active_discovered(config, lang):
            keywords.append(item["word"])
        return list(dict.fromkeys(keywords))

    if category == "models":
        manual = search.get("models", [])
        auto = _get_hot_models_from_products()
        return list(dict.fromkeys(manual + auto))

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


def get_signals_count() -> int:
    """获取信号词总数（供 admin 页面使用）"""
    config = _load_keywords_config()
    signals = config.get("signals", {})
    return len(signals.get("en", [])) + len(signals.get("zh", []))


def sync_models_to_keywords():
    """将 gpu_products.yaml 最新型号同步到 keywords.yaml 的 models 列表

    只添加不删除，保留手动添加的型号。
    """
    auto_models = _get_hot_models_from_products()
    if not auto_models:
        return

    config = _load_keywords_config()
    changed = False

    for lang in ("zh", "en"):
        search = config.setdefault("search", {}).setdefault(lang, {})
        existing = search.get("models", [])
        existing_set = set(existing)

        for model in auto_models:
            if model not in existing_set:
                existing.append(model)
                changed = True

        search["models"] = existing

    if changed:
        with _file_lock(KEYWORDS_PATH):
            with open(KEYWORDS_PATH, "w", encoding="utf-8") as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        print(f"  型号同步: {len(auto_models)} 个热门型号已同步到 keywords.yaml")


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


def discover_hot_words(posts: list[dict], min_freq: int = 2,
                       insights: list[dict] = None) -> dict:
    """从帖子 + AI 分析结果中发现高频新词

    双来源策略：
    1. AI 输出（主）：从痛点名称、隐藏需求中提取关键词（高质量）
    2. 原始帖子（辅）：只提取英文技术术语（单词级别）
    中文热词完全依赖 AI 输出，不做正则切词。
    """
    existing = set()
    config = _load_keywords_config()
    for lang in ("zh", "en"):
        for cat in ("pain", "models", "brands"):
            existing.update(w.lower() for w in config.get("search", {}).get(lang, {}).get(cat, []))
        existing.update(w.lower() for w in config.get("signals", {}).get(lang, []))

    zh_counter = Counter()
    en_counter = Counter()

    # ── 来源 1：AI 分析结果（主路径）──
    if insights:
        for insight in insights:
            # 痛点名称：去掉"显卡"前缀和"问题"后缀，提取核心词
            pain = insight.get("pain_point", "")
            for prefix in ["显卡", "GPU"]:
                if pain.startswith(prefix):
                    pain = pain[len(prefix):]
            for suffix in ["问题", "不足", "困难"]:
                if pain.endswith(suffix):
                    pain = pain[:-len(suffix)]
            pain = pain.strip()

            # 中文：按标点/逗号/空格分段，每段作为候选词（2-6字）
            zh_segments = re.split(r'[，。、；！？\s,.:;!?/\-—()（）\[\]【】]', pain)
            for seg in zh_segments:
                seg = seg.strip()
                # 只保留纯中文或中文+数字的段（2-6字）
                if re.match(r'^[\u4e00-\u9fffA-Za-z0-9]{2,6}$', seg):
                    if seg not in STOPWORDS_ZH and seg.lower() not in existing:
                        zh_counter[seg] += 1

            # 隐藏需求中的关键词（同样按段提取）
            need = insight.get("hidden_need", "") or insight.get("inferred_need", "") or ""
            zh_need_segments = re.split(r'[，。、；！？\s,.:;!?/\-—()（）\[\]【】]', need)
            for seg in zh_need_segments:
                seg = seg.strip()
                if re.match(r'^[\u4e00-\u9fffA-Za-z0-9]{2,6}$', seg):
                    if seg not in STOPWORDS_ZH and seg.lower() not in existing:
                        zh_counter[seg] += 1

            # 英文关键词（从痛点和需求中提取单词）
            for text in [pain, need]:
                en_words = re.findall(r'\b[a-zA-Z]{4,15}\b', text)
                for w in en_words:
                    w = w.lower()
                    if w not in STOPWORDS_EN and w not in existing:
                        en_counter[w] += 1

    # ── 来源 2：原始帖子（辅助，只提取英文技术术语）──
    for post in posts:
        title = post.get("title", "")
        # 英文：只匹配独立单词（4-15 字母），不匹配短语
        en_words = re.findall(r'\b[a-zA-Z]{4,15}\b', title)
        for w in en_words:
            w = w.lower()
            if w not in STOPWORDS_EN and w not in existing and len(w) >= 4:
                en_counter[w] += 1

    new_zh = [w for w, c in zh_counter.most_common(MAX_DISCOVERED_ZH) if c >= min_freq]
    new_en = [w for w, c in en_counter.most_common(MAX_DISCOVERED_EN) if c >= min_freq]

    return {"zh": new_zh, "en": new_en}


def discover_from_db(min_mentions: int = 2) -> dict:
    """从 DB 历史数据中提取高频痛点表达词 → 补充到 discovered 热词

    扫描 pain_points 表，提取用户真实痛点表达（闪退、卡死、黑屏重启等）。
    同时统计 GPU 型号讨论热度，返回供搜索关键词排序用。
    """
    import sqlite3
    db_path = Path("data/gpu_insight.db")
    if not db_path.exists():
        return {"zh": [], "en": [], "model_ranks": []}

    conn = sqlite3.connect(str(db_path))

    # 1. 从痛点名称中提取表达词
    config = _load_keywords_config()
    existing = set()
    for lang in ("zh", "en"):
        for cat in ("pain", "models", "brands"):
            existing.update(w.lower() for w in config.get("search", {}).get(lang, {}).get(cat, []))
        existing.update(w.lower() for w in config.get("signals", {}).get(lang, []))

    zh_counter = Counter()
    en_counter = Counter()

    pain_rows = conn.execute("SELECT pain_point, hidden_need FROM pain_points").fetchall()
    for pain_point, hidden_need in pain_rows:
        for text in [pain_point or "", hidden_need or ""]:
            # 按标点分段
            segments = re.split(r'[，。、；！？\s,.:;!?/\-—()（）\[\]【】]', text)
            for seg in segments:
                seg = seg.strip()
                # 去掉"显卡"前缀
                for prefix in ["显卡", "GPU"]:
                    if seg.startswith(prefix):
                        seg = seg[len(prefix):]
                for suffix in ["问题", "不足", "困难"]:
                    if seg.endswith(suffix) and len(seg) > len(suffix) + 1:
                        seg = seg[:-len(suffix)]
                seg = seg.strip()
                if not seg:
                    continue

                # 中文 2-6 字
                if re.match(r'^[\u4e00-\u9fff]{2,6}$', seg):
                    if seg not in STOPWORDS_ZH and seg.lower() not in existing:
                        zh_counter[seg] += 1

                # 英文 4-15 字母
                en_words = re.findall(r'\b[a-zA-Z]{4,15}\b', seg)
                for w in en_words:
                    w = w.lower()
                    if w not in STOPWORDS_EN and w not in existing:
                        en_counter[w] += 1

    # 2. 统计 GPU 型号讨论热度
    from src.utils.gpu_tagger import tag_post
    model_counter = Counter()
    title_rows = conn.execute("SELECT title FROM posts").fetchall()
    for (title,) in title_rows:
        post = {"title": title, "content": title}
        tag_post(post)
        for m in post.get("_gpu_tags", {}).get("models", []):
            model_counter[m] += 1

    conn.close()

    new_zh = [w for w, c in zh_counter.most_common(MAX_DISCOVERED_ZH) if c >= min_mentions]
    new_en = [w for w, c in en_counter.most_common(MAX_DISCOVERED_EN) if c >= min_mentions]
    model_ranks = [m for m, c in model_counter.most_common(10)]

    return {"zh": new_zh, "en": new_en, "model_ranks": model_ranks}


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

    with _file_lock(KEYWORDS_PATH):
        with open(KEYWORDS_PATH, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    zh_count = len(discovered.get("zh", []))
    en_count = len(discovered.get("en", []))
    print(f"  热词库: {zh_count}/{MAX_DISCOVERED_ZH} 中文, {en_count}/{MAX_DISCOVERED_EN} 英文")
