"""GPU-Insight 报告生成模块"""

import json
from datetime import datetime
from pathlib import Path


def generate_report(rankings: list[dict], config: dict) -> str:
    """生成每日 Markdown 报告"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_dir = Path(config.get("paths", {}).get("reports", "outputs/daily_reports"))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{date_str}.md"

    lines = [
        f"# GPU-Insight 每日报告 — {date_str}\n",
        f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n",
        "## Top 10 痛点排名\n",
        "| # | 痛点 | PPHI | 讨论量 | 来源 | 趋势 |",
        "|---|------|------|--------|------|------|",
    ]

    for r in rankings[:10]:
        sources = ", ".join(r.get("sources", []))
        trend_icon = {"new": "🆕", "accelerating": "📈", "stable": "➡️", "declining": "📉"}.get(r.get("trend", ""), "")
        lines.append(f"| {r['rank']} | {r['pain_point']} | {r['pphi_score']} | {r.get('mentions', 0)} | {sources} | {trend_icon} {r.get('trend', '')} |")

    lines.extend([
        "",
        "## 隐藏需求发现\n",
    ])
    for r in rankings[:5]:
        if r.get("hidden_need"):
            lines.append(f"- **{r['pain_point']}** → {r['hidden_need']}（置信度: {r.get('confidence', 0):.0%}）")

    lines.extend([
        "",
        "---",
        f"*由 GPU-Insight 自动生成*",
    ])

    report_content = "\n".join(lines)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report_content)

    return str(output_file)
