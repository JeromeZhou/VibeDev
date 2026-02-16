"""GPU-Insight 统一错误处理 — Architect 产出"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from functools import wraps

# 配置日志
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("gpu-insight")
logger.setLevel(logging.DEBUG)

# 文件 handler
fh = logging.FileHandler(
    LOG_DIR / f"gpu-insight_{datetime.now().strftime('%Y-%m-%d')}.log",
    encoding="utf-8",
)
fh.setLevel(logging.DEBUG)
fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

# 控制台 handler
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))

logger.addHandler(fh)
logger.addHandler(ch)


class PipelineError(Exception):
    """Pipeline 阶段错误"""
    def __init__(self, stage: str, message: str, recoverable: bool = True):
        self.stage = stage
        self.recoverable = recoverable
        super().__init__(f"[{stage}] {message}")


class ScraperError(PipelineError):
    """爬虫错误"""
    def __init__(self, source: str, message: str):
        super().__init__(f"Scraper/{source}", message, recoverable=True)


class LLMError(PipelineError):
    """LLM 调用错误"""
    def __init__(self, model: str, message: str):
        super().__init__(f"LLM/{model}", message, recoverable=True)


class BudgetError(PipelineError):
    """预算超标错误"""
    def __init__(self, message: str):
        super().__init__("Budget", message, recoverable=False)


def safe_stage(stage_name: str):
    """装饰器：安全执行 pipeline 阶段，失败时记录日志并继续"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                logger.info(f"[{stage_name}] 开始...")
                result = func(*args, **kwargs)
                logger.info(f"[{stage_name}] 完成")
                return result
            except BudgetError:
                raise  # 预算错误不可恢复
            except PipelineError as e:
                logger.warning(f"[{stage_name}] 可恢复错误: {e}")
                if not e.recoverable:
                    raise
                return None
            except Exception as e:
                logger.error(f"[{stage_name}] 未预期错误: {e}", exc_info=True)
                return None
        return wrapper
    return decorator
