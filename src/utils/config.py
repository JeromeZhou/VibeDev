"""GPU-Insight 配置管理"""

import yaml
from datetime import datetime
from pathlib import Path


def load_config(config_path: str = "config/config.yaml") -> dict:
    """加载主配置文件"""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_enabled_sources(config: dict) -> dict:
    """获取已启用的数据源（支持时间感知）"""
    hour = datetime.now().hour
    enabled = {}
    for name, src in config.get("sources", {}).items():
        if not src.get("enabled", False):
            # 时间感知：daytime_only 的源在 8:00-22:00 自动启用
            if src.get("daytime_only", False) and 8 <= hour <= 22:
                enabled[name] = src
            continue
        enabled[name] = src
    return enabled


def get_pphi_weights(config: dict) -> dict:
    """获取 PPHI 权重配置（5 维模型）"""
    return config.get("pphi", {}).get("weights", {
        "frequency": 0.30,
        "source_quality": 0.20,
        "interaction": 0.15,
        "cross_platform": 0.15,
        "freshness": 0.20,
    })
