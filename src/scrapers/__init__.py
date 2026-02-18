"""GPU-Insight 爬虫模块"""

from src.utils.config import get_enabled_sources


def scrape_all_forums(config: dict, skip_sources: list[str] = None) -> list[dict]:
    """串行抓取所有已启用的论坛（带增量检查点）

    Args:
        skip_sources: 跳过的数据源列表（轻量模式用）
    """
    from .chiphell_pw_scraper import ChiphellPlaywrightScraper
    from .reddit_scraper import RedditScraper
    from .tieba_scraper import TiebaScraper
    from .nga_scraper import NGAScraper
    from .videocardz_scraper import VideoCardzScraper
    from .bilibili_scraper import BilibiliScraper
    from .v2ex_scraper import V2EXScraper
    from .mydrivers_scraper import MyDriversScraper
    from .techpowerup_scraper import TechPowerUpScraper
    from src.utils.db import filter_new_posts, save_posts, save_checkpoint, get_checkpoint

    scraper_map = {
        "chiphell": ChiphellPlaywrightScraper,
        "reddit": RedditScraper,
        "tieba": TiebaScraper,
        "nga": NGAScraper,
        "videocardz": VideoCardzScraper,
        "bilibili": BilibiliScraper,
        "v2ex": V2EXScraper,
        "mydrivers": MyDriversScraper,
        "techpowerup": TechPowerUpScraper,
    }

    enabled = get_enabled_sources(config)
    all_posts = []

    for source_name, source_config in enabled.items():
        if skip_sources and source_name in skip_sources:
            print(f"  跳过 {source_name}（轻量模式）")
            continue
        scraper_cls = scraper_map.get(source_name)
        if scraper_cls:
            cp = get_checkpoint(source_name)
            cp_info = f"(上次: {cp['last_scrape_at'][:16]}, 累计: {cp['total_scraped']})" if cp else "(首次)"
            print(f"  抓取 {source_name} {cp_info}...")

            scraper = scraper_cls(config)
            posts = scraper.scrape()
            raw_count = len(posts)

            # 增量过滤：只保留新帖（在 save 之前过滤）
            new_posts = filter_new_posts(posts)
            # 保存所有帖子（新帖插入，旧帖更新互动数据）
            save_posts(posts)
            # 更新检查点
            save_checkpoint(source_name, len(new_posts))

            all_posts.extend(new_posts)  # 只传新帖给后续分析
            print(f"    获取 {raw_count} 条, 新增 {len(new_posts)} 条")
        else:
            print(f"  {source_name} 爬虫尚未实现，跳过")

    return all_posts
