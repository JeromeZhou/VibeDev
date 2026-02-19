"""GPU-Insight 周报生成器 — 对比本周与上周排名变化"""

from datetime import datetime, timedelta
from pathlib import Path


def generate_weekly_report(config: dict) -> str | None:
    """生成周报：对比最近 7 天与之前 7 天的 PPHI 排名变化

    Returns:
        报告文件路径，无数据时返回 None
    """
    try:
        from src.utils.db import get_db
    except ImportError:
        print("  [!] DB 模块不可用，跳过周报")
        return None

    now = datetime.now()
    week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    two_weeks_ago = (now - timedelta(days=14)).strftime("%Y-%m-%d")

    with get_db() as conn:
        # 本周数据：最近 7 天内最新一轮
        this_week = conn.execute(
            """SELECT pain_point, pphi_score, category, hidden_need,
                      run_date
               FROM pphi_history
               WHERE run_date >= ?
               ORDER BY pphi_score DESC""",
            (week_ago,)
        ).fetchall()

        # 上周数据：7-14 天前最新一轮
        last_week = conn.execute(
            """SELECT pain_point, pphi_score
               FROM pphi_history
               WHERE run_date >= ? AND run_date < ?
               ORDER BY pphi_score DESC""",
            (two_weeks_ago, week_ago)
        ).fetchall()

        # 本周运行次数
        runs = conn.execute(
            "SELECT COUNT(DISTINCT run_date) as cnt FROM pphi_history WHERE run_date >= ?",
            (week_ago,)
        ).fetchone()

        # 本周新增帖子数
        posts = conn.execute(
            "SELECT COUNT(*) as cnt FROM posts WHERE created_at >= ?",
            (week_ago,)
        ).fetchone()

    if not this_week:
        return None

    # 去重取最高分
    current = {}
    for r in this_week:
        name = r["pain_point"]
        if name not in current or r["pphi_score"] > current[name]["score"]:
            current[name] = {
                "score": r["pphi_score"],
                "category": r["category"] or "",
                "hidden_need": r["hidden_need"] or "",
            }

    previous = {}
    for r in last_week:
        name = r["pain_point"]
        if name not in previous or r["pphi_score"] > previous[name]:
            previous[name] = r["pphi_score"]

    # 排名
    ranked = sorted(current.items(), key=lambda x: x[1]["score"], reverse=True)

    # 变化分析
    new_pains = [name for name, _ in ranked if name not in previous]
    gone_pains = [name for name in previous if name not in current]
    rising = []
    falling = []
    for name, info in ranked:
        if name in previous:
            delta = info["score"] - previous[name]
            if delta > 3:
                rising.append((name, delta))
            elif delta < -3:
                falling.append((name, delta))

    # 生成报告
    date_str = now.strftime("%Y-%m-%d")
    output_dir = Path(config.get("paths", {}).get("reports", "outputs/daily_reports"))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"weekly_{date_str}.md"

    run_count = runs["cnt"] if runs else 0
    post_count = posts["cnt"] if posts else 0

    lines = [
        f"# GPU-Insight 周报 — {date_str}\n",
        f"> 统计周期：{week_ago} ~ {date_str}",
        f"> 运行 {run_count} 轮 · 新增 {post_count} 条帖子\n",
        "## 本周 Top 10\n",
        "| # | 痛点 | PPHI | 分类 | 变化 |",
        "|---|------|------|------|------|",
    ]

    for i, (name, info) in enumerate(ranked[:10], 1):
        if name in previous:
            delta = info["score"] - previous[name]
            change = f"+{delta:.1f} ↑" if delta > 0 else f"{delta:.1f} ↓" if delta < 0 else "→"
        else:
            change = "★ 新"
        lines.append(f"| {i} | {name} | {info['score']:.1f} | {info['category']} | {change} |")

    if new_pains:
        lines.extend(["", f"## 新增痛点（{len(new_pains)} 个）\n"])
        for name in new_pains[:10]:
            score = current[name]["score"]
            lines.append(f"- **{name}** (PPHI {score:.1f})")

    if gone_pains:
        lines.extend(["", f"## 消失痛点（{len(gone_pains)} 个）\n"])
        for name in gone_pains[:10]:
            lines.append(f"- ~~{name}~~ (上周 PPHI {previous[name]:.1f})")

    if rising:
        rising.sort(key=lambda x: x[1], reverse=True)
        lines.extend(["", "## 快速上升\n"])
        for name, delta in rising[:5]:
            lines.append(f"- **{name}** +{delta:.1f}")

    if falling:
        falling.sort(key=lambda x: x[1])
        lines.extend(["", "## 明显下降\n"])
        for name, delta in falling[:5]:
            lines.append(f"- **{name}** {delta:.1f}")

    lines.extend([
        "",
        "---",
        f"*由 GPU-Insight 自动生成 · {now.strftime('%Y-%m-%d %H:%M')}*",
    ])

    report_content = "\n".join(lines)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report_content)

    return str(output_file)
