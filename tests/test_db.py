"""测试 SQLite 持久化去重"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
import functools
print = functools.partial(print, flush=True)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.db import get_db, filter_new_posts, save_posts, get_post_count


def _make_posts():
    return [
        {"id": "test_1", "source": "test", "title": "RTX 5090 太贵了", "content": "RTX 5090 太贵了", "url": "http://a", "replies": 10, "likes": 5},
        {"id": "test_2", "source": "test", "title": "AMD 驱动又崩了", "content": "AMD 驱动又崩了", "url": "http://b", "replies": 20, "likes": 8},
        {"id": "test_3", "source": "test", "title": "显卡散热不行", "content": "显卡散热不行", "url": "http://c", "replies": 5, "likes": 2},
    ]


def test_filter_new_posts():
    """第一次过滤应全部为新帖"""
    posts = _make_posts()
    with get_db() as conn:
        conn.execute("DELETE FROM posts WHERE id LIKE 'test_%'")
    new = filter_new_posts(posts)
    assert len(new) == 3, f"Expected 3 new, got {len(new)}"
    # 清理
    with get_db() as conn:
        conn.execute("DELETE FROM posts WHERE id LIKE 'test_%'")


def test_save_and_dedup():
    """保存后再过滤应全部为旧帖"""
    posts = _make_posts()
    with get_db() as conn:
        conn.execute("DELETE FROM posts WHERE id LIKE 'test_%'")
    save_posts(posts)
    new2 = filter_new_posts(posts)
    assert len(new2) == 0, f"Expected 0 new, got {len(new2)}"
    # 清理
    with get_db() as conn:
        conn.execute("DELETE FROM posts WHERE id LIKE 'test_%'")


def test_mixed_filter():
    """混合过滤：2旧 + 1新"""
    posts = _make_posts()
    with get_db() as conn:
        conn.execute("DELETE FROM posts WHERE id LIKE 'test_%'")
    save_posts(posts)
    mixed = posts[:2] + [{"id": "test_4", "source": "test", "title": "新帖子", "content": "新帖子", "url": "http://d", "replies": 1, "likes": 0}]
    new3 = filter_new_posts(mixed)
    assert len(new3) == 1, f"Expected 1 new, got {len(new3)}"
    # 清理
    with get_db() as conn:
        conn.execute("DELETE FROM posts WHERE id LIKE 'test_%'")


def test_content_hash_dedup():
    """内容相同但 id 不同应被去重"""
    posts = _make_posts()
    with get_db() as conn:
        conn.execute("DELETE FROM posts WHERE id LIKE 'test_%'")
    save_posts(posts)
    dup = [{"id": "test_99", "source": "test", "title": "RTX 5090 太贵了", "content": "RTX 5090 太贵了", "url": "http://x", "replies": 0, "likes": 0}]
    new4 = filter_new_posts(dup)
    assert len(new4) == 0, f"Expected 0 (content hash dup), got {len(new4)}"
    # 清理
    with get_db() as conn:
        conn.execute("DELETE FROM posts WHERE id LIKE 'test_%'")


if __name__ == "__main__":
    test_filter_new_posts()
    print("第一次过滤: 3/3 条新帖 ✓")
    test_save_and_dedup()
    print("第二次过滤: 0/3 条新帖 ✓")
    test_mixed_filter()
    print("混合过滤: 1/3 条新帖 ✓")
    test_content_hash_dedup()
    print("内容去重: 0/1 条新帖 ✓")
    print("\n全部通过!")
