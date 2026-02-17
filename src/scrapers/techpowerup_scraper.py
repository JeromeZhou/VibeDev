"""GPU-Insight TechPowerUp 爬虫 — GPU 评测/新闻"""

import re
from datetime import datetime
from pathlib import Path
import json
from .base_scraper import BaseScraper
from src.utils.gpu_tagger import tag_post


class TechPowerUpScraper(BaseScraper):
    """TechPowerUp 爬虫 — GPU 新闻和评测"""

    def __init__(self, config: dict):
        super().__init__("techpowerup", config)
        self.cookies = self._load_cookies()

    def _load_cookies(self) -> dict:
        cookie_file = Path("cookies/techpowerup.json")
        if not cookie_file.exists():
            return {}
        with open(cookie_file, "r", encoding="utf-8") as f:
            cookie_list = json.load(f)
        return {c["name"]: c["value"] for c in cookie_list
                if "techpowerup.com" in c.get("domain", "")}

    def fetch_posts(self, last_id: str = None) -> list[dict]:
        """抓取 TechPowerUp GPU 新闻"""
        import httpx

        posts = []
        seen = set()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
        }

        try:
            self.random_delay(1.5, 3.0)
            resp = httpx.get("https://www.techpowerup.com/", headers=headers,
                             cookies=self.cookies, timeout=15, follow_redirects=True)
            if resp.status_code != 200:
                print(f"    [!] TechPowerUp: {resp.status_code}")
                return []

            html = resp.text

            # TechPowerUp 结构: <article class="newspost" data-id="343576">
            #   <h1><a href="/343576/..." class="newslink">TITLE</a></h1>
            for match in re.finditer(
                r'<article\s+class="newspost[^"]*"\s+data-id="(\d+)".*?'
                r'<h1>\s*<a\s+href="(/\d+/[^"]+)"\s*class="newslink">([^<]+)</a>\s*</h1>',
                html, re.DOTALL
            ):
                data_id = match.group(1)
                href = match.group(2).strip()
                title = match.group(3).strip()
                url = f"https://www.techpowerup.com{href}"

                if not title or url in seen:
                    continue
                seen.add(url)

                slug = href.rstrip("/").split("/")[-1][:60]
                posts.append({
                    "id": f"tpu_{slug}",
                    "source": "techpowerup",
                    "_source": "techpowerup",
                    "title": title,
                    "content": title,
                    "url": url,
                    "author_hash": self.hash_author("techpowerup"),
                    "replies": 0,
                    "likes": 0,
                    "language": "en",
                    "timestamp": datetime.now().isoformat(),
                })

        except Exception as e:
            print(f"    [!] TechPowerUp 抓取失败: {e}")

        # GPU 标签
        for p in posts:
            tag_post(p)

        return posts
