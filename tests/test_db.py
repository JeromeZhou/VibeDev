"""测试 SQLite 持久化去重"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
import functools
print = functools.partial(print, flush=True)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.db import get_db, filter_new_posts, save_posts, get_post_count

# 清理测试数据
conn = get_db()
conn.execute("DELETE FROM posts WHERE id LIKE 'test_%'")
conn.commit()
conn.close()

# 模拟帖子
posts = [
    {"id": "test_1", "source": "test", "title": "RTX 5090 太贵了", "content": "RTX 5090 太贵了", "url": "http://a", "replies": 10, "likes": 5},
    {"id": "test_2", "source": "test", "title": "AMD 驱动又崩了", "content": "AMD 驱动又崩了", "url": "http://b", "replies": 20, "likes": 8},
    {"id": "test_3", "source": "test", "title": "显卡散热不行", "content": "显卡散热不行", "url": "http://c", "replies": 5, "likes": 2},
]

# 第一次：全部是新帖
new = filter_new_posts(posts)
print(f"第一次过滤: {len(new)}/3 条新帖 (应为 3)")

# 保存
save_posts(posts)
stats = get_post_count()
print(f"入库后统计: {stats}")

# 第二次：全部是旧帖
new2 = filter_new_posts(posts)
print(f"第二次过滤: {len(new2)}/3 条新帖 (应为 0)")

# 混合：2旧 + 1新
mixed = posts[:2] + [{"id": "test_4", "source": "test", "title": "新帖子", "content": "新帖子", "url": "http://d", "replies": 1, "likes": 0}]
new3 = filter_new_posts(mixed)
print(f"混合过滤: {len(new3)}/3 条新帖 (应为 1)")

# 内容相同但 id 不同
dup = [{"id": "test_99", "source": "test", "title": "RTX 5090 太贵了", "content": "RTX 5090 太贵了", "url": "http://x", "replies": 0, "likes": 0}]
new4 = filter_new_posts(dup)
print(f"内容去重: {len(new4)}/1 条新帖 (应为 0, 内容hash相同)")

# 清理
conn = get_db()
conn.execute("DELETE FROM posts WHERE id LIKE 'test_%'")
conn.commit()
conn.close()

print("\n全部通过!")
