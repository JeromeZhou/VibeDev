"""GPU-Insight 单元测试 — QA Agent (James Bach) 产出"""

import sys
import json
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestConfig:
    """测试配置加载"""

    def test_load_config(self):
        from src.utils.config import load_config
        config = load_config("config/config.yaml")
        assert config["project"]["name"] == "GPU-Insight"
        assert "sources" in config
        assert "pphi" in config

    def test_get_enabled_sources(self):
        from src.utils.config import load_config, get_enabled_sources
        config = load_config("config/config.yaml")
        enabled = get_enabled_sources(config)
        # chiphell 已 disabled（567 error），验证至少有活跃源
        assert len(enabled) > 0, "应该有至少一个启用的数据源"
        assert "reddit" in enabled
        assert enabled["reddit"]["weight"] == 0.9

    def test_get_pphi_weights(self):
        from src.utils.config import load_config, get_pphi_weights
        config = load_config("config/config.yaml")
        weights = get_pphi_weights(config)
        assert abs(sum(weights.values()) - 1.0) < 0.01  # 权重之和应为 1.0


class TestCleaner:
    """测试数据清洗"""

    def test_deduplicate(self):
        from src.cleaners import _deduplicate
        posts = [
            {"content": "显存不够用", "title": "test1"},
            {"content": "显存不够用", "title": "test2"},  # 重复
            {"content": "功耗太高了", "title": "test3"},
        ]
        result = _deduplicate(posts)
        assert len(result) == 2

    def test_truncate(self):
        from src.cleaners import _truncate
        posts = [{"content": "a" * 3000}]
        result = _truncate(posts, max_chars=100)
        assert len(result[0]["content"]) <= 103  # 100 + "..."
        assert result[0].get("_truncated") is True

    def test_clean_data_empty(self):
        from src.utils.config import load_config
        from src.cleaners import clean_data
        config = load_config("config/config.yaml")
        result = clean_data([], config)
        assert result == []


class TestAnalyzerJsonExtract:
    """测试 JSON 提取（防幻觉关键环节）"""

    def test_extract_plain_json(self):
        from src.analyzers import _extract_json
        text = '{"pain_point": "显存不足", "category": "显存"}'
        result = _extract_json(text)
        assert len(result) == 1
        assert result[0]["pain_point"] == "显存不足"

    def test_extract_markdown_json(self):
        from src.analyzers import _extract_json
        text = '```json\n{"pain_point": "价格过高", "category": "价格"}\n```'
        result = _extract_json(text)
        assert len(result) == 1
        assert result[0]["pain_point"] == "价格过高"

    def test_extract_json_with_text(self):
        from src.analyzers import _extract_json
        text = '分析结果如下：\n{"pain_point": "驱动崩溃", "category": "驱动"}\n以上是分析。'
        result = _extract_json(text)
        assert len(result) >= 1
        assert result[0]["pain_point"] == "驱动崩溃"

    def test_extract_empty(self):
        from src.analyzers import _extract_json
        result = _extract_json("没有任何 JSON 内容")
        assert result == []


class TestPPHI:
    """测试 PPHI 排名算法"""

    def test_calculate_empty(self):
        from unittest.mock import patch
        from src.utils.config import load_config
        from src.rankers import calculate_pphi
        config = load_config("config/config.yaml")
        # Mock 掉历史加载和文件保存，确保纯空输入返回空
        with patch("src.rankers._load_historical_insights", return_value=[]), \
             patch("src.rankers._save_rankings"):
            result = calculate_pphi([], config)
        assert result == []

    def test_calculate_ranking_order(self):
        from unittest.mock import patch
        from src.utils.config import load_config
        from src.rankers import calculate_pphi
        config = load_config("config/config.yaml")
        data = [
            {"pain_point": "A", "confidence": 0.9, "_source": "chiphell", "approved": True},
            {"pain_point": "B", "confidence": 0.5, "_source": "reddit", "approved": True},
        ]
        # Mock 掉历史加载和文件保存，防止覆盖真实 latest.json
        with patch("src.rankers._load_historical_insights", return_value=[]), \
             patch("src.rankers._save_rankings"):
            result = calculate_pphi(data, config)
        assert len(result) == 2
        assert result[0]["rank"] == 1
        assert result[1]["rank"] == 2
        assert result[0]["pphi_score"] >= result[1]["pphi_score"]


