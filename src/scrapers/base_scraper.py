"""GPU-Insight 爬虫基类"""

import json
import time
import random
import hashlib
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path


class BaseScraper(ABC):
    """所有爬虫的基类"""

    # 只抓 2025-01-01 之后的帖子
    MIN_DATE = datetime(2025, 1, 1)

    def __init__(self, source_name: str, config: dict):
        self.source_name = source_name
        self.config = config
        self.source_config = config.get("sources", {}).get(source_name, {})
        self.raw_path = Path(config.get("paths", {}).get("raw_data", "data/raw")) / source_name
        self.raw_path.mkdir(parents=True, exist_ok=True)
        self._last_id_file = self.raw_path / ".last_id"

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
        """随机延迟，防反爬"""
        time.sleep(random.uniform(min_sec, max_sec))

    @staticmethod
    def hash_author(author_id: str) -> str:
        """作者 ID 哈希，保护隐私"""
        return hashlib.sha256(author_id.encode()).hexdigest()[:16]
