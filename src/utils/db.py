"""GPU-Insight 本地 SQLite 数据库 — 持久化去重 + 历史追踪"""

import sqlite3
import json
import hashlib
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

DB_PATH = Path("data/gpu_insight.db")

# 标记是否已初始化（进程级单例）
_initialized = False


def init_db():
    """进程启动时调用一次 — 建表 + 迁移。后续 get_db() 不再重复执行。"""
    global _initialized
    if _initialized:
        return
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    _init_tables(conn)
    conn.close()
    _initialized = True


@contextmanager
def get_db() -> sqlite3.Connection:
    """获取数据库连接（context manager，自动关闭）"""
    global _initialized
    if not _initialized:
        init_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


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
        CREATE INDEX IF NOT EXISTS idx_pphi_date_pain ON pphi_history(run_date, pain_point);

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
        ("pphi_history", "inferred_need_json", "TEXT"),  # v9.5: 完整推理对象（reasoning_chain + munger_review）
        ("pphi_history", "category", "TEXT"),  # v9.5: 痛点分类
        ("pphi_history", "affected_users", "TEXT"),  # v9.5: 影响范围
        ("posts", "comments", "TEXT"),
        # v9: AI 相关性过滤结果
        ("posts", "relevance_class", "INTEGER DEFAULT -1"),
        ("posts", "relevance_reason", "TEXT"),
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

    with get_db() as conn:
        new_posts = []
        for post in posts:
            post_id = post.get("id", "")
            text = post.get("content", "") or post.get("title", "")
            h = content_hash(text)

            row = conn.execute(
                "SELECT id FROM posts WHERE id = ? OR content_hash = ?",
                (post_id, h)
            ).fetchone()

            if not row:
                new_posts.append(post)

    return new_posts


def save_posts(posts: list[dict]):
    """批量保存帖子到数据库（新帖插入，旧帖更新互动数据）"""
    if not posts:
        return

    with get_db() as conn:
        for post in posts:
            text = post.get("content", "") or post.get("title", "")
            h = content_hash(text)
            gpu_tags = json.dumps(post.get("_gpu_tags", {}), ensure_ascii=False)

            try:
                conn.execute(
                    """INSERT INTO posts (id, source, content_hash, title, url, replies, likes, gpu_tags, timestamp, comments, relevance_class, relevance_reason)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(id) DO UPDATE SET
                           replies = MAX(posts.replies, excluded.replies),
                           likes = MAX(posts.likes, excluded.likes),
                           comments = COALESCE(excluded.comments, posts.comments),
                           relevance_class = CASE WHEN excluded.relevance_class >= 0 THEN excluded.relevance_class ELSE posts.relevance_class END,
                           relevance_reason = COALESCE(excluded.relevance_reason, posts.relevance_reason)""",
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
                        post.get("_relevance_class", -1),
                        post.get("_relevance_reason", ""),
                    )
                )
            except sqlite3.IntegrityError:
                pass


def save_rankings(rankings: list[dict]):
    """保存 PPHI 排名快照到历史表（含互动数据）"""
    if not rankings:
        return

    with get_db() as conn:
        run_date = datetime.now().strftime("%Y-%m-%d %H:%M")

        for r in rankings:
            conn.execute(
                """INSERT INTO pphi_history (run_date, rank, pain_point, pphi_score, mentions, gpu_tags, source_urls, hidden_need, total_replies, total_likes, inferred_need_json, category, affected_users)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                    json.dumps(r.get("inferred_need"), ensure_ascii=False) if r.get("inferred_need") else None,
                    r.get("category", ""),
                    r.get("affected_users", ""),
                )
            )


def save_pain_points(pain_points: list[dict]):
    """保存痛点到历史表（支持 PainInsight 结构）"""
    if not pain_points:
        return

    with get_db() as conn:
        run_date = datetime.now().strftime("%Y-%m-%d %H:%M")

        for pp in pain_points:
            source_post_ids = pp.get("source_post_ids", [])
            sources = list(set(pid.split("_")[0] for pid in source_post_ids if "_" in pid))
            mentions = len(source_post_ids)

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


def get_post_count() -> dict:
    """获取帖子统计"""
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
        by_source = {}
        for row in conn.execute("SELECT source, COUNT(*) as cnt FROM posts GROUP BY source"):
            by_source[row["source"]] = row["cnt"]
    return {"total": total, "by_source": by_source}


def save_checkpoint(source: str, post_count: int):
    """保存抓取检查点"""
    with get_db() as conn:
        conn.execute(
            """INSERT INTO scrape_checkpoints (source, last_scrape_at, last_post_count, total_scraped)
               VALUES (?, datetime('now'), ?, ?)
               ON CONFLICT(source) DO UPDATE SET
                   last_scrape_at = datetime('now'),
                   last_post_count = excluded.last_post_count,
                   total_scraped = scrape_checkpoints.total_scraped + excluded.last_post_count""",
            (source, post_count, post_count)
        )


def get_checkpoint(source: str) -> dict | None:
    """获取抓取检查点"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT source, last_scrape_at, last_post_count, total_scraped FROM scrape_checkpoints WHERE source = ?",
            (source,)
        ).fetchone()
    return dict(row) if row else None


def get_trend_data(days: int = 30) -> list[dict]:
    """获取最近 N 天的 PPHI 趋势数据"""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT run_date, rank, pain_point, pphi_score
               FROM pphi_history
               ORDER BY run_date DESC, rank ASC
               LIMIT ?""",
            (days * 10,)
        ).fetchall()
    return [dict(r) for r in rows]


def backup_db(max_backups: int = 7):
    """备份数据库文件，保留最近 N 份"""
    import shutil
    if not DB_PATH.exists():
        return
    backup_dir = DB_PATH.parent / "backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    dest = backup_dir / f"gpu_insight_{timestamp}.db"
    shutil.copy2(str(DB_PATH), str(dest))
    # 清理旧备份
    backups = sorted(backup_dir.glob("gpu_insight_*.db"), reverse=True)
    for old in backups[max_backups:]:
        old.unlink()
    print(f"  [DB] 备份: {dest.name}（保留 {min(len(backups), max_backups)} 份）")


def cleanup_old_history(keep_runs: int = 30):
    """清理 pphi_history 旧数据，只保留最近 N 轮"""
    with get_db() as conn:
        dates = conn.execute(
            "SELECT DISTINCT run_date FROM pphi_history ORDER BY run_date DESC"
        ).fetchall()
        if len(dates) <= keep_runs:
            return 0

        cutoff_date = dates[keep_runs - 1]["run_date"]
        result = conn.execute(
            "DELETE FROM pphi_history WHERE run_date < ?", (cutoff_date,)
        )
        deleted = result.rowcount
        if deleted > 0:
            print(f"  [DB] 清理 pphi_history: 删除 {deleted} 行（保留最近 {keep_runs} 轮）")
        return deleted