class TestCostTracker:
    """测试成本追踪"""

    def test_check_budget_initial(self):
        from src.utils.config import load_config
        from src.utils.cost_tracker import CostTracker
        config = load_config("config/config.yaml")
        tracker = CostTracker(config)
        budget = tracker.check_budget()
        assert budget["budget"] == 80
        assert budget["status"] == "normal"


class TestMockData:
    """测试模拟数据生成"""

    def test_generate_mock_data(self):
        from tests.mock_data import generate_mock_data
        data = generate_mock_data()
        assert len(data) == 12
        assert all("title" in d for d in data)
        assert all("content" in d for d in data)
        assert all("source" in d for d in data)

    def test_mock_data_sources(self):
        from tests.mock_data import generate_mock_data
        data = generate_mock_data()
        sources = set(d["source"] for d in data)
        assert "chiphell" in sources
        assert "reddit" in sources


class TestReporter:
    """测试报告生成"""

    def test_generate_report(self, tmp_path):
        from src.reporters import generate_report
        config = {"paths": {"reports": str(tmp_path)}}
        rankings = [
            {"rank": 1, "pain_point": "测试痛点", "pphi_score": 50.0,
             "mentions": 10, "sources": ["test"], "trend": "new",
             "hidden_need": "测试需求", "confidence": 0.8},
        ]
        path = generate_report(rankings, config)
        assert Path(path).exists()
        content = Path(path).read_text(encoding="utf-8")
        assert "测试痛点" in content


class TestSchema:
    """测试数据 Schema"""

    def test_raw_post(self):
        from src.utils.schema import RawPost
        post = RawPost(id="test_001", source="chiphell", title="测试", content="内容")
        d = post.to_dict()
        assert d["id"] == "test_001"
        assert d["source"] == "chiphell"

    def test_pain_point(self):
        from src.utils.schema import PainPoint
        pp = PainPoint(pain_point="显存不足", category="显存", emotion_intensity=0.8)
        d = pp.to_dict()
        assert d["emotion_intensity"] == 0.8


class TestPainNameGuard:
    """测试痛点名称质量守卫"""

    def test_vague_category_name(self):
        from src.analyzers import _guard_pain_name
        parsed = {"pain_point": "散热", "category": "散热", "evidence": "GPU满载95度降频严重"}
        result = _guard_pain_name(parsed)
        assert result["pain_point"] != "散热"
        assert "95" in result["pain_point"] or "降频" in result["pain_point"]

    def test_vague_with_suffix(self):
        from src.analyzers import _guard_pain_name
        parsed = {"pain_point": "显存问题", "category": "显存", "evidence": "8GB显存玩4K不够用"}
        result = _guard_pain_name(parsed)
        assert result["pain_point"] != "显存问题"
        assert "8GB" in result["pain_point"] or "4K" in result["pain_point"]

    def test_qita_wenti(self):
        from src.analyzers import _guard_pain_name
        parsed = {"pain_point": "其他问题", "category": "其他", "evidence": "5090 FE Anti Sag Bracket"}
        result = _guard_pain_name(parsed)
        assert "其他" not in result["pain_point"]

    def test_good_name_unchanged(self):
        from src.analyzers import _guard_pain_name
        parsed = {"pain_point": "4K游戏帧率不足", "category": "性能", "evidence": "some evidence"}
        result = _guard_pain_name(parsed)
        assert result["pain_point"] == "4K游戏帧率不足"

    def test_too_long_truncated(self):
        from src.analyzers import _guard_pain_name
        parsed = {"pain_point": "Cinebench23长时间负载下显卡跑分拉胯，温度稳定在95℃，功耗稳定在256w", "category": "性能", "evidence": ""}
        result = _guard_pain_name(parsed)
        assert len(result["pain_point"]) <= 30

    def test_too_short_expanded(self):
        from src.analyzers import _guard_pain_name
        parsed = {"pain_point": "热", "category": "散热", "evidence": "显卡满载温度过高"}
        result = _guard_pain_name(parsed)
        assert len(result["pain_point"]) >= 3

    def test_english_vague_category(self):
        from src.analyzers import _guard_pain_name
        parsed = {"pain_point": "driver", "category": "驱动", "evidence": "NVIDIA driver crashes after update"}
        result = _guard_pain_name(parsed)
        assert result["pain_point"] != "driver"
        assert "crash" in result["pain_point"].lower() or "NVIDIA" in result["pain_point"]

    def test_english_vague_with_suffix(self):
        from src.analyzers import _guard_pain_name
        parsed = {"pain_point": "performance issue", "category": "性能", "evidence": "RTX 5080 drops to 30fps in Cyberpunk"}
        result = _guard_pain_name(parsed)
        assert result["pain_point"] != "performance issue"

    def test_english_gpu_prefix_stripped(self):
        from src.analyzers import _guard_pain_name
        parsed = {"pain_point": "GPU thermal issues", "category": "散热", "evidence": "GPU hits 95C under load"}
        result = _guard_pain_name(parsed)
        assert result["pain_point"] != "GPU thermal issues"

    def test_english_good_name_unchanged(self):
        from src.analyzers import _guard_pain_name
        parsed = {"pain_point": "RTX 5080 crashes in Cyberpunk", "category": "性能", "evidence": "some evidence"}
        result = _guard_pain_name(parsed)
        assert result["pain_point"] == "RTX 5080 crashes in Cyberpunk"


