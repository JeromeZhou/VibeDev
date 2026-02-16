"""GPU-Insight Web 界面 — FastAPI 后端"""

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


@app.get("/api/rankings")
async def api_rankings():
    """API: 获取排名数据"""
    return JSONResponse(_load_rankings())


@app.get("/api/health")
async def health():
    """健康检查"""
    return {"status": "ok", "service": "GPU-Insight"}
