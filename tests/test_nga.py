"""NGA 爬虫测试 — 需要网络和 cookies，仅手动运行"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
import functools
print = functools.partial(print, flush=True)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_NETWORK_TESTS") != "1",
    reason="需要网络+cookies，设置 RUN_NETWORK_TESTS=1 启用"
)


def test_nga_fetch():
    from src.utils.config import load_config
    from src.scrapers.nga_scraper import NGAScraper

    config = load_config('config/config.yaml')
    nga = NGAScraper(config)

    print("NGA 爬虫测试")
    print(f"Cookie 数量: {len(nga.cookies)}")
    print(f"关键 Cookie: ngaPassportUid={nga.cookies.get('ngaPassportUid', '无')}")

    posts = nga.fetch_posts()
    print(f"\n总计: {len(posts)} 条")
    assert len(posts) > 0, "NGA 应该抓到帖子"

    for i, p in enumerate(posts[:15], 1):
        tags = p.get("_gpu_tags", {})
        models = ", ".join(tags.get("models", [])) or "-"
        brands = ", ".join(tags.get("brands", [])) or "-"
        print(f"  {i:2d}. [{p['replies']}回复] {p['title'][:60]}")
        print(f"      GPU: {brands}/{models} | {p['url']}")


if __name__ == "__main__":
    os.environ["RUN_NETWORK_TESTS"] = "1"
    test_nga_fetch()
