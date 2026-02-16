"""GPU-Insight Reddit 爬虫 — Data Engineer 产出"""

import os
from datetime import datetime
from .base_scraper import BaseScraper


class RedditScraper(BaseScraper):
    """Reddit 爬虫 — 使用官方 JSON API（无需认证）"""

    def __init__(self, config: dict):
        super().__init__("reddit", config)
        self.subreddits = self.source_config.get("subreddits", ["nvidia", "amd", "hardware"])

    def fetch_posts(self, last_id: str = None) -> list[dict]:
        """抓取 Reddit 显卡相关 subreddit"""
        posts = []
        try:
            import httpx

            headers = {
                "User-Agent": "GPU-Insight/1.0 (research bot)",
            }

            for sub in self.subreddits:
                try:
                    self.random_delay(2.0, 4.0)
                    url = f"https://www.reddit.com/r/{sub}/new.json?limit=25"
                    resp = httpx.get(url, headers=headers, timeout=30, follow_redirects=True)
                    resp.raise_for_status()
                    data = resp.json()

                    for child in data.get("data", {}).get("children", []):
                        post_data = child.get("data", {})
                        post_id = post_data.get("id", "")

                        if last_id and post_id <= last_id:
                            continue

                        title = post_data.get("title", "")
                        content = post_data.get("selftext", "")[:2000]

                        # 过滤：只要和显卡相关的
                        gpu_keywords = ["gpu", "nvidia", "amd", "rtx", "radeon", "vram",
                                       "显卡", "driver", "cuda", "geforce", "4060", "4070",
                                       "4080", "4090", "5070", "5080", "5090", "rx 7", "rx 9"]
                        text_lower = (title + " " + content).lower()
                        if not any(kw in text_lower for kw in gpu_keywords):
                            continue

                        posts.append({
                            "id": f"reddit_{post_id}",
                            "source": "reddit",
                            "_source": "reddit",
                            "title": title,
                            "content": content if content else title,
                            "url": f"https://reddit.com{post_data.get('permalink', '')}",
                            "author_hash": self.hash_author(post_data.get("author", "anon")),
                            "replies": post_data.get("num_comments", 0),
                            "likes": post_data.get("score", 0),
                            "language": "en",
                            "timestamp": datetime.fromtimestamp(
                                post_data.get("created_utc", 0)
                            ).isoformat(),
                        })

                    print(f"    r/{sub}: {len([p for p in posts if f'reddit_' in p.get('id','')])} 条")

                except Exception as e:
                    print(f"    ⚠️ r/{sub} 失败: {e}")
                    continue

        except ImportError:
            print("  ⚠️ 需要安装 httpx: pip install httpx")

        return posts
