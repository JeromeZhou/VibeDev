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
        assert "chiphell" in enabled
        assert enabled["chiphell"]["weight"] == 1.0

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
        from src.utils.config import load_config
        from src.rankers import calculate_pphi
        config = load_config("config/config.yaml")
        result = calculate_pphi([], config)
        assert result == []

    def test_calculate_ranking_order(self):
        from src.utils.config import load_config
        from src.rankers import calculate_pphi
        config = load_config("config/config.yaml")
        data = [
            {"pain_point": "A", "confidence": 0.9, "_source": "chiphell", "approved": True},
            {"pain_point": "B", "confidence": 0.5, "_source": "reddit", "approved": True},
        ]
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
