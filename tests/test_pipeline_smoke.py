"""GPU-Insight Pipeline 端到端冒烟测试 — 验证最终输出不为空"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


def _mock_scrape_all_forums(config, skip_sources=None):
    """模拟抓取：返回 3 条假帖子"""
    return [
        {
            "id": "smoke_reddit_1",
            "source": "reddit",
            "title": "RTX 5090 overheating at 95C under load",
            "content": "My RTX 5090 FE reaches 95C within minutes of gaming. Thermal paste reapplication didn't help.",
            "url": "https://reddit.com/r/nvidia/smoke1",
            "replies": 15,
            "likes": 42,
            "timestamp": "2026-02-19T10:00:00",
        },
        {
            "id": "smoke_nga_1",
            "source": "nga",
            "title": "RTX 5090 显存温度过高 散热改造记录",
            "content": "显存温度长期95度以上，拆开换了散热垫才降到85度，这做工太差了",
            "url": "https://nga.cn/read.php?tid=smoke1",
            "replies": 8,
            "likes": 20,
            "timestamp": "2026-02-19T11:00:00",
        },
        {
            "id": "smoke_bili_1",
            "source": "bilibili",
            "title": "RX 9070 XT 驱动崩溃蓝屏问题",
            "content": "装了最新驱动后玩游戏频繁蓝屏，回退旧版本才好",
            "url": "https://bilibili.com/video/smoke1",
            "replies": 5,
            "likes": 10,
            "timestamp": "2026-02-19T12:00:00",
        },
    ]


def _mock_llm_chat(self, messages, **kwargs):
    """模拟 LLM 返回"""
    user_msg = messages[-1]["content"] if messages else ""

    # AI 相关性过滤
    if "相关性" in user_msg or "relevance" in user_msg.lower():
        return '{"class": 1, "reason": "GPU相关讨论"}'

    # 漏斗 L2
    if "pain_signal" in user_msg or "痛点信号" in user_msg:
        return '{"has_pain": true, "signal": "温度过高"}'

    # 痛点提取
    if "痛点" in user_msg and "提取" in user_msg:
        return json.dumps([{
            "pain_point": "RTX 5090显存温度过高需要拆解改造",
            "category": "散热",
            "emotion_intensity": 0.8,
            "evidence": "显存温度95度",
            "affected_users": "广泛",
        }], ensure_ascii=False)

    # 语义去重
    if "去重" in user_msg or "合并" in user_msg or "dedup" in user_msg.lower():
        return json.dumps([{
            "canonical": "RTX 5090显存温度过高需要拆解改造",
            "duplicates": [],
        }], ensure_ascii=False)

    # 隐藏需求推导
    if "隐藏需求" in user_msg or "hidden" in user_msg.lower():
        return json.dumps([{
            "pain_point": "RTX 5090显存温度过高需要拆解改造",
            "hidden_need": "需要出厂即具备高效显存散热的显卡设计",
            "confidence": 0.75,
            "reasoning_chain": ["显存温度是核心痛点", "用户被迫自行改造说明出厂设计不足"],
        }], ensure_ascii=False)

    # Munger 审查
    if "munger" in user_msg.lower() or "反向" in user_msg or "devil" in user_msg.lower():
        return json.dumps([{
            "pain_point": "RTX 5090显存温度过高需要��解改造",
            "hidden_need": "需要出厂即具备高效显存散热的显卡设计",
            "approved": True,
            "quality_level": "strong",
            "comment": "多平台证据充分",
        }], ensure_ascii=False)

    return "{}"


class TestPipelineSmoke:
    """Pipeline 端到端冒烟测试"""

    def test_rankings_output_not_empty(self, tmp_path):
        """验证 pipeline 产出非空排名"""
        from src.utils.config import load_config
        config = load_config("config/config.yaml")

        # 模拟抓取
        posts = _mock_scrape_all_forums(config)
        assert len(posts) == 3

        # 清洗
        from src.cleaners import clean_data
        cleaned = clean_data(posts, config)
        assert len(cleaned) > 0, "清洗后不应为空"

        # GPU 标签
        from src.utils.gpu_tagger import tag_posts
        tagged = tag_posts(cleaned)
        gpu_count = sum(1 for p in tagged if p.get("_gpu_tags", {}).get("models"))
        assert gpu_count > 0, "应识别到 GPU 型号"

        # PPHI 排名（用历史数据 + 当前模拟数据）
        from src.rankers import calculate_pphi
        from src.analyzers import merge_pain_insights

        # 构造最小 PainInsight
        insights = [{
            "pain_point": "RTX 5090显存温度过高需要拆解改造",
            "category": "散热",
            "source_post_ids": ["smoke_reddit_1", "smoke_nga_1"],
            "source_urls": ["https://reddit.com/r/nvidia/smoke1"],
            "gpu_tags": {"brands": ["NVIDIA"], "models": ["RTX 5090"], "series": ["RTX 50"], "manufacturers": []},
            "evidence": "显存温度95度",
            "emotion_intensity": 0.8,
            "affected_users": "广泛",
            "inferred_need": {
                "hidden_need": "需要出厂即具备高效显存散热的显卡设计",
                "confidence": 0.75,
                "reasoning_chain": ["显存温度是核心痛点"],
                "munger_review": {"quality_level": "strong", "comment": "ok"},
            },
            "total_replies": 23,
            "total_likes": 62,
            "earliest_timestamp": "2026-02-19T10:00:00",
        }]

        rankings = calculate_pphi(insights, config)
        assert len(rankings) > 0, "排名不应为空"

        # 验证排名结构完整
        r = rankings[0]
        assert r.get("pain_point"), "痛点名称不应为空"
        assert r.get("pphi_score", 0) > 0, "PPHI 分数应大于 0"
        assert r.get("rank") == 1, "第一名 rank 应为 1"
        assert r.get("quality_tier") in ("gold", "silver", "bronze"), "应有质量分层"

    def test_latest_json_structure(self):
        """验证 latest.json 结构（如果存在）"""
        path = Path("outputs/pphi_rankings/latest.json")
        if not path.exists():
            pytest.skip("latest.json 不存在，跳过")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "timestamp" in data, "缺少 timestamp"
        assert "total_pain_points" in data, "缺少 total_pain_points"
        assert "rankings" in data, "缺少 rankings"

        if data["rankings"]:
            r = data["rankings"][0]
            assert "pain_point" in r, "排名项缺少 pain_point"
            assert "pphi_score" in r, "排名项缺少 pphi_score"
            assert "rank" in r, "排名项缺少 rank"
            assert "gpu_tags" in r, "排名项缺少 gpu_tags"
