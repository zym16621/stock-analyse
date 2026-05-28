from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

ui_router = APIRouter(tags=["UI"])

# 项目根目录 (app 目录的父目录)
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent


@ui_router.get("/investment-dashboard", summary="量化定投数据看板", include_in_schema=False)
async def serve_investment_dashboard():
    """
    返回量化定投数据看板 HTML 页面。
    访问地址: http://localhost:8168/ui/investment-dashboard
    """
    html_path = BASE_DIR / "app" / "static" / "quant_investment_dashboard.html"

    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Dashboard UI not found. Please check static/quant_investment_dashboard.html")

    return FileResponse(html_path)