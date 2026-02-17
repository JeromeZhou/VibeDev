"""GPU-Insight Web 界面 — FastAPI 后端 — UI Designer + Fullstack 协作"""

import json
import csv
import io
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI(title="GPU-Insight", description="显卡用户痛点智能分析系统")

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

RANKINGS_PATH = Path("outputs/pphi_rankings/latest.json")


def _load_rankings() -> dict:
    """加载最新排名数据"""
    if RANKINGS_PATH.exists():
        with open(RANKINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"timestamp": None, "total_pain_points": 0, "rankings": []}


def _get_trend_data() -> dict:
    """从 DB 获取 PPHI 趋势数据"""
    try:
        from src.utils.db import get_db
        conn = get_db()
        rows = conn.execute(
            """SELECT run_date, pain_point, pphi_score
               FROM pphi_history ORDER BY run_date ASC"""
        ).fetchall()
        conn.close()

        if not rows:
            return {"labels": [], "datasets": []}

        # 按日期分组
        dates = sorted(set(r["run_date"] for r in rows))
        # 取最近 10 次运行
        dates = dates[-10:]

        # 找出出现频率最高的 top 5 痛点
        from collections import Counter
        pp_counter = Counter(r["pain_point"] for r in rows if r["run_date"] in dates)
        top_pps = [pp for pp, _ in pp_counter.most_common(5)]

        colors = ["#F44336", "#FF9800", "#1976D2", "#4CAF50", "#9C27B0"]
        datasets = []
        for i, pp in enumerate(top_pps):
            scores = []
            for d in dates:
                score = next((r["pphi_score"] for r in rows if r["run_date"] == d and r["pain_point"] == pp), None)
                scores.append(score)
            datasets.append({
                "label": pp[:15],
                "data": scores,
                "borderColor": colors[i % len(colors)],
            })

        labels = [d[5:] for d in dates]  # MM-DD HH:MM
        return {"labels": labels, "datasets": datasets}
    except Exception:
        return {"labels": [], "datasets": []}


def _get_source_distribution() -> dict:
    """从 DB 获取来源分布"""
    try:
        from src.utils.db import get_db
        conn = get_db()
        rows = conn.execute(
            "SELECT source, COUNT(*) as cnt FROM posts GROUP BY source"
        ).fetchall()
        conn.close()
        labels = [r["source"] for r in rows]
        data = [r["cnt"] for r in rows]
        colors = {"reddit": "#FF5722", "nga": "#4CAF50", "tieba": "#FF9800", "chiphell": "#1976D2"}
        bg = [colors.get(l, "#9C27B0") for l in labels]
        return {"labels": labels, "data": data, "backgroundColor": bg}
    except Exception:
        return {"labels": [], "data": [], "backgroundColor": []}


def _get_cumulative_stats() -> dict:
    """从 DB 获取累计统计"""
    try:
        from src.utils.db import get_db
        conn = get_db()
        total_posts = conn.execute("SELECT COUNT(*) as c FROM posts").fetchone()["c"]
        total_runs = conn.execute("SELECT COUNT(DISTINCT run_date) as c FROM pphi_history").fetchone()["c"]
        total_pains = conn.execute("SELECT COUNT(DISTINCT pain_point) as c FROM pphi_history").fetchone()["c"]
        total_sources = conn.execute("SELECT COUNT(DISTINCT source) as c FROM posts").fetchone()["c"]
        conn.close()
        return {"total_posts": total_posts, "total_runs": total_runs, "total_pains": total_pains, "total_sources": total_sources}
    except Exception:
        return {"total_posts": 0, "total_runs": 0, "total_pains": 0, "total_sources": 0}


