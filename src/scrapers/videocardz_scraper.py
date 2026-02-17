"""GPU-Insight VideoCardz 爬虫 — 英文显卡新闻/评测源"""

import json
import re
from datetime import datetime
from pathlib import Path
from .base_scraper import BaseScraper


class VideoCardzScraper(BaseScraper):
    """VideoCardz.com 爬虫 — GPU 新闻和评测"""

    def __init__(self, config: dict):
        super().__init__("videocardz", config)
        self.cookies = self._load_cookies()

    def _load_cookies(self) -> dict:
        cookie_file = Path("cookies/videocardz.json")
        if not cookie_file.exists():
            return {}
        with open(cookie_file, "r", encoding="utf-8") as f:
            cookie_list = json.load(f)
        return {c["name"]: c["value"] for c in cookie_list if "videocardz.com" in c.get("domain", "")}

    def fetch_posts(self, last_id: str = None) -> list[dict]:
        """抓取 VideoCardz 首页文章"""
        import httpx

        posts = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
        }

        try:
            self.random_delay(1.0, 2.0)
            resp = httpx.get("https://videocardz.com/", headers=headers,
                             cookies=self.cookies, timeout=15, follow_redirects=True)
            if resp.status_code != 200:
                print(f"    [!] VideoCardz: {resp.status_code}")
                return []

            # 提取文章链接和标题
            # Pattern: href=https://videocardz.com/newz/... 或 /press-release/...
            seen = set()
            for match in re.finditer(
                r'href=(https://videocardz\.com/(?:newz|press-release|review)/[^\s<>"]+).*?'
                r'(?:story-title|entry-title)[^>]*>([^<]+)<',
                resp.text, re.DOTALL
            ):
                url = match.group(1).strip()
                title = match.group(2).strip()
                if not title or url in seen:
                    continue
                seen.add(url)

                post_id = url.rstrip("/").split("/")[-1][:60]
                posts.append({
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
                })

            # 备用：更宽松的匹配
            if not posts:
                for match in re.finditer(
                    r'href=(https://videocardz\.com/(?:newz|press-release|review)/([^\s<>"]+))',
                    resp.text
                ):
                    url = match.group(1).strip()
                    slug = match.group(2).strip()
                    if url in seen:
                        continue
                    seen.add(url)
                    # 从 slug 生成标题
                    title = slug.rstrip("/").split("/")[-1].replace("-", " ").title()
                    post_id = slug.rstrip("/").split("/")[-1][:60]
                    posts.append({
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
                    })

        except Exception as e:
            print(f"    [!] VideoCardz 抓取失败: {e}")

        return posts
