"""GPU-Insight Reddit 爬虫 v4 — 统一 safe_request + 域名降级"""

from datetime import datetime
from .base_scraper import BaseScraper
from src.utils.gpu_tagger import tag_post
from src.utils.keywords import get_reddit_queries


class RedditScraper(BaseScraper):
    """Reddit 爬虫 — /hot + /new + /search 三端点"""

    def __init__(self, config: dict):
        super().__init__("reddit", config)
        self.subreddits = self.source_config.get("subreddits", ["nvidia", "amd", "hardware"])
        # 从配置动态加载搜索关键词
        self.search_queries = get_reddit_queries()

    def fetch_posts(self, last_id: str = None) -> list[dict]:
        """三端点抓取 + 热帖评论"""
        posts = []
        seen_ids = set()

        for sub in self.subreddits:
            for ep in ["hot", "new"]:
                for p in self._fetch_reddit(sub, ep, limit=25):
                    if p["id"] not in seen_ids:
                        seen_ids.add(p["id"])
                        posts.append(p)

            for query in self.search_queries:
                qs = f"search.json?q={query}&restrict_sr=on&sort=relevance&t=week&limit=10"
                for p in self._fetch_reddit(sub, qs):
                    if p["id"] not in seen_ids:
                        seen_ids.add(p["id"])
                        posts.append(p)

        # 信号分数排序
        for p in posts:
            p["_signal_score"] = self._calc_signal_score(p)
        posts.sort(key=lambda x: x["_signal_score"], reverse=True)

        # 热帖评论（回复>10，最多 15 条）— 独立存储到 comments 字段
        hot_posts = [p for p in posts if p.get("replies", 0) > 10][:15]
        if hot_posts:
            print(f"    抓取 {len(hot_posts)} 条热帖评论...", end=" ")
            fetched = 0
            for p in hot_posts:
                comments = self._fetch_comments(p)
                if comments:
                    p["comments"] = comments[:2000]
                    fetched += 1
            print(f"成功 {fetched} 条")

        return posts

    def _fetch_reddit(self, subreddit: str, path: str, limit: int = None) -> list[dict]:
        """统一 Reddit 请求 — www → old.reddit 域名降级，单次尝试"""
        if limit and "?" not in path:
            path = f"{path}.json?limit={limit}"

        urls = [
            f"https://www.reddit.com/r/{subreddit}/{path}",
            f"https://old.reddit.com/r/{subreddit}/{path}",
        ]

        for url in urls:
            # max_retries=1 避免重复重试（域名降级已经是重试机制）
            resp = self.safe_request(url, referer="https://www.reddit.com/",
                                     delay=(2.0, 3.5), timeout=15, max_retries=1)
            if resp and resp.status_code == 200:
                try:
                    return self._parse_listing(resp.json(), subreddit)
                except Exception:
                    pass
            elif resp and resp.status_code == 429:
                return []
        return []

    def _fetch_comments(self, post: dict, max_comments: int = 5) -> str | None:
        """抓取帖子 Top N 评论"""
        post_id = post["id"].replace("reddit_", "")
        urls = [
            f"https://www.reddit.com/comments/{post_id}.json?sort=top&limit={max_comments}",
            f"https://old.reddit.com/comments/{post_id}.json?sort=top&limit={max_comments}",
        ]

        for url in urls:
            resp = self.safe_request(url, referer="https://www.reddit.com/",
                                     delay=(0.5, 1.5), timeout=10, max_retries=1)
            if not resp or resp.status_code != 200:
                continue
            try:
                data = resp.json()
                if not isinstance(data, list) or len(data) < 2:
                    return None

                texts = []
                for c in data[1].get("data", {}).get("children", [])[:max_comments]:
                    cd = c.get("data", {})
                    body = cd.get("body", "")
                    score = cd.get("score", 0)
                    if body and body not in ("[deleted]", "[removed]"):
                        texts.append(f"[+{score}] {body[:200]}")
                return "\n".join(texts) if texts else None
            except Exception:
                continue
        return None

    def _parse_listing(self, data: dict, subreddit: str) -> list[dict]:
        """解析 Reddit JSON listing"""
        posts = []
        for child in data.get("data", {}).get("children", []):
            pd = child.get("data", {})
            post_id = pd.get("id", "")
            title = pd.get("title", "")
            content = pd.get("selftext", "")[:2000]

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
            tag_post(posts[-1])
        return posts

    @staticmethod
    def _calc_signal_score(post: dict) -> float:
        """信号分数排序公式"""
        replies = min(post.get("replies", 0), 500)
        likes = min(post.get("likes", 0), 5000)
        has_question = 1.0 if "?" in post.get("title", "") else 0.0
        has_negative = 1.0 if any(w in post.get("title", "").lower()
            for w in ["problem", "issue", "crash", "bug", "broken", "bad",
                       "worst", "hate", "disappointed", "regret", "overheat",
                       "loud", "noise", "expensive", "rip", "dead", "fail"]) else 0.0
        content_len = min(len(post.get("content", "")), 2000)

        return round(
            replies * 0.25 + likes * 0.15 + has_question * 5.0
            + has_negative * 10.0 + (content_len / 500) * 0.05, 2
        )
