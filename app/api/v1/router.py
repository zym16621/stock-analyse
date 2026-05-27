from fastapi import APIRouter

from app.core.config import settings

api_router = APIRouter()


if settings.RUN_MODE in ("local"):
    from app.api.v1.endpoints import code_generate

    api_router.include_router(
        code_generate.router, 
        prefix="/code_generate",
        tags=["code_generate"]
    )
