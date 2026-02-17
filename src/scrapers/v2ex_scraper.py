"""GPU-Insight V2EX 爬虫 — 官方 API"""

import re
from datetime import datetime
from .base_scraper import BaseScraper
from src.utils.gpu_tagger import tag_post


class V2EXScraper(BaseScraper):
    """V2EX 爬虫 — 通过官方 API 抓取硬件相关话题"""

    # GPU/硬件相关节点（gpu 节点不存在，已移除）
    NODES = ["hardware", "computer", "apple", "gamer"]
    # 搜索关键词（补充节点外的显卡讨论）
    SEARCH_KEYWORDS = ["显卡", "GPU", "RTX", "RX", "NVIDIA", "AMD"]

    def __init__(self, config: dict):
        super().__init__("v2ex", config)

    def fetch_posts(self, last_id: str = None) -> list[dict]:
        """抓取 V2EX 硬件相关帖子"""
        import httpx

        posts = []
        seen_ids = set()

        # 1. 按节点抓取
        for node in self.NODES:
            try:
                url = f"https://www.v2ex.com/api/topics/show.json?node_name={node}"
                resp = self.safe_request(url, referer="https://www.v2ex.com/",
                                         delay=(1.5, 3.0),
                                         extra_headers={"Accept": "application/json"})
                if resp and resp.status_code == 200:
                    for item in resp.json():
                        post = self._parse_topic(item)
                        if post and post["id"] not in seen_ids:
                            seen_ids.add(post["id"])
                            posts.append(post)
                elif resp and resp.status_code == 403:
                    print(f"    [!] V2EX 被限流(403)，跳过后续节点")
                    break  # 403 限流才跳过
            except Exception as e:
                print(f"    [!] V2EX 节点 {node} 失败: {e}")

        # 2. 热门话题中筛选显卡相关
        try:
            url = "https://www.v2ex.com/api/topics/hot.json"
            resp = self.safe_request(url, referer="https://www.v2ex.com/",
                                     delay=(2.0, 4.0),
                                     extra_headers={"Accept": "application/json"})
            if resp and resp.status_code == 200:
                for item in resp.json():
                    title = item.get("title", "")
                    content = item.get("content", "")
                    text = f"{title} {content}".lower()
                    if any(kw.lower() in text for kw in self.SEARCH_KEYWORDS):
                        post = self._parse_topic(item)
                        if post and post["id"] not in seen_ids:
                            seen_ids.add(post["id"])
                            posts.append(post)
        except Exception as e:
            print(f"    [!] V2EX 热门搜索失败: {e}")

        # GPU 标签
        for p in posts:
            tag_post(p)

        return posts

    def _parse_topic(self, item: dict) -> dict | None:
        """解析 V2EX topic JSON"""
        topic_id = item.get("id", 0)
        if not topic_id:
            return None

        title = item.get("title", "").strip()
        if not title:
            return None

        content = item.get("content", "") or ""
        content = re.sub(r'<[^>]+>', ' ', content)  # 去 HTML
        content = re.sub(r'\s+', ' ', content).strip()

        # 时间过滤
        created = item.get("created", 0)
        try:
            post_time = datetime.fromtimestamp(created) if created > 0 else datetime.now()
        except (OSError, ValueError):
            post_time = datetime.now()

        if post_time < self.MIN_DATE:
            return None

        replies = item.get("replies", 0)
        member = item.get("member", {})
        author = member.get("username", "anon") if isinstance(member, dict) else "anon"

        return {
            "id": f"v2ex_{topic_id}",
            "source": "v2ex",
            "_source": "v2ex",
            "_node": item.get("node", {}).get("name", "") if isinstance(item.get("node"), dict) else "",
            "title": title,
            "content": content[:2000] if content else title,
            "url": item.get("url", f"https://www.v2ex.com/t/{topic_id}"),
            "author_hash": self.hash_author(author),
            "replies": replies,
            "likes": 0,  # V2EX API 不返回收藏数
            "language": "zh-CN",
            "timestamp": post_time.isoformat(),
        }
