"""GPU-Insight Bilibili 爬虫 — 搜索 API 抓取显卡相关视频讨论"""

import re
import random
import uuid
from datetime import datetime
from urllib.parse import quote
from .base_scraper import BaseScraper
from src.utils.gpu_tagger import tag_post
from src.utils.keywords import get_bilibili_keywords


def _generate_buvid3() -> str:
    """生成 Bilibili buvid3 cookie — 模拟浏览器首次访问"""
    # buvid3 格式: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx + infoc 后缀
    return str(uuid.uuid4()).upper() + "infoc"


def _generate_b_nut() -> str:
    """生成 b_nut cookie — 13位时间戳"""
    import time
    return str(int(time.time() * 1000))[:13]


class BilibiliScraper(BaseScraper):
    """Bilibili 爬虫 — 通过搜索 API 抓取显卡相关视频"""

    def __init__(self, config: dict):
        super().__init__("bilibili", config)
        # 从配置动态加载关键词，限制数量减少请求
        self.search_keywords = get_bilibili_keywords(max_count=5)
        self._rate_limited = False  # 412 限流标记
        # 生成会话级 cookies — 模拟真实浏览器
        self._session_cookies = {
            "buvid3": _generate_buvid3(),
            "b_nut": _generate_b_nut(),
            "i-wanna-go-back": "-1",
            "b_ut": "7",
            "CURRENT_FNVAL": "4048",
        }

    def _bili_headers(self) -> dict:
        """Bilibili 专用请求头 — 模拟浏览器 XHR"""
        return {
            "Origin": "https://www.bilibili.com",
            "X-Requested-With": "XMLHttpRequest",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
        }

    def fetch_posts(self, last_id: str = None) -> list[dict]:
        """搜索 Bilibili 显卡相关视频"""
        posts = []
        seen_ids = set()
        self._rate_limited = False

        # 随机打乱关键词顺序，避免每次相同请求模式
        keywords = list(self.search_keywords)
        random.shuffle(keywords)

        for i, keyword in enumerate(keywords):
            try:
                encoded_kw = quote(keyword)
                full_url = (
                    f"https://api.bilibili.com/x/web-interface/search/type"
                    f"?search_type=video&keyword={encoded_kw}"
                    f"&order=pubdate&duration=0&page=1&pagesize=20"
                )
                # 关键词间递增延迟: 4-7s, 5-8s, 6-9s...
                kw_delay = (4.0 + i * 1.0, 7.0 + i * 1.0)
                resp = self.safe_request(
                    full_url,
                    referer=f"https://search.bilibili.com/all?keyword={encoded_kw}",
                    delay=kw_delay,
                    extra_headers=self._bili_headers(),
                    cookies=self._session_cookies,
                )

                # 412 限流 — 立即停止
                if resp and resp.status_code == 412:
                    print(f"    [!] Bilibili 被限流(412)，停止搜索")
                    self._rate_limited = True
                    break
                if not resp or resp.status_code != 200:
                    continue

                data = resp.json()
                if data.get("code") != 0:
                    if data.get("code") == -412:
                        print(f"    [!] Bilibili 被限流(-412)，停止搜索")
                        self._rate_limited = True
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

        # 热门视频评论区抓取（被限流时跳过，限制数量避免耗时过长）
        if self._rate_limited:
            print(f"    跳过评论抓取（限流中）")
        else:
            hot_posts = [p for p in posts if p.get("replies", 0) > 5][:8]  # 最多8条，避免耗时
            if hot_posts:
                print(f"    抓取 {len(hot_posts)} 条热门视频评论...", end=" ")
                fetched = 0
                import time as _time
                comment_start = _time.time()
                for p in hot_posts:
                    # 总耗时超过 120s 则停止
                    if _time.time() - comment_start > 120:
                        print(f"(超时截断)", end=" ")
                        break
                    comments = self._fetch_comments(p)
                    if comments:
                        p["comments"] = comments[:2000]
                        fetched += 1
                    elif self._rate_limited:
                        break  # 评论 API 也被限流，停止
                print(f"成功 {fetched} 条")

        return posts

    def _fetch_comments(self, post: dict, max_comments: int = 10) -> str | None:
        """抓取视频 Top 评论（按热度排序）"""
        # 从 bvid 获取 aid（Bilibili 评论 API 需要 aid）
        bvid = post["id"].replace("bili_", "")
        try:
            # 先用 bvid 查 aid
            info_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
            resp = self.safe_request(
                info_url,
                referer=f"https://www.bilibili.com/video/{bvid}",
                delay=(1.5, 3.0),
                max_retries=1,
                extra_headers=self._bili_headers(),
                cookies=self._session_cookies,
                timeout=15,
            )
            if resp and resp.status_code == 412:
                self._rate_limited = True
                return None
            if not resp or resp.status_code != 200:
                return None
            info_data = resp.json()
            if info_data.get("code") != 0:
                return None
            aid = info_data.get("data", {}).get("aid", 0)
            if not aid:
                return None

            # 抓取评论（type=1 表示视频，sort=1 按热度）
            reply_url = (
                f"https://api.bilibili.com/x/v2/reply/main"
                f"?type=1&oid={aid}&mode=3&ps={max_comments}"
            )
            resp = self.safe_request(
                reply_url,
                referer=f"https://www.bilibili.com/video/{bvid}",
                delay=(1.5, 3.0),
                max_retries=1,
                extra_headers=self._bili_headers(),
                cookies=self._session_cookies,
                timeout=15,
            )
            if resp and resp.status_code == 412:
                self._rate_limited = True
                return None
            if not resp or resp.status_code != 200:
                return None

            reply_data = resp.json()
            if reply_data.get("code") != 0:
                return None

            replies = reply_data.get("data", {}).get("replies", [])
            if not replies:
                return None

            texts = []
            for r in replies[:max_comments]:
                content = r.get("content", {}).get("message", "")
                like_count = r.get("like", 0)
                if content and len(content) > 5:
                    texts.append(f"[+{like_count}] {content[:200]}")

            return "\n".join(texts) if texts else None
        except Exception:
            return None

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