def _get_run_delta() -> dict:
    """对比最新两轮 pphi_history，计算新增痛点数和新增 GPU 型号数"""
    try:
        from src.utils.db import get_db
        conn = get_db()
        dates = conn.execute(
            "SELECT DISTINCT run_date FROM pphi_history ORDER BY run_date DESC LIMIT 2"
        ).fetchall()
        if len(dates) < 2:
            conn.close()
            return {"new_pains": 0, "new_models": 0, "prev_date": ""}

        curr_date, prev_date = dates[0]["run_date"], dates[1]["run_date"]

        # Current run pain points and models
        curr_rows = conn.execute(
            "SELECT pain_point, gpu_tags FROM pphi_history WHERE run_date = ?", (curr_date,)
        ).fetchall()
        prev_rows = conn.execute(
            "SELECT pain_point, gpu_tags FROM pphi_history WHERE run_date = ?", (prev_date,)
        ).fetchall()
        conn.close()

        curr_pains = set(r["pain_point"] for r in curr_rows)
        prev_pains = set(r["pain_point"] for r in prev_rows)
        new_pains = len(curr_pains - prev_pains)

        curr_models = set()
        for r in curr_rows:
            tags = json.loads(r["gpu_tags"]) if r["gpu_tags"] else {}
            curr_models.update(tags.get("models", []))
        prev_models = set()
        for r in prev_rows:
            tags = json.loads(r["gpu_tags"]) if r["gpu_tags"] else {}
            prev_models.update(tags.get("models", []))
        new_models = len(curr_models - prev_models)

        return {"new_pains": new_pains, "new_models": new_models, "prev_date": prev_date}
    except Exception:
        return {"new_pains": 0, "new_models": 0, "prev_date": ""}


def _get_pain_trend(pain_point_name: str) -> dict:
    """获取单个痛点的 PPHI 历史趋势"""
    if not pain_point_name:
        return {"labels": [], "scores": [], "mentions": []}
    try:
        from src.utils.db import get_db
        conn = get_db()
        # 模糊匹配：去掉括号后的分类标签进行匹配
        import re
        base_name = re.sub(r'[（(][^）)]*[）)]', '', pain_point_name).strip()
        rows = conn.execute(
            """SELECT run_date, pphi_score, mentions
               FROM pphi_history
               WHERE pain_point LIKE ?
               ORDER BY run_date ASC""",
            (f"%{base_name}%",)
        ).fetchall()
        conn.close()

        # 每个 run_date 取最高分（可能有多条匹配）
        by_date = {}
        for r in rows:
            d = r["run_date"]
            if d not in by_date or r["pphi_score"] > by_date[d]["score"]:
                by_date[d] = {"score": r["pphi_score"], "mentions": r["mentions"]}

        dates = sorted(by_date.keys())[-12:]  # 最近 12 轮
        return {
            "labels": [d[5:] for d in dates],  # MM-DD HH:MM
            "scores": [by_date[d]["score"] for d in dates],
            "mentions": [by_date[d]["mentions"] for d in dates],
        }
    except Exception:
        return {"labels": [], "scores": [], "mentions": []}


@app.get("/")
async def dashboard(request: Request):
    """痛点仪表盘"""
    data = _load_rankings()
    stats = _get_cumulative_stats()

    # 计算本轮新增统计（对比最新两轮 pphi_history）
    delta = _get_run_delta()

    return templates.TemplateResponse("index.html", {
        "request": request,
        "data": data,
        "rankings": data.get("rankings", []),
        "updated_at": data.get("timestamp", "尚未运行"),
        "stats": stats,
        "delta": delta,
    })


@app.get("/trends")
async def trends(request: Request):
    """趋势分析页"""
    data = _load_rankings()
    return templates.TemplateResponse("trends.html", {
        "request": request,
        "rankings": data.get("rankings", []),
        "trend_data_json": json.dumps(_get_trend_data(), ensure_ascii=False),
        "source_data_json": json.dumps(_get_source_distribution(), ensure_ascii=False),
        "evolution_data_json": json.dumps(_get_evolution_data(), ensure_ascii=False),
    })


