"""GPU-Insight VideoCardz 爬虫 — 英文显卡新闻/评测源

注意: VideoCardz 使用 Cloudflare + JS 渲染，httpx 无法获取文章内容。
首页返回 200 但内容是 JS 渲染的空壳，RSS/API/sitemap 全部 403。
需要 Playwright 才能正常抓取。当前作为降级模式运行。
"""

import json
import re
from datetime import datetime
from pathlib import Path
from .base_scraper import BaseScraper


class VideoCardzScraper(BaseScraper):
    """VideoCardz.com 爬虫 — GPU 新闻和评测

    当前状态: 降级模式（需要 Playwright 支持 JS 渲染）
    """

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
        """抓取 VideoCardz 文章 — 尝试从首页 HTML 提取，失败则静默跳过"""
        posts = []

        try:
            resp = self.safe_request("https://videocardz.com/",
                                     referer="https://www.google.com/",
                                     delay=(3.0, 5.0),
                                     cookies=self.cookies if self.cookies else None)
            if not resp or resp.status_code != 200:
                print(f"    [!] VideoCardz: HTTP {resp.status_code if resp else 'None'}")
                return []

            # VideoCardz 首页是 JS 渲染的，httpx 只能拿到空壳 HTML
            # 尝试从 HTML 中提取任何文章链接（可能在 <script> 或 preload 中）
            seen = set()

            # 策略 1: 标准 <a> 标签（带引号或不带引号的 href）
            for match in re.finditer(
                r'href=["\']?(https://videocardz\.com/(?:newz|press-release|review)/[^\s<>"\']+)',
                resp.text
            ):
                url = match.group(1).strip().rstrip('"\'')
                if url not in seen:
                    seen.add(url)

            # 策略 2: JSON/script 中的 URL
            for match in re.finditer(
                r'(https://videocardz\.com/(?:newz|press-release|review)/[a-z0-9-]+(?:/[a-z0-9-]+)*)',
                resp.text
            ):
                url = match.group(1).strip()
                if url not in seen:
                    seen.add(url)

            for url in seen:
                slug = url.rstrip("/").split("/")[-1]
                title = slug.replace("-", " ").title()
                post_id = slug[:60]
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

            if not posts:
                # JS 渲染页面，httpx 无法获取内容 — 这是预期行为
                print(f"    [!] VideoCardz: JS渲染页面，需要Playwright（降级跳过）")

        except Exception as e:
            print(f"    [!] VideoCardz 抓取失败: {e}")

        return posts
