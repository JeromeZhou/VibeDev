"""GPU-Insight 共识自动更新器"""

from datetime import datetime
from pathlib import Path


def update_consensus(rankings: list, cost_info: dict, config: dict):
    """自动更新 memories/consensus.md 的 Top 痛点和成本追踪

    Args:
        rankings: PPHI 排名列表
        cost_info: 成本信息 {"monthly_cost": float, "budget": float, "round_cost": float, "round_tokens": int}
        config: 配置字典
    """
    consensus_path = Path("memories/consensus.md")

    if not consensus_path.exists():
        print(f"  [!] {consensus_path} 不存在，跳过共识更新")
        return

    # 读取现有内容
    with open(consensus_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # 生成新的 Top 痛点部分
    top_section = _generate_top_section(rankings)

    # 生成新的成本追踪部分
    cost_section = _generate_cost_section(cost_info)

    # 更新时间戳
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 替换相应部分
    new_lines = []
    skip_until = None

    for i, line in enumerate(lines):
        # 更新时间戳
        if line.startswith("> 最后更新："):
            new_lines.append(f"> 最后更新：{timestamp}\n")
            continue

        # 替换 Top 痛点部分
        if line.startswith("### Top 痛点"):
            new_lines.append(line)
            new_lines.extend(top_section)
            skip_until = "### 已验证的隐藏需求"
            continue

        # 替换成本追踪部分
        if line.startswith("## 成本追踪"):
            new_lines.append(line)
            new_lines.extend(cost_section)
            skip_until = "## 开发进度"
            continue

        # 跳过旧内容
        if skip_until:
            if line.startswith(skip_until):
                skip_until = None
                new_lines.append(line)
            continue

        new_lines.append(line)

    # 写回文件
    with open(consensus_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    print(f"  已更新 {consensus_path}")


def _generate_top_section(rankings: list) -> list:
    """生成 Top 痛点部分"""
    lines = []
    top_n = min(5, len(rankings))

    for i, r in enumerate(rankings[:top_n], 1):
        gpu_models = ", ".join(r.get("gpu_tags", {}).get("models", [])) or "通用"
        pphi = r["pphi_score"]
        pain = r["pain_point"]
        need = r.get("hidden_need", "")

        if need:
            lines.append(f"{i}. {pain} — {gpu_models}（PPHI {pphi:.1f}）→ 需求：{need}\n")
        else:
            lines.append(f"{i}. {pain} — {gpu_models}（PPHI {pphi:.1f}）\n")

    lines.append("\n")
    return lines


def _generate_cost_section(cost_info: dict) -> list:
    """生成成本追踪部分"""
    lines = []
    round_cost = cost_info.get("round_cost", 0)
    monthly_cost = cost_info.get("monthly_cost", 0)
    budget = cost_info.get("budget", 80)
    remaining = budget - monthly_cost

    lines.append(f"- 本轮消耗：${round_cost:.4f}\n")
    lines.append(f"- 月度累计：${monthly_cost:.2f}\n")
    lines.append(f"- 预算剩余：${remaining:.2f} / ${budget}\n")
    lines.append("\n")

    return lines
