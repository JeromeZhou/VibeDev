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
        self.log_dir = Path(config.get("paths", {}).get("logs", "logs"))
        self.log_path = self.log_dir / "cost.log"
        self._rotate_if_needed()

    def _rotate_if_needed(self):
        """月初自动轮转：将上月日志归档，清空当月日志"""
        if not self.log_path.exists():
            return
        try:
            current_month = datetime.now().strftime("%Y-%m")
            # 读取第一行判断日志起始月份
            with open(self.log_path, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
            if not first_line:
                return
            first_entry = json.loads(first_line)
            first_month = first_entry["timestamp"][:7]  # "YYYY-MM"

            # 如果日志包含上月数据，归档非当月条目
            if first_month != current_month:
                current_lines = []
                archive_lines = []
                with open(self.log_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            if entry["timestamp"].startswith(current_month):
                                current_lines.append(line)
                            else:
                                archive_lines.append(line)
                        except (json.JSONDecodeError, KeyError):
                            archive_lines.append(line)

                # 归档旧数据
                if archive_lines:
                    archive_path = self.log_dir / f"cost_{first_month}.log"
                    with open(archive_path, "a", encoding="utf-8") as f:
                        f.write("\n".join(archive_lines) + "\n")

                # 只保留当月数据
                with open(self.log_path, "w", encoding="utf-8") as f:
                    if current_lines:
                        f.write("\n".join(current_lines) + "\n")
                print(f"  [成本] 归档 {len(archive_lines)} 条旧日志 → cost_{first_month}.log")
        except Exception:
            pass  # 轮转失败不影响正常运行

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
