"""GPU-Insight 本地 SQLite 数据库 — 持久化去重 + 历史追踪"""

import sqlite3
import json
import hashlib
from datetime import datetime
from pathlib import Path

DB_PATH = Path("data/gpu_insight.db")


def get_db() -> sqlite3.Connection:
    """获取数据库连接（自动建表）"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _init_tables(conn)
    return conn


def _init_tables(conn: sqlite3.Connection):
    """初始化表结构"""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS posts (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            title TEXT,
            url TEXT,
            replies INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            gpu_tags TEXT,
            timestamp TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_posts_hash ON posts(content_hash);
        CREATE INDEX IF NOT EXISTS idx_posts_source ON posts(source);

        CREATE TABLE IF NOT EXISTS pain_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date TEXT NOT NULL,
            pain_point TEXT NOT NULL,
            category TEXT,
            mentions INTEGER DEFAULT 0,
            sources TEXT,
            gpu_tags TEXT,
            source_urls TEXT,
            evidence TEXT,
            hidden_need TEXT,
            confidence REAL DEFAULT 0,
            pphi_score REAL DEFAULT 0,
            total_replies INTEGER DEFAULT 0,
            total_likes INTEGER DEFAULT 0,
            earliest_timestamp TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_pp_date ON pain_points(run_date);

        CREATE TABLE IF NOT EXISTS pphi_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date TEXT NOT NULL,
            rank INTEGER NOT NULL,
            pain_point TEXT NOT NULL,
            pphi_score REAL NOT NULL,
            mentions INTEGER DEFAULT 0,
            gpu_tags TEXT,
            source_urls TEXT,
            hidden_need TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_pphi_date ON pphi_history(run_date);

        CREATE TABLE IF NOT EXISTS scrape_checkpoints (
            source TEXT PRIMARY KEY,
            last_scrape_at TEXT NOT NULL,
            last_post_count INTEGER DEFAULT 0,
            total_scraped INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_posts_url ON posts(url);
    """)
    conn.commit()

    # 迁移：为旧表添加新列（如果不存在）
    _migrate_tables(conn)


def _migrate_tables(conn: sqlite3.Connection):
    """增量迁移：安全添加新列"""
    migrations = [
        ("pain_points", "total_replies", "INTEGER DEFAULT 0"),
        ("pain_points", "total_likes", "INTEGER DEFAULT 0"),
        ("pain_points", "earliest_timestamp", "TEXT"),
        ("pphi_history", "total_replies", "INTEGER DEFAULT 0"),
        ("pphi_history", "total_likes", "INTEGER DEFAULT 0"),
        ("posts", "comments", "TEXT"),
    ]
    for table, column, col_type in migrations:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # 列已存在


def content_hash(text: str) -> str:
    """计算内容哈希"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def filter_new_posts(posts: list[dict]) -> list[dict]:
    """过滤已入库的帖子，只返回新帖子（持久化去重）"""
    if not posts:
        return []

    conn = get_db()
    new_posts = []

    for post in posts:
        post_id = post.get("id", "")
        text = post.get("content", "") or post.get("title", "")
        h = content_hash(text)

        # 检查 id 或 content_hash 是否已存在
        row = conn.execute(
            "SELECT id FROM posts WHERE id = ? OR content_hash = ?",
            (post_id, h)
        ).fetchone()

        if not row:
            new_posts.append(post)

    conn.close()
    return new_posts


def save_posts(posts: list[dict]):
    """批量保存帖子到数据库（新帖插入，旧帖更新互动数据）"""
    if not posts:
        return

    conn = get_db()
    for post in posts:
        text = post.get("content", "") or post.get("title", "")
        h = content_hash(text)
        gpu_tags = json.dumps(post.get("_gpu_tags", {}), ensure_ascii=False)

        try:
            conn.execute(
                """INSERT INTO posts (id, source, content_hash, title, url, replies, likes, gpu_tags, timestamp, comments)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       replies = MAX(posts.replies, excluded.replies),
                       likes = MAX(posts.likes, excluded.likes),
                       comments = COALESCE(excluded.comments, posts.comments)""",
                (
                    post.get("id", ""),
                    post.get("source", ""),
                    h,
                    post.get("title", ""),
                    post.get("url", ""),
                    post.get("replies", 0),
                    post.get("likes", 0),
                    gpu_tags,
                    post.get("timestamp", ""),
                    post.get("comments", ""),
                )
            )
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()


def save_rankings(rankings: list[dict]):
    """保存 PPHI 排名快照到历史表（含互动数据）"""
    if not rankings:
        return

    conn = get_db()
    run_date = datetime.now().strftime("%Y-%m-%d %H:%M")

    for r in rankings:
        conn.execute(
            """INSERT INTO pphi_history (run_date, rank, pain_point, pphi_score, mentions, gpu_tags, source_urls, hidden_need, total_replies, total_likes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_date,
                r.get("rank", 0),
                r.get("pain_point", ""),
                r.get("pphi_score", 0),
                r.get("mentions", 0),
                json.dumps(r.get("gpu_tags", {}), ensure_ascii=False),
                json.dumps(r.get("source_urls", []), ensure_ascii=False),
                r.get("hidden_need", ""),
                r.get("total_replies", 0),
                r.get("total_likes", 0),
            )
        )

    conn.commit()
    conn.close()


