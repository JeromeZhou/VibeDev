"""GPU-Insight 报告生成模块 — v2 支持 GPU 标签 + URL 追溯"""

import json
from datetime import datetime
from pathlib import Path

from .consensus_updater import update_consensus


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
        trend_icon = {"new": "★", "rising": "↑", "stable": "→", "falling": "↓"}.get(r.get("trend", ""), "")
        lines.append(f"| {r['rank']} | {r['pain_point']} | {r['pphi_score']} | {models} | {mfrs} | {sources} | {trend_icon} |")

    lines.extend(["", "## 痛点详情\n"])
    for r in rankings[:10]:
        gpu = r.get("gpu_tags", {})
        urls = r.get("source_urls", [])
        inferred = r.get("inferred_need")

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

        # 展示推理链和 Munger 审查结果
        if inferred:
            hidden_need = inferred.get("hidden_need", "")
            confidence = inferred.get("confidence", 0)
            reasoning_chain = inferred.get("reasoning_chain", [])
            munger_review = inferred.get("munger_review")
            munger_rejected = inferred.get("munger_rejected", False)

            lines.append(f"- **推理需求**: {hidden_need}（置信度: {confidence:.0%}）")

            if reasoning_chain:
                lines.append(f"- **推理链**:")
                for i, step in enumerate(reasoning_chain, 1):
                    lines.append(f"  {i}. {step}")

            if munger_review:
                approved = munger_review.get("approved", False)
                comment = munger_review.get("comment", "")
                rejection_reason = munger_review.get("rejection_reason", "")

                if munger_rejected:
                    lines.append(f"- **Munger 审查**: ❌ 未通过")
                    if rejection_reason:
                        lines.append(f"  - 原因: {rejection_reason}")
                else:
                    lines.append(f"- **Munger 审查**: ✅ 通过")

                if comment:
                    lines.append(f"  - 评价: {comment}")

        lines.append("")

    lines.extend([
        "---",
        f"*由 GPU-Insight 自动生成*",
    ])

    report_content = "\n".join(lines)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report_content)

    return str(output_file)
