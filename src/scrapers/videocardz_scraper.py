"""GPU-Insight VideoCardz 爬虫 — 英文显卡新闻/评测源

从 www.videocardz.com 首页 HTML 提取文章链接和标题。
虽然页面是 JS 渲染的，但文章 URL 嵌在 HTML 中可直接提取。
"""

import re
from datetime import datetime
from .base_scraper import BaseScraper
from src.utils.gpu_tagger import tag_post


class VideoCardzScraper(BaseScraper):
    """VideoCardz.com 爬虫 — GPU 新闻和评测"""

    def __init__(self, config: dict):
        super().__init__("videocardz", config)

    def fetch_posts(self, last_id: str = None) -> list[dict]:
        """从首页 HTML 提取文章链接"""
        posts = []

        try:
            # 禁用 Brotli（httpx 未装 brotli 包会返回乱码）
            resp = self.safe_request(
                "https://www.videocardz.com/",
                referer="https://www.google.com/",
                delay=(3.0, 5.0),
                extra_headers={"Accept-Encoding": "gzip, deflate"},
            )
            if not resp or resp.status_code != 200:
                print(f"    [!] VideoCardz: HTTP {resp.status_code if resp else 'None'}")
                return []

            # 从 HTML 提取文章 URL（newz/press-release/review）
            seen = set()
            for match in re.finditer(
                r'https://(?:www\.)?videocardz\.com/(?:newz|press-release|review)/([a-z0-9-]+(?:/[a-z0-9-]+)*)',
                resp.text
            ):
                url = match.group(0).rstrip('/"\'')
                slug = match.group(1).rstrip('/"\'')
                if url not in seen:
                    seen.add(url)
                    # slug → 标题：nvidia-rtx-5090-review → Nvidia Rtx 5090 Review
                    title = slug.split('/')[-1].replace('-', ' ').title()
                    post_id = slug.split('/')[-1][:60]

                    post = {
                        "id": f"vcz_{post_id}",
                        "source": "videocardz",
                        "_source": "videocardz",
                        "title": title,
                        "content": title,
                        "url": url,
                        "author_hash": self.hash_author("videocardz"),
                        "replies": 0,
                        "likes": 0,
                        "language": "en",
                        "timestamp": datetime.now().isoformat(),
                    }
                    tag_post(post)
                    posts.append(post)

            if posts:
                print(f"    {len(posts)} 篇文章")
            else:
                print(f"    [!] VideoCardz: 未提取到文章")

        except Exception as e:
            print(f"    [!] VideoCardz 抓取失败: {e}")

        return posts
