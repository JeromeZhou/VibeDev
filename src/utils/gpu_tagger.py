"""GPU-Insight GPU 产品标签识别器 — L0 本地正则，零 token"""

import re
import yaml
from pathlib import Path
from typing import Optional

_PRODUCTS: Optional[dict] = None


def _load_products() -> dict:
    global _PRODUCTS
    if _PRODUCTS is None:
        path = Path(__file__).parent.parent.parent / "config" / "gpu_products.yaml"
        with open(path, "r", encoding="utf-8") as f:
            _PRODUCTS = yaml.safe_load(f)
    return _PRODUCTS


def _build_model_patterns(products: dict) -> list[tuple[str, str, str, re.Pattern]]:
    """构建 (brand, series, model, pattern) 列表，按型号长度降序（优先匹配长型号）"""
    patterns = []
    for brand_key, brand_info in products.get("brands", {}).items():
        brand_name = brand_key.upper()
        for series in brand_info.get("series", []):
            series_name = series["name"]
            for model in series.get("models", []):
                # 构建灵活正则：RTX 5070 Ti → RTX\s*5070\s*Ti
                escaped = re.escape(model)
                # 允许空格可选、大小写不敏感
                flex = escaped.replace(r"\ ", r"\s*")
                pat = re.compile(flex, re.IGNORECASE)
                patterns.append((brand_name, series_name, model, pat))
    # 长型号优先匹配（避免 "5070 Ti" 被 "5070" 先匹配）
    patterns.sort(key=lambda x: len(x[2]), reverse=True)
    return patterns


def _make_pattern(alias: str) -> re.Pattern:
    """构建匹配模式：中文用直接匹配，英文用词边界"""
    escaped = re.escape(alias)
    if any(ord(c) > 127 for c in alias):
        # 中文/非 ASCII：直接匹配，不加词边界
        return re.compile(escaped, re.IGNORECASE)
    else:
        return re.compile(r'\b' + escaped + r'\b', re.IGNORECASE)


def _build_manufacturer_patterns(products: dict) -> list[tuple[str, re.Pattern]]:
    """构建厂商匹配模式"""
    patterns = []
    for mfr in products.get("manufacturers", []):
        name = mfr["name"]
        for alias in mfr.get("aliases", []):
            patterns.append((name, _make_pattern(alias)))
    return patterns


def _build_brand_patterns(products: dict) -> list[tuple[str, re.Pattern]]:
    """构建品牌别名匹配"""
    patterns = []
    for brand_key, brand_info in products.get("brands", {}).items():
        brand_name = brand_key.upper()
        for alias in brand_info.get("aliases", []):
            patterns.append((brand_name, _make_pattern(alias)))
    return patterns


# 模块级缓存
_MODEL_PATTERNS = None
_MFR_PATTERNS = None
_BRAND_PATTERNS = None


def _get_patterns():
    global _MODEL_PATTERNS, _MFR_PATTERNS, _BRAND_PATTERNS
    if _MODEL_PATTERNS is None:
        products = _load_products()
        _MODEL_PATTERNS = _build_model_patterns(products)
        _MFR_PATTERNS = _build_manufacturer_patterns(products)
        _BRAND_PATTERNS = _build_brand_patterns(products)
    return _MODEL_PATTERNS, _MFR_PATTERNS, _BRAND_PATTERNS


def tag_gpu_products(text: str) -> dict:
    """从文本中识别 GPU 产品标签

    返回:
        {
            "brands": ["NVIDIA"],
            "models": ["RTX 5070"],
            "series": ["RTX 50"],
            "manufacturers": ["ASUS"]
        }
    """
    model_pats, mfr_pats, brand_pats = _get_patterns()

    brands = set()
    models = set()
    series = set()
    manufacturers = set()

    # 匹配具体型号（同时确定品牌和系列）
    for brand, ser, model, pat in model_pats:
        if pat.search(text):
            brands.add(brand)
            models.add(model)
            series.add(ser)

    # 匹配品牌别名（补充没有具体型号但提到品牌的情况）
    for brand, pat in brand_pats:
        if pat.search(text):
            brands.add(brand)

    # 匹配板卡厂商
    for mfr, pat in mfr_pats:
        if pat.search(text):
            manufacturers.add(mfr)

    return {
        "brands": sorted(brands),
        "models": sorted(models),
        "series": sorted(series),
        "manufacturers": sorted(manufacturers),
    }


def tag_post(post: dict) -> dict:
    """给单条帖子打 GPU 产品标签，写入 _gpu_tags 字段"""
    text = f"{post.get('title', '')} {post.get('content', '')}"
    post["_gpu_tags"] = tag_gpu_products(text)
    return post


def tag_posts(posts: list[dict]) -> list[dict]:
    """批量打标签"""
    for post in posts:
        tag_post(post)
    return posts