def save_pain_points(pain_points: list[dict]):
    """保存痛点到历史表（支持 PainInsight 结构）"""
    if not pain_points:
        return

    conn = get_db()
    run_date = datetime.now().strftime("%Y-%m-%d %H:%M")

    for pp in pain_points:
        # 从 source_post_ids 提取来源列表
        source_post_ids = pp.get("source_post_ids", [])
        sources = list(set(pid.split("_")[0] for pid in source_post_ids if "_" in pid))

        # mentions = 关联帖子数
        mentions = len(source_post_ids)

        # 从 inferred_need 对象中提取 hidden_need 和 confidence
        inferred_need = pp.get("inferred_need") or {}
        hidden_need = inferred_need.get("hidden_need", "") if isinstance(inferred_need, dict) else ""
        confidence = inferred_need.get("confidence", 0) if isinstance(inferred_need, dict) else 0

        conn.execute(
            """INSERT INTO pain_points (run_date, pain_point, category, mentions, sources, gpu_tags, source_urls, evidence, hidden_need, confidence, pphi_score, total_replies, total_likes, earliest_timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_date,
                pp.get("pain_point", ""),
                pp.get("category", ""),
                mentions,
                json.dumps(sources, ensure_ascii=False),
                json.dumps(pp.get("gpu_tags", {}), ensure_ascii=False),
                json.dumps(pp.get("source_urls", []), ensure_ascii=False),
                pp.get("evidence", ""),
                hidden_need,
                confidence,
                pp.get("pphi_score", 0),
                pp.get("total_replies", 0),
                pp.get("total_likes", 0),
                pp.get("earliest_timestamp", ""),
            )
        )

    conn.commit()
    conn.close()


def get_post_count() -> dict:
    """获取帖子统计"""
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    by_source = {}
    for row in conn.execute("SELECT source, COUNT(*) as cnt FROM posts GROUP BY source"):
        by_source[row["source"]] = row["cnt"]
    conn.close()
    return {"total": total, "by_source": by_source}


def save_checkpoint(source: str, post_count: int):
    """保存抓取检查点"""
    conn = get_db()
    conn.execute(
        """INSERT INTO scrape_checkpoints (source, last_scrape_at, last_post_count, total_scraped)
           VALUES (?, datetime('now'), ?, ?)
           ON CONFLICT(source) DO UPDATE SET
               last_scrape_at = datetime('now'),
               last_post_count = excluded.last_post_count,
               total_scraped = scrape_checkpoints.total_scraped + excluded.last_post_count""",
        (source, post_count, post_count)
    )
    conn.commit()
    conn.close()


def get_checkpoint(source: str) -> dict | None:
    """获取抓取检查点"""
    conn = get_db()
    row = conn.execute(
        "SELECT source, last_scrape_at, last_post_count, total_scraped FROM scrape_checkpoints WHERE source = ?",
        (source,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_trend_data(days: int = 30) -> list[dict]:
    """获取最近 N 天的 PPHI 趋势数据"""
    conn = get_db()
    rows = conn.execute(
        """SELECT run_date, rank, pain_point, pphi_score
           FROM pphi_history
           ORDER BY run_date DESC, rank ASC
           LIMIT ?""",
        (days * 10,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
