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


@app.get("/")
async def dashboard(request: Request):
    """痛点仪表盘"""
    data = _load_rankings()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "data": data,
        "rankings": data.get("rankings", [])[:10],
        "updated_at": data.get("timestamp", "尚未运行"),
    })


@app.get("/trends")
async def trends(request: Request):
    """趋势分析页"""
    data = _load_rankings()
    return templates.TemplateResponse("trends.html", {
        "request": request,
        "rankings": data.get("rankings", []),
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
