"""GPU-Insight 爬虫模块"""

from src.utils.config import get_enabled_sources


def scrape_all_forums(config: dict) -> list[dict]:
    """串行抓取所有已启用的论坛"""
    from .chiphell_scraper import ChiphellScraper
    from .reddit_scraper import RedditScraper
    from .tieba_scraper import TiebaScraper
    from .nga_scraper import NGAScraper

    scraper_map = {
        "chiphell": ChiphellScraper,
        "reddit": RedditScraper,
        "tieba": TiebaScraper,
        "nga": NGAScraper,
    }

    enabled = get_enabled_sources(config)
    all_posts = []

    for source_name, source_config in enabled.items():
        scraper_cls = scraper_map.get(source_name)
        if scraper_cls:
            print(f"  抓取 {source_name}...")
            scraper = scraper_cls(config)
            posts = scraper.scrape()
            all_posts.extend(posts)
            print(f"    获取 {len(posts)} 条")
        else:
            print(f"  {source_name} 爬虫尚未实现，跳过")

    return all_posts
