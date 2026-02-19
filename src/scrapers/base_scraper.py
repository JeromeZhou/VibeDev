"""GPU-Insight 爬虫基类 — 统一反爬基础设施"""

import json
import time
import random
import hashlib
import ssl
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

import httpx

# 全局 UA 池 — 真实浏览器指纹，所有爬虫共享
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 Edg/133.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
]


class BaseScraper(ABC):
    """所有爬虫的基类 — 提供统一反爬、限流处理、SSL 容错"""

    # 只抓 2025-01-01 之后的帖子
    MIN_DATE = datetime(2025, 1, 1)

    def __init__(self, source_name: str, config: dict):
        self.source_name = source_name
        self.config = config
        self.source_config = config.get("sources", {}).get(source_name, {})
        self.raw_path = Path(config.get("paths", {}).get("raw_data", "data/raw")) / source_name
        self.raw_path.mkdir(parents=True, exist_ok=True)
        self._last_id_file = self.raw_path / ".last_id"
        self._ua = random.choice(_USER_AGENTS)

    @abstractmethod
    def fetch_posts(self, last_id: str = None) -> list[dict]:
        """抓取新帖子，子类必须实现"""
        pass

    def scrape(self) -> list[dict]:
        """执行增量抓取"""
        last_id = self._load_last_id()
        try:
            posts = self.fetch_posts(last_id)
            if posts:
                self._save_raw(posts)
                newest_id = posts[0].get("id", "")
                if newest_id:
                    self._save_last_id(newest_id)
            return posts
        except Exception as e:
            print(f"  [!] {self.source_name} 抓取失败: {e}")
            return []

    def _save_raw(self, posts: list[dict]):
        """保存原始数据到 JSONL"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        output_file = self.raw_path / f"{date_str}.jsonl"
        with open(output_file, "a", encoding="utf-8") as f:
            for post in posts:
                post["_scraped_at"] = datetime.now().isoformat()
                post["_source"] = self.source_name
                f.write(json.dumps(post, ensure_ascii=False) + "\n")

    def _load_last_id(self) -> str | None:
        if self._last_id_file.exists():
            return self._last_id_file.read_text().strip()
        return None

    def _save_last_id(self, last_id: str):
        self._last_id_file.write_text(last_id)

    @staticmethod
    def random_delay(min_sec: float = 2.0, max_sec: float = 5.0):
        """随机延迟 + ±20% 抖动，防反爬"""
        base = random.uniform(min_sec, max_sec)
        jitter = base * random.uniform(-0.2, 0.2)
        time.sleep(max(0.5, base + jitter))

    @staticmethod
    def hash_author(author_id: str) -> str:
        """作者 ID 哈希，保护隐私"""
        return hashlib.sha256(author_id.encode()).hexdigest()[:16]

    def get_headers(self, referer: str = None, extra: dict = None) -> dict:
        """生成标准浏览器请求头 — 所有爬虫统一使用"""
        headers = {
            "User-Agent": self._ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        if referer:
            headers["Referer"] = referer
        if extra:
            headers.update(extra)
        return headers

    def safe_request(self, url: str, referer: str = None, timeout: int = 30,
                     delay: tuple = (2.0, 4.5), extra_headers: dict = None,
                     cookies: dict = None, max_retries: int = 3,
                     verify_ssl: bool = None) -> httpx.Response | None:
        """统一安全请求 — 自动处理 403/429/SSL 错误 + 指数退避

        Args:
            verify_ssl: True/False 强制指定，None 则自动（首次 True，重试 False）

        Returns:
            httpx.Response on success, None on failure (已打印错误日志)
        """
        headers = self.get_headers(referer=referer, extra=extra_headers)

        for attempt in range(max_retries):
            if verify_ssl is not None:
                verify = verify_ssl
            else:
                verify = attempt == 0  # 第二次尝试禁用 SSL 验证
            try:
                self.random_delay(*delay)
                # 显式设置 connect/read/write 超时，避免 Windows 下连接挂起
                to = httpx.Timeout(timeout, connect=min(timeout, 10))
                resp = httpx.get(url, headers=headers, timeout=to,
                                 follow_redirects=True, verify=verify,
                                 cookies=cookies)

                if resp.status_code == 429:
                    # 指数退避: 30s → 60s → 120s，加随机抖动
                    base_wait = int(resp.headers.get("Retry-After", 30))
                    backoff = min(base_wait * (2 ** attempt), 120)
                    jitter = random.uniform(0, backoff * 0.3)
                    wait = backoff + jitter
                    print(f"    [!] {self.source_name} 限流(429)，退避 {wait:.0f}s (attempt {attempt+1})...")
                    time.sleep(wait)
                    continue

                if resp.status_code == 412:
                    # Bilibili 风控等，不重试
                    return resp

                if resp.status_code == 403:
                    if attempt < max_retries - 1:
                        # 退避后重试
                        backoff = 5 * (2 ** attempt) + random.uniform(0, 3)
                        time.sleep(backoff)
                        continue
                    print(f"    [!] {self.source_name} 被拒(403): {url[:80]}")
                    return None

                resp.raise_for_status()
                return resp

            except (httpx.ReadError, ssl.SSLError):
                if attempt < max_retries - 1:
                    time.sleep(3 * (attempt + 1))
                    continue  # SSL 降级重试
                print(f"    [!] {self.source_name} SSL 错误: {url[:80]}")
                return None
            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))
                    continue
                print(f"    [!] {self.source_name} 超时: {url[:80]}")
                return None
            except Exception as e:
                print(f"    [!] {self.source_name} 请求失败: {e}")
                return None

        return None
