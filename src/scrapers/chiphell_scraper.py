"""GPU-Insight Chiphell 爬虫（Phase 1 MVP）— Data Engineer + Fullstack 协作"""

import re
import json
from datetime import datetime
from .base_scraper import BaseScraper


class ChiphellScraper(BaseScraper):
    """Chiphell 论坛爬虫 — 使用 httpx + BeautifulSoup 解析"""

    def __init__(self, config: dict):
        super().__init__("chiphell", config)
        self.base_url = self.source_config.get("url", "https://www.chiphell.com")
        self.sections = self.source_config.get("sections", ["显卡", "硬件"])
        # 显卡区 forum id
        self.forum_urls = [
            f"{self.base_url}/forum-80-1.html",  # 显卡区
        ]

    def fetch_posts(self, last_id: str = None) -> list[dict]:
        """抓取 Chiphell 显卡板块新帖"""
        posts = []
        try:
            import httpx
            from bs4 import BeautifulSoup

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9",
            }

            for forum_url in self.forum_urls:
                try:
                    self.random_delay(1.0, 3.0)
                    resp = httpx.get(forum_url, headers=headers, timeout=30, follow_redirects=True)
                    resp.raise_for_status()

                    soup = BeautifulSoup(resp.text, "html.parser")
                    # Discuz 论坛结构：帖子列表在 #threadlisttableid 或 .bm_c
                    thread_list = soup.select("tbody[id^='normalthread_']")

                    for thread in thread_list:
                        try:
                            post = self._parse_thread(thread, last_id)
                            if post:
                                posts.append(post)
                        except Exception as e:
                            continue

                except httpx.HTTPError as e:
                    print(f"    ⚠️ 请求失败 {forum_url}: {e}")
                    continue

        except ImportError as e:
            print(f"  ⚠️ 缺少依赖: {e}")
            print("     请运行: pip install httpx beautifulsoup4 lxml")

        return posts

    def _parse_thread(self, thread, last_id: str = None) -> dict | None:
        """解析单个帖子"""
        # 提取帖子 ID
        tbody_id = thread.get("id", "")
        post_id = tbody_id.replace("normalthread_", "")

        if last_id and post_id <= last_id:
            return None

        # 标题和链接
        title_tag = thread.select_one("a.s.xst")
        if not title_tag:
            return None
        title = title_tag.get_text(strip=True)
        href = title_tag.get("href", "")
        url = f"{self.base_url}/{href}" if not href.startswith("http") else href

        # 作者
        author_tag = thread.select_one("td.by cite a")
        author = author_tag.get_text(strip=True) if author_tag else "anonymous"

        # 回复数和查看数
        replies_tag = thread.select_one("td.num a")
        replies = int(replies_tag.get_text(strip=True)) if replies_tag else 0

        views_tag = thread.select_one("td.num em")
        views = int(views_tag.get_text(strip=True)) if views_tag else 0

        return {
            "id": f"chh_{post_id}",
            "source": "chiphell",
            "_source": "chiphell",
            "title": title,
            "content": title,  # 列表页只有标题，详情需要二次抓取
            "url": url,
            "author_hash": self.hash_author(author),
            "replies": replies,
            "likes": views,  # 用浏览量近似
            "language": "zh-CN",
            "timestamp": datetime.now().isoformat(),
        }

    def fetch_post_detail(self, url: str) -> str:
        """抓取帖子详情内容（二次请求）"""
        try:
            import httpx
            from bs4 import BeautifulSoup

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
            self.random_delay(2.0, 5.0)
            resp = httpx.get(url, headers=headers, timeout=30, follow_redirects=True)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            # 主楼内容
            post_msg = soup.select_one("td.t_f")
            if post_msg:
                # 去掉引用和签名
                for tag in post_msg.select(".quote, .sign"):
                    tag.decompose()
                return post_msg.get_text(strip=True)[:2000]
        except Exception:
            pass
        return ""
