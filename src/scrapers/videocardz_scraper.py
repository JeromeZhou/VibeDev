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
        posts = []

        try:
            resp = self.safe_request("https://videocardz.com/",
                                     referer="https://www.google.com/",
                                     delay=(3.0, 5.0),
                                     cookies=self.cookies if self.cookies else None)
            if not resp or resp.status_code != 200:
                print(f"    [!] VideoCardz: 请求失败 (status={resp.status_code if resp else 'None'})")
                return []

            # 提取文章链接和标题
            # 多种 CSS class 匹配：story-title, entry-title, post-title
            seen = set()
            for match in re.finditer(
                r'href=["\']?(https://videocardz\.com/(?:newz|press-release|review)/[^\s<>"\']+)["\']?.*?'
                r'(?:story-title|entry-title|post-title|news-title)[^>]*>([^<]+)<',
                resp.text, re.DOTALL
            ):
                url = match.group(1).strip().rstrip('"\'')
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

            # 备用策略 1：先找链接，再在附近找标题文本
            if not posts:
                for match in re.finditer(
                    r'<a[^>]+href=["\']?(https://videocardz\.com/(?:newz|press-release|review)/([^\s<>"\']+))["\']?[^>]*>([^<]{10,})</a>',
                    resp.text
                ):
                    url = match.group(1).strip().rstrip('"\'')
                    slug = match.group(2).strip()
                    title = match.group(3).strip()
                    if url in seen or not title or title.lower() in ("read full story", "read more", "continue reading"):
                        continue
                    seen.add(url)
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

            # 备用策略 2：从 URL slug 生成标题
            if not posts:
                for match in re.finditer(
                    r'href=["\']?(https://videocardz\.com/(?:newz|press-release|review)/([^\s<>"\']+))["\']?',
                    resp.text
                ):
                    url = match.group(1).strip().rstrip('"\'')
                    slug = match.group(2).strip()
                    if url in seen:
                        continue
                    seen.add(url)
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

            if not posts:
                # 调试：输出页面中找到的链接数量
                all_links = re.findall(r'https://videocardz\.com/(?:newz|press-release|review)/', resp.text)
                print(f"    [debug] VideoCardz: 页面中找到 {len(all_links)} 个文章链接但无法提取标题")

        except Exception as e:
            print(f"    [!] VideoCardz 抓取失败: {e}")

        return posts
