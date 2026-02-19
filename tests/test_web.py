"""GPU-Insight Web 路由冒烟测试 — TestClient 验证所有页面"""

import json
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from src.web.app import app

client = TestClient(app)

# Mock 数据
MOCK_RANKINGS = {
    "timestamp": "2026-02-19T12:00:00",
    "total_pain_points": 2,
    "rankings": [
        {
            "rank": 1,
            "pain_point": "显存温度过高需要拆解改造散热",
            "pphi_score": 45.2,
            "mentions": 5,
            "sources": ["reddit", "nga"],
            "source_urls": ["https://reddit.com/r/nvidia/abc"],
            "gpu_tags": {"brands": ["NVIDIA"], "models": ["RTX 4090"], "series": [], "manufacturers": []},
            "hidden_need": "需要具备多重安全保护的主动散热系统",
            "inferred_need": {
                "hidden_need": "需要具备多重安全保护的主动散热系统",
                "confidence": 0.7,
                "reasoning_chain": ["散热是核心痛点", "用户需要主动散热"],
                "munger_review": {"quality_level": "moderate", "comment": "需更多数据验证"},
            },
            "confidence": 0.7,
            "category": "散热",
            "affected_users": "广泛",
            "evidence": "显存温度95度",
            "trend": "stable",
            "total_replies": 10,
            "total_likes": 20,
            "munger_quality": "moderate",
            "needs_verification": False,
        },
        {
            "rank": 2,
            "pain_point": "RTX 5090 溢价严重性价比低",
            "pphi_score": 38.1,
            "mentions": 3,
            "sources": ["nga"],
            "source_urls": [],
            "gpu_tags": {"brands": ["NVIDIA"], "models": ["RTX 5090"], "series": [], "manufacturers": []},
            "hidden_need": "",
            "inferred_need": None,
            "confidence": 0,
            "category": "价格",
            "affected_users": "广泛",
            "evidence": "",
            "trend": "new",
            "total_replies": 5,
            "total_likes": 8,
            "munger_quality": "unknown",
            "needs_verification": False,
        },
    ],
}


def _mock_load_rankings():
    return MOCK_RANKINGS


class TestPages:
    """页面路由冒烟测试"""

    @patch("src.web.app._load_rankings", _mock_load_rankings)
    def test_dashboard(self):
        r = client.get("/")
        assert r.status_code == 200
        assert "PPHI" in r.text
        assert "显存温度" in r.text

    @patch("src.web.app._load_rankings", _mock_load_rankings)
    def test_trends(self):
        r = client.get("/trends")
        assert r.status_code == 200
        assert "趋势" in r.text or "trend" in r.text.lower()

    @patch("src.web.app._load_rankings", _mock_load_rankings)
    def test_pain_point_detail_with_inferred(self):
        """详情页 — 有推理数据"""
        r = client.get("/pain-point/1")
        assert r.status_code == 200
        assert "显存温度" in r.text
        assert "推理链" in r.text or "reasoning" in r.text.lower()
        assert "Munger" in r.text or "munger" in r.text

    @patch("src.web.app._load_rankings", _mock_load_rankings)
    def test_pain_point_detail_no_inferred(self):
        """详情页 — 无推理数据"""
        r = client.get("/pain-point/2")
        assert r.status_code == 200
        assert "RTX 5090" in r.text
        assert "尚未推导" in r.text

    @patch("src.web.app._load_rankings", _mock_load_rankings)
    def test_pain_point_detail_not_found(self):
        """详情页 — 不存在的排名"""
        r = client.get("/pain-point/999")
        assert r.status_code == 200  # 返回空页面，不是 404

    def test_history(self):
        r = client.get("/history")
        assert r.status_code == 200
        assert "历史" in r.text or "history" in r.text.lower()

    def test_history_detail_redirect(self):
        """历史详情 — 无 run_date 参数时重定向"""
        r = client.get("/history/detail", follow_redirects=False)
        assert r.status_code in (301, 302, 307)

    def test_admin(self):
        r = client.get("/admin")
        assert r.status_code == 200
        assert "管理" in r.text or "admin" in r.text.lower()

    @patch("src.web.app._load_rankings", _mock_load_rankings)
    def test_report(self):
        r = client.get("/report")
        assert r.status_code == 200
        assert "报告" in r.text or "report" in r.text.lower()
        assert "显存温度" in r.text


class TestAPI:
    """API 端点测试"""

    def test_health(self):
        r = client.get("/api/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["service"] == "GPU-Insight"

    @patch("src.web.app._load_rankings", _mock_load_rankings)
    def test_rankings_api(self):
        r = client.get("/api/rankings")
        assert r.status_code == 200
        data = r.json()
        assert data["total_pain_points"] == 2
        assert len(data["rankings"]) == 2

    @patch("src.web.app._load_rankings", _mock_load_rankings)
    def test_export_csv(self):
        r = client.get("/api/export/csv")
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]
        assert "显存温度" in r.text
