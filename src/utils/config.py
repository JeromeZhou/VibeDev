"""GPU-Insight 配置管理"""

import yaml
from pathlib import Path


def load_config(config_path: str = "config/config.yaml") -> dict:
    """加载主配置文件"""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_enabled_sources(config: dict) -> dict:
    """获取已启用的数据源"""
    return {
        name: src
        for name, src in config.get("sources", {}).items()
        if src.get("enabled", False)
    }


def get_pphi_weights(config: dict) -> dict:
    """获取 PPHI 权重配置"""
    return config.get("pphi", {}).get("weights", {
        "frequency": 0.3,
        "source_quality": 0.4,
        "interaction": 0.2,
        "time_decay": 0.1,
    })
