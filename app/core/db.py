from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, create_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings

# echo=False, 因为我们用 Loguru 接管了日志
engine = create_engine(settings.DATABASE_URL, echo=False)

def get_db():
    with Session(engine) as session:
        yield session


async_engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
    pool_size=20,        # 连接池大小
    max_overflow=10,     # 超出连接池大小时，允许额外创建的连接数
    pool_recycle=3600
)

# 创建异步 Session 工厂
AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    异步数据库依赖
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            # 当业务逻辑正常执行完毕，准备退出依赖时，统一提交事务
            await session.commit()
        except Exception as e:
            # 如果业务逻辑抛出异常，统一回滚，防止脏数据，并维持连接池健康
            await session.rollback()
            raise e
        finally:
            # 可选：关闭 session，但在 async with 块中 SQLAlchemy 会自动处理
            await session.close()