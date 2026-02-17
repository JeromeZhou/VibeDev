"""GPU-Insight 成本追踪器"""

import json
from datetime import datetime
from pathlib import Path


class CostTracker:
    """月度成本追踪和预算告警"""

    def __init__(self, config: dict):
        self.budget = config.get("cost", {}).get("monthly_budget_usd", 80)
        self.thresholds = config.get("cost", {}).get("alert_thresholds", {
            "warning": 0.8, "downgrade": 0.9, "pause": 0.95, "stop": 1.0,
        })
        self.log_path = Path(config.get("paths", {}).get("logs", "logs")) / "cost.log"

    def get_monthly_cost(self) -> float:
        """获取当月累计成本"""
        if not self.log_path.exists():
            return 0.0
        total = 0.0
        current_month = datetime.now().strftime("%Y-%m")
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if entry["timestamp"].startswith(current_month):
                        total += entry.get("cost_usd", 0)
                except (json.JSONDecodeError, KeyError):
                    continue
        return round(total, 4)

    def check_budget(self) -> dict:
        """检查预算状态"""
        cost = self.get_monthly_cost()
        ratio = cost / self.budget if self.budget > 0 else 0
        status = "normal"
        if ratio >= self.thresholds.get("stop", 1.0):
            status = "stop"
        elif ratio >= self.thresholds.get("pause", 0.95):
            status = "pause"
        elif ratio >= self.thresholds.get("downgrade", 0.9):
            status = "downgrade"
        elif ratio >= self.thresholds.get("warning", 0.8):
            status = "warning"
        return {
            "monthly_cost": cost,
            "budget": self.budget,
            "usage_ratio": round(ratio, 4),
            "status": status,
        }

    def enforce_budget(self, llm_client) -> str:
        """执行预算控制策略

        Returns:
            "normal" | "warning" | "downgrade" | "pause" | "stop"
        """
        budget = self.check_budget()
        status = budget["status"]
        ratio = budget["usage_ratio"]

        if status == "warning":
            print(f"[预算警告] 已使用 {ratio*100:.1f}% (${budget['monthly_cost']:.2f}/${budget['budget']})")
        elif status == "downgrade":
            print(f"[预算降级] 已使用 {ratio*100:.1f}%，切换到低成本模型")
            llm_client.downgrade_model()
        elif status == "pause":
            print(f"[预算暂停] 已使用 {ratio*100:.1f}%，跳过非关键步骤（隐藏需求推导）")
        elif status == "stop":
            print(f"[预算停止] 已使用 {ratio*100:.1f}%，停止运行")

        return status
