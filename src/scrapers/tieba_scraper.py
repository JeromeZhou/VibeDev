"""GPU-Insight 百度贴吧爬虫 — 中文数据源替代 Chiphell"""

from datetime import datetime
from .base_scraper import BaseScraper


class TiebaScraper(BaseScraper):
    """百度贴吧爬虫 — 显卡吧、NVIDIA吧、AMD吧"""

    def __init__(self, config: dict):
        super().__init__("tieba", config)
        self.bars = ["显卡", "nvidia", "amd", "gpu"]

    def fetch_posts(self, last_id: str = None) -> list[dict]:
        """抓取贴吧帖子列表"""
        posts = []
        seen_ids = set()

        try:
            import httpx

            for bar in self.bars:
                try:
                    self.random_delay(1.5, 3.0)
                    # 贴吧移动端 API（不需要登录）
                    url = f"https://tieba.baidu.com/mo/q/m?word={bar}&lp=5024&lm=&partation_id=&footer_topic_id=&cid=0&has_url_param=0&_client_type=2"
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 Mobile Safari/537.36",
                    }
                    resp = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)

                    if resp.status_code != 200:
                        # 备用：PC 端页面
                        posts.extend(self._fetch_pc(bar, last_id, seen_ids))
                        continue

                    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    # 解析移动端 JSON
                    for thread in data.get("data", {}).get("thread_list", []):
                        tid = str(thread.get("id", ""))
                        if tid in seen_ids or (last_id and tid <= last_id):
                            continue
                        seen_ids.add(tid)

                        posts.append({
                            "id": f"tieba_{tid}",
                            "source": "tieba",
                            "_source": "tieba",
                            "_bar": bar,
                            "title": thread.get("title", ""),
                            "content": thread.get("abstract", [{}])[0].get("text", "") if thread.get("abstract") else thread.get("title", ""),
                            "url": f"https://tieba.baidu.com/p/{tid}",
                            "author_hash": self.hash_author(str(thread.get("author", {}).get("id", "anon"))),
                            "replies": thread.get("reply_num", 0),
                            "likes": thread.get("agree", {}).get("agree_num", 0) if isinstance(thread.get("agree"), dict) else 0,
                            "language": "zh-CN",
                            "timestamp": datetime.now().isoformat(),
                        })

                    print(f"    {bar}吧: {len([p for p in posts if p.get('_bar') == bar])} 条")

                except Exception as e:
                    print(f"    ⚠️ {bar}吧失败: {e}")
                    # 尝试 PC 端
                    posts.extend(self._fetch_pc(bar, last_id, seen_ids))

        except ImportError:
            print("  ⚠️ 需要安装 httpx: pip install httpx")

        return posts

    def _fetch_pc(self, bar: str, last_id: str, seen_ids: set) -> list[dict]:
        """PC 端页面抓取（备用方案）"""
        posts = []
        try:
            import httpx
            from bs4 import BeautifulSoup

            self.random_delay(1.5, 3.0)
            url = f"https://tieba.baidu.com/f?kw={bar}&ie=utf-8"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
            resp = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
            soup = BeautifulSoup(resp.text, "html.parser")

            for thread in soup.select("li.j_thread_list"):
                try:
                    data_field = thread.get("data-field", "")
                    if not data_field:
                        continue
                    import json
                    tdata = json.loads(data_field.replace("&quot;", '"'))
                    tid = str(tdata.get("id", ""))

                    if tid in seen_ids or (last_id and tid <= last_id):
                        continue
                    seen_ids.add(tid)

                    title_tag = thread.select_one("a.j_th_tit")
                    title = title_tag.get_text(strip=True) if title_tag else ""
                    content_tag = thread.select_one("div.threadlist_abs")
                    content = content_tag.get_text(strip=True) if content_tag else title

                    posts.append({
                        "id": f"tieba_{tid}",
                        "source": "tieba",
                        "_source": "tieba",
                        "_bar": bar,
                        "title": title,
                        "content": content[:2000],
                        "url": f"https://tieba.baidu.com/p/{tid}",
                        "author_hash": self.hash_author(str(tdata.get("author_name", "anon"))),
                        "replies": tdata.get("reply_num", 0),
                        "likes": 0,
                        "language": "zh-CN",
                        "timestamp": datetime.now().isoformat(),
                    })
                except Exception:
                    continue

            print(f"    {bar}吧(PC): {len(posts)} 条")

        except Exception as e:
            print(f"    ⚠️ {bar}吧(PC)失败: {e}")

        return posts
