"""GPU-Insight Reddit 爬虫 v2 — 三端点并行 + 信号分数 + GPU 产品标签"""

import os
from datetime import datetime
from .base_scraper import BaseScraper
from src.utils.gpu_tagger import tag_post


class RedditScraper(BaseScraper):
    """Reddit 爬虫 — /hot + /new + /search 三端点并行"""

    def __init__(self, config: dict):
        super().__init__("reddit", config)
        self.subreddits = self.source_config.get("subreddits", ["nvidia", "amd", "hardware"])

    def fetch_posts(self, last_id: str = None) -> list[dict]:
        """三端点并行抓取"""
        posts = []
        seen_ids = set()

        for sub in self.subreddits:
            # 端点 1: /hot（社区验证过的热门讨论）
            hot = self._fetch_endpoint(sub, "hot", limit=25)
            for p in hot:
                if p["id"] not in seen_ids:
                    seen_ids.add(p["id"])
                    posts.append(p)

            # 端点 2: /new（发现新兴痛点）
            new = self._fetch_endpoint(sub, "new", limit=25)
            for p in new:
                if p["id"] not in seen_ids:
                    seen_ids.add(p["id"])
                    posts.append(p)

            # 端点 3: /search（主动搜索痛点关键词）
            for query in ["problem", "issue", "crash", "overheat", "expensive", "broken", "disappointed"]:
                search = self._fetch_search(sub, query, limit=10)
                for p in search:
                    if p["id"] not in seen_ids:
                        seen_ids.add(p["id"])
                        posts.append(p)

        # 计算信号分数并排序
        for p in posts:
            p["_signal_score"] = self._calc_signal_score(p)
        posts.sort(key=lambda x: x["_signal_score"], reverse=True)

        return posts

    def _fetch_endpoint(self, subreddit: str, endpoint: str, limit: int = 25) -> list[dict]:
        """抓取指定端点"""
        try:
            import httpx
            self.random_delay(1.5, 3.0)
            url = f"https://www.reddit.com/r/{subreddit}/{endpoint}.json?limit={limit}"
            headers = {"User-Agent": "GPU-Insight/1.0 (research bot)"}
            resp = httpx.get(url, headers=headers, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            return self._parse_listing(resp.json(), subreddit)
        except Exception as e:
            print(f"    [!] r/{subreddit}/{endpoint} 失败: {e}")
            return []

    def _fetch_search(self, subreddit: str, query: str, limit: int = 10) -> list[dict]:
        """搜索端点"""
        try:
            import httpx
            self.random_delay(1.5, 3.0)
            url = f"https://www.reddit.com/r/{subreddit}/search.json?q={query}&restrict_sr=on&sort=relevance&t=week&limit={limit}"
            headers = {"User-Agent": "GPU-Insight/1.0 (research bot)"}
            resp = httpx.get(url, headers=headers, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            return self._parse_listing(resp.json(), subreddit)
        except Exception as e:
            return []

    def _parse_listing(self, data: dict, subreddit: str) -> list[dict]:
        """解析 Reddit JSON listing"""
        posts = []
        for child in data.get("data", {}).get("children", []):
            pd = child.get("data", {})
            post_id = pd.get("id", "")
            title = pd.get("title", "")
            content = pd.get("selftext", "")[:2000]

            # 时间过滤：跳过 MIN_DATE 之前的帖子
            created_utc = pd.get("created_utc", 0)
            post_time = datetime.fromtimestamp(created_utc)
            if post_time < self.MIN_DATE:
                continue

            posts.append({
                "id": f"reddit_{post_id}",
                "source": "reddit",
                "_source": "reddit",
                "_subreddit": subreddit,
                "title": title,
                "content": content if content else title,
                "url": f"https://reddit.com{pd.get('permalink', '')}",
                "author_hash": self.hash_author(pd.get("author", "anon")),
                "replies": pd.get("num_comments", 0),
                "likes": pd.get("score", 0),
                "upvote_ratio": pd.get("upvote_ratio", 0.5),
                "language": "en",
                "timestamp": post_time.isoformat(),
            })
            # L0 本地 GPU 产品标签
            tag_post(posts[-1])
        return posts

    @staticmethod
    def _calc_signal_score(post: dict) -> float:
        """计算信号分数 — Architect 设计的排序公式"""
        replies = min(post.get("replies", 0), 500)  # 封顶防异常
        likes = min(post.get("likes", 0), 5000)
        title_len = len(post.get("title", ""))
        has_question = 1.0 if "?" in post.get("title", "") else 0.0
        has_negative = 1.0 if any(w in post.get("title", "").lower()
            for w in ["problem", "issue", "crash", "bug", "broken", "bad",
                       "worst", "hate", "disappointed", "regret", "overheat",
                       "loud", "noise", "expensive", "rip", "dead", "fail"]) else 0.0
        content_len = min(len(post.get("content", "")), 2000)

        score = (
            replies * 0.25
            + likes * 0.15
            + (title_len / 100) * 0.05
            + has_question * 5.0
            + has_negative * 10.0
            + (content_len / 500) * 0.05
        )
        return round(score, 2)
