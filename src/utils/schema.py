"""GPU-Insight 数据 Schema 定义 — Data Engineer 产出"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
import json


@dataclass
class RawPost:
    """原始帖子数据"""
    id: str
    source: str
    title: str
    content: str
    url: str = ""
    author_hash: str = ""
    replies: int = 0
    likes: int = 0
    language: str = "zh-CN"
    timestamp: str = ""
    _scraped_at: str = ""
    _source: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass
class PainPoint:
    """提取的痛点"""
    pain_point: str
    category: str  # 性能|价格|散热|驱动|生态|显存|功耗|其他
    emotion_intensity: float  # 0.0-1.0
    summary: str = ""
    _source: str = ""
    _post_id: str = ""
    evidence_count: int = 0
    first_seen: str = ""
    trend: str = "new"  # new|rising|stable|declining

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class HiddenNeed:
    """推导的隐藏需求"""
    pain_point: str
    hidden_need: str
    reasoning_chain: list[str] = field(default_factory=list)
    confidence: float = 0.0
    category: str = "功能需求"  # 功能需求|情感需求|社会需求
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CouncilReview:
    """Expert Council 评审结果"""
    hidden_need: str
    approved: bool = False
    adjusted_confidence: float = 0.0
    hardware_assessment: str = ""
    product_assessment: str = ""
    data_assessment: str = ""
    concerns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PPHIRanking:
    """PPHI 排名条目"""
    rank: int
    pain_point: str
    pphi_score: float
    mentions: int = 0
    sources: list[str] = field(default_factory=list)
    hidden_need: str = ""
    confidence: float = 0.0
    trend: str = "new"
    change: str = ""
    flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
