"""NGA 爬虫测试"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
import functools
print = functools.partial(print, flush=True)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.config import load_config
from src.scrapers.nga_scraper import NGAScraper

config = load_config('config/config.yaml')
nga = NGAScraper(config)

print("NGA 爬虫测试")
print(f"Cookie 数量: {len(nga.cookies)}")
print(f"关键 Cookie: ngaPassportUid={nga.cookies.get('ngaPassportUid', '无')}")
print()

posts = nga.fetch_posts()
print(f"\n总计: {len(posts)} 条")
print()

for i, p in enumerate(posts[:15], 1):
    tags = p.get("_gpu_tags", {})
    models = ", ".join(tags.get("models", [])) or "-"
    brands = ", ".join(tags.get("brands", [])) or "-"
    print(f"  {i:2d}. [{p['replies']}回复] {p['title'][:60]}")
    print(f"      GPU: {brands}/{models} | {p['url']}")
    print()
