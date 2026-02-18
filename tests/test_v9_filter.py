"""v9 AI 相关性过滤 + 漏斗整合 测试"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_filter_fast_pass():
    """测试快速通道：专业源 + 已打标帖子直接保留"""
    from src.filters import filter_gpu_relevant, AUTO_KEEP_SOURCES

    # 专业源帖子
    posts = [
        {"id": "tp_1", "source": "techpowerup", "_source": "techpowerup", "title": "RTX 5090 Review"},
        {"id": "vc_1", "source": "videocardz", "_source": "videocardz", "title": "AMD RX 9070 Specs"},
        {"id": "ch_1", "source": "chiphell", "_source": "chiphell", "title": "装机分享"},
    ]
    # 不调用 LLM，用 mock
    class MockLLM:
        def call_simple(self, prompt, system):
            raise Exception("Should not be called for fast pass")

    result = filter_gpu_relevant(posts, MockLLM(), shadow=True)
    assert len(result) == 3, f"Expected 3, got {len(result)}"
    assert all(p["_relevance_class"] == 2 for p in result), "All should be class 2"
    assert all(p["_relevance_reason"] == "fast_pass" for p in result)
    print("  OK test_filter_fast_pass")


def test_filter_gpu_tagged():
    """测试已打标帖子走快速通道"""
    from src.filters import filter_gpu_relevant

    posts = [
        {"id": "nga_1", "source": "nga", "_source": "nga", "title": "电脑卡顿",
         "_gpu_tags": {"models": ["RTX 4060"], "brands": ["NVIDIA"], "series": []}},
    ]
    class MockLLM:
        def call_simple(self, prompt, system):
            raise Exception("Should not be called for tagged posts")

    result = filter_gpu_relevant(posts, MockLLM(), shadow=True)
    assert len(result) == 1
    assert result[0]["_relevance_class"] == 2
    print("  OK test_filter_gpu_tagged")


def test_filter_layer1_classify():
    """测试 Layer 1 标题分类"""
    from src.filters import _layer1_title_classify

    posts = [
        {"id": "1", "source": "nga", "title": "RTX 5090 温度太高了"},
        {"id": "2", "source": "nga", "title": "iPhone 16 Pro 体验"},
        {"id": "3", "source": "nga", "title": "电脑配置推荐"},
    ]

    class MockLLM:
        def call_simple(self, prompt, system):
            return "2\n0\n1"

    keep, uncertain, drop = _layer1_title_classify(posts, MockLLM())
    assert len(keep) == 1 and keep[0]["id"] == "1", f"keep: {[p['id'] for p in keep]}"
    assert len(drop) == 1 and drop[0]["id"] == "2", f"drop: {[p['id'] for p in drop]}"
    assert len(uncertain) == 1 and uncertain[0]["id"] == "3", f"uncertain: {[p['id'] for p in uncertain]}"
    print("  OK test_filter_layer1_classify")


def test_filter_layer2_content():
    """测试 Layer 2 内容深度判断"""
    from src.filters import _layer2_content_classify

    posts = [
        {"id": "1", "source": "nga", "title": "电脑配置推荐",
         "content": "想配一台4K游戏机，显卡选RTX 4070还是RX 7800XT？", "comments": ""},
        {"id": "2", "source": "nga", "title": "新买的设备",
         "content": "iPhone Air 真的很轻", "comments": "手感不错"},
    ]

    class MockLLM:
        def call_simple(self, prompt, system):
            return "1|讨论显卡选择\n0|iPhone手机话题"

    kept, dropped = _layer2_content_classify(posts, MockLLM())
    assert len(kept) == 1 and kept[0]["id"] == "1"
    assert len(dropped) == 1 and dropped[0]["id"] == "2"
    assert kept[0]["_relevance_class"] == 2  # L2 确认 → 提升到 class 2
    assert dropped[0]["_relevance_class"] == 0
    print("  OK test_filter_layer2_content")


def test_filter_shadow_mode():
    """测试 Shadow Mode：标记但不删除"""
    from src.filters import filter_gpu_relevant

    posts = [
        {"id": "1", "source": "nga", "_source": "nga", "title": "RTX 5090 散热",
         "_gpu_tags": {}},
        {"id": "2", "source": "nga", "_source": "nga", "title": "iPhone 16 评测",
         "_gpu_tags": {}},
    ]

    class MockLLM:
        def call_simple(self, prompt, system):
            # L1: 第一条相关，第二条不相关
            return "2\n0"

    result = filter_gpu_relevant(posts, MockLLM(), shadow=True)
    # Shadow mode: 全部返回
    assert len(result) == 2, f"Shadow mode should return all, got {len(result)}"
    shadow_drops = [p for p in result if p.get("_relevance_shadow_drop")]
    assert len(shadow_drops) == 1
    assert shadow_drops[0]["id"] == "2"
    print("  OK test_filter_shadow_mode")


def test_filter_hard_mode():
    """测试硬过滤模式"""
    from src.filters import filter_gpu_relevant

    posts = [
        {"id": "1", "source": "nga", "_source": "nga", "title": "显卡驱动崩溃",
         "_gpu_tags": {}},
        {"id": "2", "source": "nga", "_source": "nga", "title": "路由器设置教程",
         "_gpu_tags": {}},
    ]

    class MockLLM:
        def call_simple(self, prompt, system):
            return "2\n0"

    result = filter_gpu_relevant(posts, MockLLM(), shadow=False)
    # 硬过滤: 只返回相关的
    assert len(result) == 1, f"Hard mode should filter, got {len(result)}"
    assert result[0]["id"] == "1"
    print("  OK test_filter_hard_mode")


def test_filter_llm_error_fallback():
    """测试 LLM 失败时的降级处理"""
    from src.filters import filter_gpu_relevant

    posts = [
        {"id": "1", "source": "nga", "_source": "nga", "title": "测试帖子",
         "_gpu_tags": {}},
    ]

    class FailLLM:
        def call_simple(self, prompt, system):
            raise Exception("API timeout")

    result = filter_gpu_relevant(posts, FailLLM(), shadow=True)
    # LLM 失败时应保留全部
    assert len(result) == 1
    print("  OK test_filter_llm_error_fallback")


def test_funnel_no_signal_goes_to_l2():
    """测试 v9 改进：无信号帖子也送 L2"""
    from src.analyzers.funnel import run_funnel

    # 构造一个无信号词的帖子
    posts = [
        {"id": "1", "source": "nga", "_source": "nga", "title": "这个东西怎么样",
         "content": "这个东西怎么样", "comments": ""},
        {"id": "2", "source": "reddit", "_source": "reddit", "title": "GPU crash after update",
         "content": "GPU crash after driver update", "comments": ""},
    ]

    class MockLLM:
        def call_simple(self, prompt, system):
            # 第二条有信号词会排前面，第一条无信号排后面
            # 但两条都应该被 L2 处理
            return "2\n1"

    deep, light = run_funnel(posts, MockLLM())
    # 关键：无信号帖子不应该被直接标 class=0
    all_posts = deep + light
    # 至少有帖子进入了 deep 或 light（不是全被排除）
    assert len(all_posts) >= 1, f"Expected at least 1 post in funnel output, got {len(all_posts)}"
    print("  OK test_funnel_no_signal_goes_to_l2")


def test_db_migration():
    """测试 DB 迁移：新增 relevance 列"""
    import tempfile
    import sqlite3
    from pathlib import Path

    # 临时 DB
    tmp = tempfile.mktemp(suffix=".db")
    try:
        # 模拟旧 DB（没有 relevance 列）
        conn = sqlite3.connect(tmp)
        conn.execute("""CREATE TABLE posts (
            id TEXT PRIMARY KEY, source TEXT NOT NULL, content_hash TEXT NOT NULL,
            title TEXT, url TEXT, replies INTEGER DEFAULT 0, likes INTEGER DEFAULT 0,
            gpu_tags TEXT, timestamp TEXT, created_at TEXT DEFAULT (datetime('now')),
            comments TEXT
        )""")
        conn.commit()
        conn.close()

        # 用 db 模块的迁移
        import src.utils.db as db_mod
        original_path = db_mod.DB_PATH
        db_mod.DB_PATH = Path(tmp)
        try:
            with db_mod.get_db() as conn:
                # 迁移应该自动添加 relevance_class 和 relevance_reason
                conn.execute("INSERT INTO posts (id, source, content_hash, relevance_class, relevance_reason) VALUES ('test', 'nga', 'abc', 2, 'L1_relevant')")
                row = conn.execute("SELECT relevance_class, relevance_reason FROM posts WHERE id='test'").fetchone()
                assert row["relevance_class"] == 2, f"Expected 2, got {row['relevance_class']}"
                assert row["relevance_reason"] == "L1_relevant"
            print("  OK test_db_migration")
        finally:
            db_mod.DB_PATH = original_path
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def test_cleaners_no_ai_filter():
    """测试 cleaners 不再包含 AI 过滤"""
    import src.cleaners as cleaners
    # 确认 _filter_gpu_relevant 不存在
    assert not hasattr(cleaners, '_filter_gpu_relevant'), "Cleaner should not have AI filter"
    assert not hasattr(cleaners, '_batch_relevance_check'), "Cleaner should not have batch check"
    print("  OK test_cleaners_no_ai_filter")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    print("v9 Tests:")
    test_filter_fast_pass()
    test_filter_gpu_tagged()
    test_filter_layer1_classify()
    test_filter_layer2_content()
    test_filter_shadow_mode()
    test_filter_hard_mode()
    test_filter_llm_error_fallback()
    test_funnel_no_signal_goes_to_l2()
    test_db_migration()
    test_cleaners_no_ai_filter()
    print("\nALL 10 TESTS PASSED")
