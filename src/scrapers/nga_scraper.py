"""GPU-Insight NGA 爬虫 — 使用 Cookie 登录访问硬件区"""

import json
import re
from datetime import datetime
from pathlib import Path
from .base_scraper import BaseScraper
from src.utils.gpu_tagger import tag_post


class NGAScraper(BaseScraper):
    """NGA 玩家社区爬虫 — PC软硬件 + 消费电子"""

    # NGA 硬件相关板块
    FORUMS = {
        334: "PC软硬件",
        436: "消费电子IT新闻",
    }

    def __init__(self, config: dict):
        super().__init__("nga", config)
        self.cookies = self._load_cookies()

    def _load_cookies(self) -> dict:
        """从 cookies/nga.json 加载 Cookie"""
        cookie_file = Path("cookies/nga.json")
        if not cookie_file.exists():
            print("    [!] cookies/nga.json 不存在")
            return {}
        with open(cookie_file, "r", encoding="utf-8") as f:
            cookie_list = json.load(f)
        # 转为 {name: value} 字典，只取 .nga.cn 域名的
        return {c["name"]: c["value"] for c in cookie_list if ".nga.cn" in c.get("domain", "")}

    def fetch_posts(self, last_id: str = None) -> list[dict]:
        """抓取 NGA 硬件区帖子"""
        if not self.cookies:
            print("    [!] NGA Cookie 为空，跳过")
            return []

        posts = []
        seen_ids = set()

        for fid, name in self.FORUMS.items():
            print(f"    {name}(fid={fid})...", end=" ")
            page_posts = self._fetch_forum(fid)
            for p in page_posts:
                if p["id"] not in seen_ids:
                    seen_ids.add(p["id"])
                    posts.append(p)
            print(f"{len(page_posts)} 条")

        # GPU 标签
        for p in posts:
            tag_post(p)

        # 抓取热门帖子正文（回复>3的帖子更可能有痛点讨论）
        hot_posts = [p for p in posts if p.get("replies", 0) > 3][:30]
        if hot_posts:
            print(f"    抓取 {len(hot_posts)} 条热帖正文...", end=" ")
            fetched = 0
            for p in hot_posts:
                main_content, comments = self._fetch_thread_content(p["id"].replace("nga_", ""))
                if main_content:
                    p["content"] = main_content
                    fetched += 1
                if comments:
                    p["comments"] = comments[:2000]
            print(f"成功 {fetched} 条")

        return posts

    def _fetch_forum(self, fid: int, pages: int = 2) -> list[dict]:
        """抓取指定板块的帖子列表"""
        posts = []

        for page in range(1, pages + 1):
            try:
                url = f"https://bbs.nga.cn/thread.php?fid={fid}&page={page}&__output=11"
                resp = self.safe_request(url,
                                         referer="https://bbs.nga.cn/",
                                         delay=(2.0, 4.0),
                                         extra_headers={"Accept": "application/json, text/plain, */*"},
                                         cookies=self.cookies)
                if not resp:
                    continue
                # NGA 返回的可能是 JSONP 或纯 JSON
                text = resp.text.strip()
                # 去掉 JSONP 包装
                if text.startswith("window.script_muti_get_var_store"):
                    text = re.sub(r'^window\.script_muti_get_var_store\s*=\s*', '', text)
                    text = text.rstrip(';')

                data = json.loads(text)
                result = data.get("data", data)
                thread_list = result.get("__T", {})

                # __T 可能是 dict 或 list，统一处理
                if isinstance(thread_list, dict):
                    items = thread_list.values()
                elif isinstance(thread_list, list):
                    items = thread_list
                else:
                    items = []

                for thread in items:
                    if not isinstance(thread, dict):
                        continue
                    post = self._parse_thread(thread, fid)
                    if post:
                        posts.append(post)

            except json.JSONDecodeError as e:
                print(f"[!] NGA JSON 解析失败(fid={fid},page={page}): {e}")
            except Exception as e:
                print(f"[!] NGA 请求失败(fid={fid},page={page}): {e}")

        return posts

    def _parse_thread(self, thread: dict, fid: int) -> dict | None:
        """解析单个帖子"""
        tid = thread.get("tid", 0)
        if not tid:
            return None

        title = thread.get("subject", "")
        # 去除 HTML 标签
        title = re.sub(r'<[^>]+>', '', title).strip()
        if not title:
            return None

        # 时间过滤
        postdate = thread.get("postdate", 0)
        if isinstance(postdate, str):
            try:
                post_time = datetime.strptime(postdate, "%Y-%m-%d %H:%M")
            except ValueError:
                post_time = datetime.now()
        else:
            post_time = datetime.fromtimestamp(postdate) if postdate > 0 else datetime.now()

        if post_time < self.MIN_DATE:
            return None

        replies = thread.get("replies", 0)
        # NGA 没有 likes，用 recommend 代替
        recommend = thread.get("recommend", 0)

        return {
            "id": f"nga_{tid}",
            "source": "nga",
            "_source": "nga",
            "_forum_id": fid,
            "title": title,
            "content": title,  # NGA 列表页没有正文，只有标题
            "url": f"https://bbs.nga.cn/read.php?tid={tid}",
            "author_hash": self.hash_author(str(thread.get("authorid", "anon"))),
            "replies": replies,
            "likes": recommend,
            "language": "zh-CN",
            "timestamp": post_time.isoformat(),
        }

    def _fetch_thread_content(self, tid: str) -> tuple[str | None, str | None]:
        """抓取帖子首楼正文 + Top 回复，分离返回 (content, comments)"""
        try:
            url = f"https://bbs.nga.cn/read.php?tid={tid}&page=1&__output=11"
            resp = self.safe_request(url,
                                     referer=f"https://bbs.nga.cn/read.php?tid={tid}",
                                     delay=(1.0, 2.5),
                                     cookies=self.cookies)
            if not resp:
                return None, None
            text = resp.text.strip()
            if text.startswith("window.script_muti_get_var_store"):
                text = re.sub(r'^window\.script_muti_get_var_store\s*=\s*', '', text)
                text = text.rstrip(';')

            data = json.loads(text)
            result = data.get("data", data)
            rows = result.get("__R", {})
            if isinstance(rows, dict):
                items = list(rows.values())
            elif isinstance(rows, list):
                items = rows
            else:
                return None, None

            # 首楼正文
            main_content = None
            if items and isinstance(items[0], dict):
                content = items[0].get("content", "")
                content = re.sub(r'<[^>]+>', ' ', content)
                content = re.sub(r'\[.*?\]', '', content)
                content = re.sub(r'\s+', ' ', content).strip()
                if content:
                    main_content = content[:500]

            # Top 回复（2-6 楼，最多 5 条）— 独立存储
            reply_parts = []
            for item in items[1:6]:
                if not isinstance(item, dict):
                    continue
                reply = item.get("content", "")
                reply = re.sub(r'<[^>]+>', ' ', reply)
                reply = re.sub(r'\[.*?\]', '', reply)
                reply = re.sub(r'\s+', ' ', reply).strip()
                if reply and len(reply) > 10:
                    reply_parts.append(reply[:200])

            comments = "\n".join(reply_parts) if reply_parts else None
            return main_content, comments
        except Exception:
            pass
        return None, None