def _load_source_posts(pain_point: dict) -> list[dict]:
    """根据痛点的 source_urls 从 DB 加载关联原帖"""
    if not pain_point:
        return []
    source_urls = pain_point.get("source_urls", [])
    if not source_urls:
        return []
    try:
        from src.utils.db import get_db
        conn = get_db()
        posts = []
        for url in source_urls[:20]:
            row = conn.execute(
                "SELECT id, source, title, url, replies, likes, timestamp FROM posts WHERE url = ?",
                (url,)
            ).fetchone()
            if row:
                posts.append(dict(row))
        # 如果 URL 匹配不到，尝试用 post id 前缀匹配
        if not posts:
            for url in source_urls[:20]:
                # 从 URL 提取可能的 ID 片段
                slug = url.rstrip("/").split("/")[-1]
                rows = conn.execute(
                    "SELECT id, source, title, url, replies, likes, timestamp FROM posts WHERE id LIKE ? LIMIT 1",
                    (f"%{slug[:30]}%",)
                ).fetchall()
                posts.extend(dict(r) for r in rows)
        conn.close()
        # 去重
        seen = set()
        unique = []
        for p in posts:
            if p["id"] not in seen:
                seen.add(p["id"])
                unique.append(p)
        return unique
    except Exception:
        return []


@app.get("/pain-point/{rank}")
async def pain_point_detail(request: Request, rank: int):
    """痛点详情页"""
    data = _load_rankings()
    rankings = data.get("rankings", [])
    pain_point = next((r for r in rankings if r.get("rank") == rank), {})
    posts = _load_source_posts(pain_point)

    # 获取该痛点的 PPHI 历史趋势
    trend_data = _get_pain_trend(pain_point.get("pain_point", ""))

    return templates.TemplateResponse("details.html", {
        "request": request,
        "pain_point": pain_point,
        "posts": posts,
        "trend_data_json": json.dumps(trend_data, ensure_ascii=False),
    })


@app.get("/api/rankings")
async def api_rankings():
    """API: 获取排名数据"""
    return JSONResponse(_load_rankings())


@app.get("/api/health")
async def health():
    """健康检查"""
    return {"status": "ok", "service": "GPU-Insight"}


@app.get("/report")
async def report(request: Request):
    """打印友好的分析报告页（浏览器 Ctrl+P 导出 PDF）"""
    data = _load_rankings()
    stats = _get_cumulative_stats()

    # 数据源分布（带颜色）
    source_colors = {
        'reddit': '#e5534b', 'nga': '#5ec49e', 'tieba': '#d4a04a',
        'chiphell': '#5b8def', 'bilibili': '#fb7299', 'bili': '#fb7299',
        'v2ex': '#778087', 'mydrivers': '#1e88e5', 'techpowerup': '#ff6f00',
    }
    source_raw = _get_source_distribution()
    source_dist = []
    for name, count in zip(source_raw.get("labels", []), source_raw.get("data", [])):
        source_dist.append({
            "name": name,
            "count": count,
            "color": source_colors.get(name, "#5b8def"),
        })

    return templates.TemplateResponse("report.html", {
        "request": request,
        "timestamp": data.get("timestamp", ""),
        "total_pain_points": data.get("total_pain_points", 0),
        "rankings": data.get("rankings", []),
        "stats": stats,
        "source_dist": source_dist,
    })


@app.get("/history")
async def history(request: Request):
    """历史轮次浏览"""
    try:
        from src.utils.db import get_db
        conn = get_db()
        # 获取所有运行轮次
        runs = conn.execute(
            """SELECT run_date, COUNT(*) as pain_count,
                      ROUND(MAX(pphi_score), 1) as top_pphi,
                      GROUP_CONCAT(DISTINCT pain_point) as pain_list
               FROM pphi_history
               GROUP BY run_date
               ORDER BY run_date DESC"""
        ).fetchall()
        conn.close()
        run_list = []
        for r in runs:
            run_list.append({
                "run_date": r["run_date"],
                "pain_count": r["pain_count"],
                "top_pphi": r["top_pphi"],
                "pain_list": (r["pain_list"] or "")[:100],
            })
    except Exception:
        run_list = []

    return templates.TemplateResponse("history.html", {
        "request": request,
        "runs": run_list,
    })


