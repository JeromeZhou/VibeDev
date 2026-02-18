"""GPU-Insight 数据清洗模块"""

import json
import re
import hashlib
from datetime import datetime
from pathlib import Path


def clean_data(posts: list[dict], config: dict) -> list[dict]:
    """清洗数据：去重 + 规范化 + 截断"""
    if not posts:
        return []

    # 1. 编码统一（Python 默认 UTF-8）
    # 2. 繁简转换
    posts = _convert_traditional(posts)
    # 3. 内存去重（同批次内）
    posts = _deduplicate(posts)
    # 4. 持久化去重已在爬虫层完成（scrape_all_forums → filter_new_posts + save_posts）
    #    此处不再重复过滤，避免爬虫 save_posts 后 cleaner 误判为"旧帖"
    # 5. 截断长文本
    posts = _truncate(posts, max_chars=2000)
    # 6. 保存清洗结果
    _save_cleaned(posts, config)

    return posts


def _convert_traditional(posts: list[dict]) -> list[dict]:
    """繁简转换"""
    try:
        import opencc
        converter = opencc.OpenCC("t2s")
        for post in posts:
            if "content" in post:
                post["content"] = converter.convert(post["content"])
            if "title" in post:
                post["title"] = converter.convert(post["title"])
    except ImportError:
        pass  # opencc 未安装时跳过
    return posts


def _deduplicate(posts: list[dict]) -> list[dict]:
    """SimHash 去重（简化版：基于内容哈希）"""
    seen = set()
    unique = []
    for post in posts:
        content = post.get("content", "") or post.get("title", "")
        h = hashlib.md5(content.encode()).hexdigest()
        if h not in seen:
            seen.add(h)
            unique.append(post)
    return unique


def _truncate(posts: list[dict], max_chars: int = 2000) -> list[dict]:
    """截断长文本"""
    for post in posts:
        if "content" in post and len(post["content"]) > max_chars:
            post["content"] = post["content"][:max_chars] + "..."
            post["_truncated"] = True
    return posts


def _save_cleaned(posts: list[dict], config: dict):
    """保存清洗后数据"""
    output_dir = Path(config.get("paths", {}).get("processed_data", "data/processed"))
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_file = output_dir / f"cleaned_{date_str}.jsonl"
    with open(output_file, "a", encoding="utf-8") as f:
        for post in posts:
            f.write(json.dumps(post, ensure_ascii=False) + "\n")