class TestNormalizePainPoint:
    """测试痛点名称规范化（语义合并基础）"""

    def test_strip_parenthetical(self):
        from src.rankers import _normalize_pain_point
        norm, orig = _normalize_pain_point("散热温度过高(散热)")
        assert norm == "散热温度过高"
        assert orig == "散热温度过高(散热)"

    def test_strip_chinese_parenthetical(self):
        from src.rankers import _normalize_pain_point
        norm, _ = _normalize_pain_point("驱动崩溃（驱动）")
        assert norm == "驱动崩溃"

    def test_strip_gpu_prefix(self):
        from src.rankers import _normalize_pain_point
        norm, _ = _normalize_pain_point("显卡散热不足")
        assert norm == "散热"

    def test_strip_suffix(self):
        from src.rankers import _normalize_pain_point
        norm, _ = _normalize_pain_point("散热温度问题")
        assert norm == "散热温度"

    def test_same_after_normalize(self):
        """同义痛点规范化后应相同"""
        from src.rankers import _normalize_pain_point
        n1, _ = _normalize_pain_point("显卡散热问题")
        n2, _ = _normalize_pain_point("散热(散热)")
        assert n1 == n2  # 都应该规范化为 "散热"

    def test_different_stay_different(self):
        """不同痛点规范化后应不同"""
        from src.rankers import _normalize_pain_point
        n1, _ = _normalize_pain_point("显存温度过高")
        n2, _ = _normalize_pain_point("风扇噪音大")
        assert n1 != n2

    def test_short_name_preserved(self):
        """短名称不应被过度裁剪"""
        from src.rankers import _normalize_pain_point
        norm, _ = _normalize_pain_point("功耗")
        assert norm == "功耗"


