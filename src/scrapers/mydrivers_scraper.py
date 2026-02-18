"""GPU-Insight 快科技(MyDrivers) 爬虫 — 中文硬件新闻"""

import re
import json
from datetime import datetime
from pathlib import Path
from .base_scraper import BaseScraper
from src.utils.gpu_tagger import tag_post


class MyDriversScraper(BaseScraper):
    """快科技(MyDrivers) 爬虫 — 中文硬件新闻和评测"""

    def __init__(self, config: dict):
        super().__init__("mydrivers", config)
        self.cookies = self._load_cookies()

    def _load_cookies(self) -> dict:
        cookie_file = Path("cookies/mydrivers.json")
        if not cookie_file.exists():
            return {}
        with open(cookie_file, "r", encoding="utf-8") as f:
            cookie_list = json.load(f)
        return {c["name"]: c["value"] for c in cookie_list
                if "mydrivers" in c.get("domain", "") or "快科技" in c.get("domain", "")}

    def fetch_posts(self, last_id: str = None) -> list[dict]:
        """抓取快科技显卡相关新闻"""
        posts = []
        seen = set()

        # 快科技首页（新闻频道 URL 已失效，直接用首页）
        urls_to_try = [
            "https://www.mydrivers.com/",
        ]

        for page_url in urls_to_try:
            try:
                resp = self.safe_request(page_url,
                                         referer="https://www.mydrivers.com/",
                                         delay=(2.0, 4.0),
                                         extra_headers={"Accept-Language": "zh-CN,zh;q=0.9"})
                if not resp or resp.status_code != 200:
                    print(f"    [!] 快科技: 请求失败 {page_url}")
                    continue

                # 提取新闻链接和标题
                # 快科技文章 URL 格式: //news.mydrivers.com/1/xxx/xxx.htm
                for match in re.finditer(
                    r'href="((?:https?:)?//news\.mydrivers\.com/1/\d+/\d+\.htm)"[^>]*>'
                    r'\s*([^<]{5,}?)\s*</a>',
                    resp.text, re.DOTALL
                ):
                    url = match.group(1).strip()
                    if url.startswith("//"):
                        url = "https:" + url
                    title = match.group(2).strip()
                    title = re.sub(r'\s+', ' ', title)
                    title = re.sub(r'<[^>]+>', '', title).strip()

                    if not title or url in seen or len(title) < 5:
                        continue

                    # 过滤非显卡相关（快科技覆盖面很广）
                    gpu_keywords = [
                        "显卡", "GPU", "RTX", "RX", "NVIDIA", "AMD", "Radeon",
                        "GeForce", "驱动", "光追", "DLSS", "FSR", "帧",
                        "4090", "4080", "4070", "4060", "5090", "5080", "5070",
                        "7900", "7800", "7700", "7600", "9070",
                        "Intel Arc", "锐炫",
                    ]
                    if not any(kw.lower() in title.lower() for kw in gpu_keywords):
                        continue

                    seen.add(url)
                    # 从 URL 提取 ID
                    id_match = re.search(r'/1/(\d+)/(\d+)\.htm', url)
                    post_id = f"myd_{id_match.group(1)}_{id_match.group(2)}" if id_match else f"myd_{len(posts)}"

                    posts.append({
                        "id": post_id,
                        "source": "mydrivers",
                        "_source": "mydrivers",
                        "title": title,
                        "content": title,
                        "url": url,
                        "author_hash": self.hash_author("mydrivers"),
                        "replies": 0,
                        "likes": 0,
                        "language": "zh-CN",
                        "timestamp": datetime.now().isoformat(),
                    })

            except Exception as e:
                print(f"    [!] 快科技抓取失败: {e}")

        # GPU 标签
        for p in posts:
            tag_post(p)

        return posts
