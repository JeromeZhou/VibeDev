"""GPU-Insight 报告生成模块 — v2 支持 GPU 标签 + URL 追溯"""

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
        "| # | 痛点 | PPHI | GPU型号 | 厂商 | 来源 | 趋势 |",
        "|---|------|------|---------|------|------|------|",
    ]

    for r in rankings[:10]:
        gpu = r.get("gpu_tags", {})
        models = ", ".join(gpu.get("models", [])) or "-"
        mfrs = ", ".join(gpu.get("manufacturers", [])) or "-"
        sources = ", ".join(r.get("sources", []))
        trend_icon = {"new": "NEW", "accelerating": "UP", "stable": "->", "declining": "DN"}.get(r.get("trend", ""), "")
        lines.append(f"| {r['rank']} | {r['pain_point']} | {r['pphi_score']} | {models} | {mfrs} | {sources} | {trend_icon} |")

    lines.extend(["", "## 痛点详情\n"])
    for r in rankings[:10]:
        gpu = r.get("gpu_tags", {})
        urls = r.get("source_urls", [])
        lines.append(f"### #{r['rank']} {r['pain_point']}\n")
        lines.append(f"- PPHI: {r['pphi_score']} | 分类: {r.get('category', '-')} | 影响: {r.get('affected_users', '-')}")
        if gpu.get("brands"):
            lines.append(f"- GPU品牌: {', '.join(gpu['brands'])}")
        if gpu.get("models"):
            lines.append(f"- GPU型号: {', '.join(gpu['models'])}")
        if gpu.get("manufacturers"):
            lines.append(f"- 板卡厂商: {', '.join(gpu['manufacturers'])}")
        if r.get("evidence"):
            lines.append(f"- 证据: {r['evidence']}")
        if urls:
            lines.append(f"- 原帖链接:")
            for url in urls[:5]:
                lines.append(f"  - [{url[:80]}]({url})")
        if r.get("hidden_need"):
            lines.append(f"- **推理需求**: {r['hidden_need']}（置信度: {r.get('confidence', 0):.0%}）")
        lines.append("")

    lines.extend([
        "---",
        f"*由 GPU-Insight 自动生成*",
    ])

    report_content = "\n".join(lines)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report_content)

    return str(output_file)