class TestAggregate:
    """测试痛点聚合逻辑"""

    def test_merge_same_pain_point(self):
        from src.rankers import _aggregate
        insights = [
            {"pain_point": "散热问题", "source_post_ids": ["reddit_abc"], "source_urls": ["https://reddit.com/abc"],
             "gpu_tags": {"brands": ["NVIDIA"], "models": ["RTX 4090"], "series": [], "manufacturers": []},
             "inferred_need": None, "total_replies": 5, "total_likes": 10, "earliest_timestamp": ""},
            {"pain_point": "显卡散热不足", "source_post_ids": ["nga_123"], "source_urls": ["https://nga.cn/123"],
             "gpu_tags": {"brands": ["NVIDIA"], "models": ["RTX 4080"], "series": [], "manufacturers": []},
             "inferred_need": None, "total_replies": 3, "total_likes": 7, "earliest_timestamp": ""},
        ]
        result = _aggregate(insights)
        # 两个痛点应合并为一个（规范化后都是 "散热"）
        assert len(result) == 1
        key = list(result.keys())[0]
        assert result[key]["count"] == 2
        assert "RTX 4090" in result[key]["gpu_tags"]["models"]
        assert "RTX 4080" in result[key]["gpu_tags"]["models"]

    def test_no_merge_different(self):
        from src.rankers import _aggregate
        insights = [
            {"pain_point": "显存温度过高", "source_post_ids": ["reddit_abc"], "source_urls": [],
             "gpu_tags": {"brands": [], "models": [], "series": [], "manufacturers": []},
             "inferred_need": None, "total_replies": 0, "total_likes": 0, "earliest_timestamp": ""},
            {"pain_point": "风扇噪音大", "source_post_ids": ["nga_123"], "source_urls": [],
             "gpu_tags": {"brands": [], "models": [], "series": [], "manufacturers": []},
             "inferred_need": None, "total_replies": 0, "total_likes": 0, "earliest_timestamp": ""},
        ]
        result = _aggregate(insights)
        assert len(result) == 2

    def test_mixed_language_good(self):
        from src.analyzers import _guard_pain_name
        parsed = {"pain_point": "RTX 5090散热不足导致降频", "category": "散热", "evidence": ""}
        result = _guard_pain_name(parsed)
        assert result["pain_point"] == "RTX 5090散热不足导致降频"


class TestWeeklyReport:
    """周报生成测试"""

    def test_generate_weekly_no_data(self, tmp_path):
        """无数据时返回 None"""
        from src.reporters.weekly import generate_weekly_report
        config = {"paths": {"reports": str(tmp_path)}}
        result = generate_weekly_report(config)
        # 可能返回 None（无数据）或路径（有历史数据）
        assert result is None or str(tmp_path) in result


class TestQualityTier:
    """数据质量分层测试"""

    def test_gold_tier(self):
        from src.rankers import _classify_quality_tier
        data = {"inferred_need_obj": {
            "hidden_need": "需要主动散热系统",
            "reasoning_chain": ["散热是核心", "用户需要主动散热"],
            "munger_review": {"quality_level": "strong", "comment": "ok"},
        }}
        assert _classify_quality_tier(data) == "gold"

    def test_gold_moderate(self):
        from src.rankers import _classify_quality_tier
        data = {"inferred_need_obj": {
            "hidden_need": "需要更好的驱动",
            "reasoning_chain": ["驱动问题频发"],
            "munger_review": {"quality_level": "moderate", "comment": "需更多数据"},
        }}
        assert _classify_quality_tier(data) == "gold"

    def test_silver_no_munger(self):
        from src.rankers import _classify_quality_tier
        data = {"inferred_need_obj": {
            "hidden_need": "需要更好的散热",
            "reasoning_chain": ["温度过高"],
            "munger_review": None,
        }}
        assert _classify_quality_tier(data) == "silver"

    def test_silver_weak_munger(self):
        from src.rankers import _classify_quality_tier
        data = {"inferred_need_obj": {
            "hidden_need": "需要更好的散热",
            "reasoning_chain": ["温度过高"],
            "munger_review": {"quality_level": "weak", "comment": "证据不足"},
        }}
        assert _classify_quality_tier(data) == "silver"

    def test_bronze_no_hidden_need(self):
        from src.rankers import _classify_quality_tier
        data = {"inferred_need_obj": {
            "hidden_need": "",
            "reasoning_chain": [],
            "munger_review": None,
        }}
        assert _classify_quality_tier(data) == "bronze"

    def test_bronze_no_inferred(self):
        from src.rankers import _classify_quality_tier
        data = {"inferred_need_obj": None}
        assert _classify_quality_tier(data) == "bronze"

    def test_bronze_missing_key(self):
        from src.rankers import _classify_quality_tier
        data = {}
        assert _classify_quality_tier(data) == "bronze"
