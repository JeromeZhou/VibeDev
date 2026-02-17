"""GPU-Insight Reddit 爬虫 v3 — 三端点并行 + 信号分数 + GPU 产品标签 + 403 容错"""

import os
import random
from datetime import datetime
from .base_scraper import BaseScraper
from src.utils.gpu_tagger import tag_post

# 真实浏览器 UA 池，避免被 Reddit 403
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) Gecko/20100101 Firefox/134.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
]


class RedditScraper(BaseScraper):
    """Reddit 爬虫 — /hot + /new + /search 三端点并行"""

    def __init__(self, config: dict):
        super().__init__("reddit", config)
        self.subreddits = self.source_config.get("subreddits", ["nvidia", "amd", "hardware"])
        self._ua = random.choice(_USER_AGENTS)

    def fetch_posts(self, last_id: str = None) -> list[dict]:
        """三端点并行抓取 + 热帖评论"""
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

        # 抓取热帖 Top 评论（回复>10 的帖子，最多 20 条）
        hot_posts = [p for p in posts if p.get("replies", 0) > 10][:20]
        if hot_posts:
            print(f"    抓取 {len(hot_posts)} 条热帖评论...", end=" ")
            fetched = 0
            for p in hot_posts:
                comments = self._fetch_top_comments(p)
                if comments:
                    p["content"] = (p.get("content", "") + "\n\n--- Top Comments ---\n" + comments)[:3000]
                    fetched += 1
            print(f"成功 {fetched} 条")

        return posts

    def _fetch_endpoint(self, subreddit: str, endpoint: str, limit: int = 25) -> list[dict]:
        """抓取指定端点 — 三级降级：www → old.reddit → verify=False"""
        import httpx
        import ssl

        headers = {
            "User-Agent": self._ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        # 尝试的 URL 列表：www.reddit.com → old.reddit.com
        urls = [
            f"https://www.reddit.com/r/{subreddit}/{endpoint}.json?limit={limit}",
            f"https://old.reddit.com/r/{subreddit}/{endpoint}.json?limit={limit}",
        ]

        for i, url in enumerate(urls):
            domain = "old.reddit" if "old.reddit" in url else "www.reddit"
            # 尝试标准 HTTPS
            try:
                self.random_delay(2.0, 4.5)
                resp = httpx.get(url, headers=headers, timeout=30, follow_redirects=True)
                resp.raise_for_status()
                if i > 0:
                    print(f"    [√] r/{subreddit}/{endpoint} via {domain}")
                return self._parse_listing(resp.json(), subreddit)
            except (httpx.ReadError, ssl.SSLError):
                # SSL 错误 → 同域 verify=False 重试
                try:
                    self.random_delay(2.0, 4.0)
                    resp = httpx.get(url, headers=headers, timeout=30, follow_redirects=True, verify=False)
                    resp.raise_for_status()
                    print(f"    [√] r/{subreddit}/{endpoint} via {domain} (no-ssl)")
                    return self._parse_listing(resp.json(), subreddit)
                except Exception:
                    pass
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 403 and i < len(urls) - 1:
                    continue  # 403 → 尝试下一个域名
                if e.response.status_code == 429:
                    print(f"    [!] r/{subreddit}/{endpoint} 限流(429)，跳过")
                    return []
            except Exception:
                if i < len(urls) - 1:
                    continue

        print(f"    [!] r/{subreddit}/{endpoint} 全部失败")
        return []

    def _fetch_search(self, subreddit: str, query: str, limit: int = 10) -> list[dict]:
        """搜索端点 — 带域名降级 + SSL 容错"""
        import httpx
        import ssl

        headers = {
            "User-Agent": self._ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        qs = f"search.json?q={query}&restrict_sr=on&sort=relevance&t=week&limit={limit}"
        urls = [
            f"https://www.reddit.com/r/{subreddit}/{qs}",
            f"https://old.reddit.com/r/{subreddit}/{qs}",
        ]

        for i, url in enumerate(urls):
            try:
                self.random_delay(1.5, 3.5)
                resp = httpx.get(url, headers=headers, timeout=30, follow_redirects=True)
                resp.raise_for_status()
                return self._parse_listing(resp.json(), subreddit)
            except (httpx.ReadError, ssl.SSLError):
                try:
                    self.random_delay(2.0, 4.0)
                    resp = httpx.get(url, headers=headers, timeout=30, follow_redirects=True, verify=False)
                    resp.raise_for_status()
                    return self._parse_listing(resp.json(), subreddit)
                except Exception:
                    pass
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 403 and i < len(urls) - 1:
                    continue
            except Exception:
                if i < len(urls) - 1:
                    continue
        return []

    def _fetch_top_comments(self, post: dict, max_comments: int = 5) -> str | None:
        """抓取帖子 Top N 评论（按 score 排序）"""
        import httpx

        post_id = post["id"].replace("reddit_", "")
        url = f"https://www.reddit.com/comments/{post_id}.json?sort=top&limit={max_comments}"
        headers = self.get_headers(referer=f"https://www.reddit.com/")

        try:
            self.random_delay(1.0, 2.5)
            resp = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
            if resp.status_code != 200:
                # 降级到 old.reddit
                url2 = f"https://old.reddit.com/comments/{post_id}.json?sort=top&limit={max_comments}"
                resp = httpx.get(url2, headers=headers, timeout=15, follow_redirects=True, verify=False)
            resp.raise_for_status()
            data = resp.json()

            # Reddit comments JSON: [post_listing, comments_listing]
            if not isinstance(data, list) or len(data) < 2:
                return None

            comments_data = data[1].get("data", {}).get("children", [])
            texts = []
            for c in comments_data[:max_comments]:
                cd = c.get("data", {})
                body = cd.get("body", "")
                score = cd.get("score", 0)
                if body and body != "[deleted]" and body != "[removed]":
                    texts.append(f"[+{score}] {body[:200]}")

            return "\n".join(texts) if texts else None
        except Exception:
            return None

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