@app.get("/history/detail")
async def history_detail(request: Request, run_date: str = ""):
    """某一轮的详细排名"""
    if not run_date:
        from starlette.responses import RedirectResponse
        return RedirectResponse("/history")
    try:
        from src.utils.db import get_db
        conn = get_db()
        rows = conn.execute(
            """SELECT rank, pain_point, pphi_score, mentions, gpu_tags, source_urls, hidden_need
               FROM pphi_history
               WHERE run_date = ?
               ORDER BY rank ASC""",
            (run_date,)
        ).fetchall()
        conn.close()
        rankings = []
        for r in rows:
            rankings.append({
                "rank": r["rank"],
                "pain_point": r["pain_point"],
                "pphi_score": r["pphi_score"],
                "mentions": r["mentions"],
                "gpu_tags": json.loads(r["gpu_tags"]) if r["gpu_tags"] else {},
                "source_urls": json.loads(r["source_urls"]) if r["source_urls"] else [],
                "hidden_need": r["hidden_need"] or "",
                "trend": "stable",
            })
    except Exception:
        rankings = []

    return templates.TemplateResponse("history_detail.html", {
        "request": request,
        "run_date": run_date,
        "rankings": rankings,
    })


@app.get("/api/export/csv")
async def export_csv():
    """导出当前排名为 CSV"""
    data = _load_rankings()
    rankings = data.get("rankings", [])

    output = io.StringIO()
    output.write('\ufeff')  # BOM for Excel UTF-8
    writer = csv.writer(output)
    writer.writerow([
        "排名", "痛点", "PPHI", "讨论数", "类别", "影响范围",
        "GPU型号", "数据源", "隐藏需求", "Munger评级", "置信度", "证据"
    ])
    for r in rankings:
        gpu_models = ", ".join(r.get("gpu_tags", {}).get("models", []))
        sources = ", ".join(r.get("sources", []))
        inferred = r.get("inferred_need") or {}
        munger = inferred.get("munger_review", {}) or {}
        writer.writerow([
            r.get("rank", ""),
            r.get("pain_point", ""),
            r.get("pphi_score", ""),
            r.get("mentions", ""),
            r.get("category", ""),
            r.get("affected_users", ""),
            gpu_models,
            sources,
            r.get("hidden_need", ""),
            munger.get("quality_level", ""),
            inferred.get("confidence", ""),
            r.get("evidence", ""),
        ])

    output.seek(0)
    ts = (data.get("timestamp") or "export")[:10]
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=gpu-insight-{ts}.csv"}
    )


def _get_evolution_data() -> dict:
    """获取痛点排名演变数据（Bump Chart 用）"""
    try:
        from src.utils.db import get_db
        conn = get_db()
        rows = conn.execute(
            """SELECT run_date, pain_point, rank, pphi_score
               FROM pphi_history
               ORDER BY run_date ASC, rank ASC"""
        ).fetchall()
        conn.close()

        if not rows:
            return {"dates": [], "series": []}

        dates = sorted(set(r["run_date"] for r in rows))
        dates = dates[-10:]  # 最近 10 轮

        # 找出在这些轮次中出现最多的 Top 8 痛点
        from collections import Counter
        pp_counter = Counter(
            r["pain_point"] for r in rows if r["run_date"] in dates
        )
        top_pps = [pp for pp, _ in pp_counter.most_common(8)]

        colors = [
            "#5b8def", "#9d8abf", "#5ec49e", "#d4a04a",
            "#e5534b", "#fb7299", "#778087", "#1e88e5"
        ]

        series = []
        for i, pp in enumerate(top_pps):
            ranks = []
            for d in dates:
                rank = next(
                    (r["rank"] for r in rows if r["run_date"] == d and r["pain_point"] == pp),
                    None
                )
                ranks.append(rank)
            series.append({
                "name": pp[:20],
                "data": ranks,
                "color": colors[i % len(colors)],
            })

        labels = [d[5:] for d in dates]  # MM-DD HH:MM
        return {"dates": labels, "series": series}
    except Exception:
        return {"dates": [], "series": []}
