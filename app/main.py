from contextlib import asynccontextmanager

import httpx
import jinja2
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.api.v1.endpoints.ui import ui_router
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logger import setup_logging
from app.core.middleware import LogMiddleware

jinja_env = jinja2.Environment(undefined=jinja2.StrictUndefined)


# 生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化日志
    setup_logging()
    logger.info("Application starting up...")

    # 生产环境安全验证（仅在启用对应组件时校验密码）
    if settings.RUN_MODE == "prod":
        if settings.ENABLE_REDIS and not settings.REDIS_PASSWORD:
            logger.error("❌ 生产环境启用 Redis 必须配置密码，请检查 .env 文件中的 REDIS_PASSWORD")
            raise ValueError("生产环境Redis密码未配置，禁止启动")
        if settings.ENABLE_DB and not settings.DB_PASSWORD:
            logger.error("❌ 生产环境启用 DB 必须配置密码，请检查 .env 文件中的 DB_PASSWORD")
            raise ValueError("生产环境数据库密码未配置，禁止启动")
        logger.info(
            f"✅ 生产环境安全配置验证通过 (ENABLE_DB={settings.ENABLE_DB}, "
            f"ENABLE_REDIS={settings.ENABLE_REDIS})"
        )

    # 针对 LLM 长耗时/流式场景的连接池配置
    limits = httpx.Limits(
        max_keepalive_connections=50,  # 维持的最大空闲连接数，减少频繁 TLS 握手的开销
        max_connections=500,           # 最大并发连接数（结合你的服务器配置及预期 QPS 调整）
        keepalive_expiry=30.0          # 空闲连接保持时长(秒)
    )

    app.state.http_client = httpx.AsyncClient(
        http2=True, 
        timeout=httpx.Timeout(300.0, connect=10.0),
        limits=limits
    )
    logger.info("Stock Analyse Service HTTP/2 Client Initialized.")

    try:
        yield
    finally:              
        await app.state.http_client.aclose()
        logger.info("Stock Analyse Service HTTP/2 Client Closed.")
        logger.info("Application shutting down...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan
)

# CORS 配置：允许本地跨域调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，便于本地开发
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(LogMiddleware)


# ✅ 注册全局异常处理 (建议放在中间件之后，路由之前)
register_exception_handlers(app)

# 静态文件挂载 - 使用项目根目录下的 static 目录
from pathlib import Path
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# 注册路由
app.include_router(api_router, prefix=settings.API_V1_STR)


app.include_router(ui_router, prefix="/ui", tags=["UI"])

@app.get("/")
async def root():
    logger.info("Root endpoint accessed")
    return {"message": "Welcome to Python Web!"}
