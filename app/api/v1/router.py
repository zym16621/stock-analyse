from fastapi import APIRouter

from app.core.config import settings

api_router = APIRouter()


# 投资快照路由（始终启用）
from app.api.v1.endpoints import investment

api_router.include_router(
    investment.router,
    prefix="/investment",
    tags=["investment"],
)


if settings.RUN_MODE in ("local"):
    from app.api.v1.endpoints import code_generate

    api_router.include_router(
        code_generate.router,
        prefix="/code_generate",
        tags=["code_generate"]
    )
