"""GPU-Insight Web 界面 — FastAPI 后端 — UI Designer + Fullstack 协作"""

import json
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse

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
        conn.close()
        return {"total_posts": total_posts, "total_runs": total_runs, "total_pains": total_pains}
    except Exception:
        return {"total_posts": 0, "total_runs": 0, "total_pains": 0}


@app.get("/")
async def dashboard(request: Request):
    """痛点仪表盘"""
    data = _load_rankings()
    stats = _get_cumulative_stats()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "data": data,
        "rankings": data.get("rankings", [])[:10],
        "updated_at": data.get("timestamp", "尚未运行"),
        "stats": stats,
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
    })


@app.get("/pain-point/{rank}")
async def pain_point_detail(request: Request, rank: int):
    """痛点详情页"""
    data = _load_rankings()
    rankings = data.get("rankings", [])
    pain_point = next((r for r in rankings if r.get("rank") == rank), {})
    return templates.TemplateResponse("details.html", {
        "request": request,
        "pain_point": pain_point,
        "posts": [],  # TODO: 从 data/processed 加载关联讨论
    })


@app.get("/api/rankings")
async def api_rankings():
    """API: 获取排名数据"""
    return JSONResponse(_load_rankings())


@app.get("/api/health")
async def health():
    """健康检查"""
    return {"status": "ok", "service": "GPU-Insight"}
