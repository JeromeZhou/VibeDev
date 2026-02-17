"""GPU-Insight Bilibili 爬虫 — 搜索 API 抓取显卡相关视频讨论"""

import re
from datetime import datetime
from .base_scraper import BaseScraper
from src.utils.gpu_tagger import tag_post


class BilibiliScraper(BaseScraper):
    """Bilibili 爬虫 — 通过搜索 API 抓取显卡相关视频"""

    SEARCH_KEYWORDS = [
        "显卡 问题", "GPU 翻车", "显卡 散热", "显卡 噪音",
        "RTX 5090", "RTX 5080", "RTX 5070", "RX 9070",
        "显卡 驱动", "显卡 黑屏", "显卡 崩溃",
    ]

    def __init__(self, config: dict):
        super().__init__("bilibili", config)

    def fetch_posts(self, last_id: str = None) -> list[dict]:
        """搜索 Bilibili 显卡相关视频"""
        posts = []
        seen_ids = set()

        for keyword in self.SEARCH_KEYWORDS:
            try:
                url = "https://api.bilibili.com/x/web-interface/search/type"
                params = {
                    "search_type": "video",
                    "keyword": keyword,
                    "order": "pubdate",
                    "duration": 0,
                    "page": 1,
                    "pagesize": 20,
                }
                # 手动拼 URL 以便 safe_request 使用
                qs = "&".join(f"{k}={v}" for k, v in params.items())
                full_url = f"{url}?{qs}"
                resp = self.safe_request(full_url, referer="https://www.bilibili.com",
                                         delay=(2.5, 4.5))
                if not resp or resp.status_code != 200:
                    continue

                data = resp.json()
                if data.get("code") != 0:
                    if data.get("code") == -412:
                        print(f"    [!] Bilibili 被限流(-412)，停止搜索")
                        break
                    continue

                results = data.get("data", {}).get("result", [])
                if not results:
                    continue

                for item in results:
                    post = self._parse_video(item)
                    if post and post["id"] not in seen_ids:
                        seen_ids.add(post["id"])
                        posts.append(post)

            except Exception as e:
                print(f"    [!] Bilibili 搜索 '{keyword}' 失败: {e}")

        # GPU 标签
        for p in posts:
            tag_post(p)

        return posts

    def _parse_video(self, item: dict) -> dict | None:
        """解析 Bilibili 搜索结果"""
        bvid = item.get("bvid", "")
        if not bvid:
            return None

        title = item.get("title", "")
        # 去除搜索高亮标签
        title = re.sub(r'</?em[^>]*>', '', title).strip()
        if not title:
            return None

        description = item.get("description", "") or ""
        description = re.sub(r'<[^>]+>', ' ', description).strip()

        # 时间过滤
        pubdate = item.get("pubdate", 0)
        try:
            post_time = datetime.fromtimestamp(pubdate) if pubdate > 0 else datetime.now()
        except (OSError, ValueError):
            post_time = datetime.now()

        if post_time < self.MIN_DATE:
            return None

        author = item.get("author", "anon")
        # 弹幕数 + 评论数作为互动指标
        danmaku = item.get("video_review", 0) or item.get("danmaku", 0)
        review = item.get("review", 0)  # 评论数
        play = item.get("play", 0)
        like = item.get("like", 0)

        return {
            "id": f"bili_{bvid}",
            "source": "bilibili",
            "_source": "bilibili",
            "title": title,
            "content": f"{title}。{description}"[:2000] if description else title,
            "url": f"https://www.bilibili.com/video/{bvid}",
            "author_hash": self.hash_author(str(author)),
            "replies": review + danmaku,  # 评论+弹幕
            "likes": like if like else play // 100,  # 点赞，无则用播放量估算
            "language": "zh-CN",
            "timestamp": post_time.isoformat(),
        }
