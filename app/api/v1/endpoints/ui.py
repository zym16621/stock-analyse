from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

ui_router = APIRouter(tags=["UI"])

@ui_router.get("/prompt-studio", summary="Prompt 可视化工作台", include_in_schema=False)
async def serve_prompt_studio():
    """
    返回静态的前端 HTML 页面。
    注意：include_in_schema=False 可以让这个接口不在 Swagger UI (docs) 里显示，
    保持纯净的 API 文档。
    """
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    html_path = base_dir / "static" / "index.html"

    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Frontend UI not found. Please check app/static/index.html")

    return FileResponse(html_path)