"""GPU-Insight Chiphell 爬虫 — Playwright 版本，绕过 567 反爬"""

import re
import json
from datetime import datetime
from pathlib import Path
from .base_scraper import BaseScraper
from src.utils.gpu_tagger import tag_post


class ChiphellPlaywrightScraper(BaseScraper):
    """Chiphell 论坛爬虫 — 使用 Playwright 渲染页面"""

    def __init__(self, config: dict):
        super().__init__("chiphell", config)
        self.base_url = self.source_config.get("url", "https://www.chiphell.com")
        self.forum_urls = [
            f"{self.base_url}/forum-80-1.html",  # 显卡区
        ]
        self.cookies = self._load_cookies()

    def _load_cookies(self) -> list[dict]:
        """加载 Chiphell cookies"""
        cookie_file = Path("cookies/chiphell.json")
        if not cookie_file.exists():
            return []
        with open(cookie_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def fetch_posts(self, last_id: str = None) -> list[dict]:
        """使用 Playwright 抓取 Chiphell 显卡区"""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print("    [!] playwright 未安装，跳过 Chiphell")
            return []

        posts = []
        seen_ids = set()

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                    locale="zh-CN",
                )

                # 注入 cookies
                if self.cookies:
                    context.add_cookies(self.cookies)

                page = context.new_page()

                for forum_url in self.forum_urls:
                    try:
                        self.random_delay(2.0, 4.0)
                        page.goto(forum_url, wait_until="domcontentloaded", timeout=30000)
                        # 等待帖子列表加载
                        page.wait_for_selector("tbody[id^='normalthread_']", timeout=10000)

                        # 提取帖子
                        threads = page.query_selector_all("tbody[id^='normalthread_']")
                        for thread in threads:
                            try:
                                post = self._parse_thread_element(thread, last_id)
                                if post and post["id"] not in seen_ids:
                                    seen_ids.add(post["id"])
                                    posts.append(post)
                            except Exception:
                                continue

                    except Exception as e:
                        print(f"    [!] Chiphell Playwright 加载失败: {e}")

                browser.close()

        except Exception as e:
            print(f"    [!] Chiphell Playwright 启动失败: {e}")
            # 降级到 httpx 方案
            return self._fallback_fetch(last_id)

        # GPU 标签
        for p in posts:
            tag_post(p)

        return posts

    def _parse_thread_element(self, thread, last_id: str = None) -> dict | None:
        """从 Playwright element 解析帖子"""
        tbody_id = thread.get_attribute("id") or ""
        post_id = tbody_id.replace("normalthread_", "")

        if last_id and post_id <= last_id:
            return None

        # 标题和链接
        title_el = thread.query_selector("a.s.xst")
        if not title_el:
            return None
        title = title_el.inner_text().strip()
        href = title_el.get_attribute("href") or ""
        url = f"{self.base_url}/{href}" if not href.startswith("http") else href

        # 作者
        author_el = thread.query_selector("td.by cite a")
        author = author_el.inner_text().strip() if author_el else "anonymous"

        # 回复数
        replies_el = thread.query_selector("td.num a")
        replies = 0
        if replies_el:
            try:
                replies = int(replies_el.inner_text().strip())
            except ValueError:
                pass

        # 查看数
        views_el = thread.query_selector("td.num em")
        views = 0
        if views_el:
            try:
                views = int(views_el.inner_text().strip())
            except ValueError:
                pass

        return {
            "id": f"chh_{post_id}",
            "source": "chiphell",
            "_source": "chiphell",
            "title": title,
            "content": title,
            "url": url,
            "author_hash": self.hash_author(author),
            "replies": replies,
            "likes": views,
            "language": "zh-CN",
            "timestamp": datetime.now().isoformat(),
        }

    def _fallback_fetch(self, last_id: str = None) -> list[dict]:
        """降级方案：用 httpx 尝试"""
        import httpx

        posts = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
        }
        cookie_dict = {c["name"]: c["value"] for c in self.cookies if "chiphell" in c.get("domain", "")}

        for forum_url in self.forum_urls:
            try:
                self.random_delay(1.0, 3.0)
                resp = httpx.get(forum_url, headers=headers, cookies=cookie_dict,
                                 timeout=15, follow_redirects=True)
                if resp.status_code == 200:
                    posts.extend(self._parse_html(resp.text, last_id))
                else:
                    print(f"    [!] Chiphell httpx 降级: {resp.status_code}")
            except Exception as e:
                print(f"    [!] Chiphell httpx 降级失败: {e}")

        return posts

    def _parse_html(self, html: str, last_id: str = None) -> list[dict]:
        """从 HTML 解析帖子列表"""
        from bs4 import BeautifulSoup

        posts = []
        soup = BeautifulSoup(html, "html.parser")
        threads = soup.select("tbody[id^='normalthread_']")

        for thread in threads:
            tbody_id = thread.get("id", "")
            post_id = tbody_id.replace("normalthread_", "")
            if last_id and post_id <= last_id:
                continue

            title_tag = thread.select_one("a.s.xst")
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            href = title_tag.get("href", "")
            url = f"{self.base_url}/{href}" if not href.startswith("http") else href

            author_tag = thread.select_one("td.by cite a")
            author = author_tag.get_text(strip=True) if author_tag else "anonymous"

            replies_tag = thread.select_one("td.num a")
            replies = int(replies_tag.get_text(strip=True)) if replies_tag else 0

            views_tag = thread.select_one("td.num em")
            views = int(views_tag.get_text(strip=True)) if views_tag else 0

            posts.append({
                "id": f"chh_{post_id}",
                "source": "chiphell",
                "_source": "chiphell",
                "title": title,
                "content": title,
                "url": url,
                "author_hash": self.hash_author(author),
                "replies": replies,
                "likes": views,
                "language": "zh-CN",
                "timestamp": datetime.now().isoformat(),
            })

        return posts
