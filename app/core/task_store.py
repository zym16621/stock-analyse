import json
from datetime import datetime
from typing import Any, Dict, Optional

import redis
import redis.asyncio as aioredis  # 异步客户端
from loguru import logger

from app.core.config import settings

# =========================================================
# 客户端初始化
# =========================================================

# 异步客户端
async_pool = aioredis.ConnectionPool(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    password=settings.REDIS_PASSWORD,
    db=settings.REDIS_DB,
    decode_responses=True,
    max_connections=100,      # 限制最大连接数，防止耗尽资源
    socket_timeout=5.0        # 防止网络抖动导致协程死锁
)
redis_async = aioredis.Redis(connection_pool=async_pool)


# SSE 异步客户端
stream_pool = aioredis.ConnectionPool(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    password=settings.REDIS_PASSWORD,
    db=settings.REDIS_DB,
    decode_responses=True,
    max_connections=50,
    socket_timeout=None,             
    health_check_interval=30   
)
redis_stream_async = aioredis.Redis(connection_pool=stream_pool)


# 同步客户端
sync_pool = redis.ConnectionPool(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    password=settings.REDIS_PASSWORD,
    db=settings.REDIS_DB,
    decode_responses=True,
    max_connections=50,
    socket_timeout=5.0
)
redis_sync = redis.Redis(connection_pool=sync_pool)


# 任务过期时间 (秒)，例如 24 小时后自动删除，防止 Redis 爆满
TASK_TTL = 60 * 60 * 24 


# =========================================================
# 辅助方法：统一的 JSON 序列化器
# =========================================================
def _serialize_data(data: Any) -> str:
    if data is None:
        return ""
    try:
        if hasattr(data, 'model_dump'):   # Pydantic v2
            data_dict = data.model_dump()
        elif hasattr(data, 'dict'):       # Pydantic v1
            data_dict = data.dict()
        else:
            data_dict = data
        # default=str 解决 datetime 等不可序列化对象的报错
        return json.dumps(data_dict, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"序列化任务数据失败: {e}")
        return str(data)

# =========================================================
# 2. 方法定义
# =========================================================

async def create_task_async(task_id: str):
    """[Async] 创建任务 (API层调用)"""
    key = f"task:{task_id}"
    try:
        await redis_async.hset(key, mapping={
            "status": "pending",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        await redis_async.expire(key, TASK_TTL)
    except Exception as e:
        logger.error(f"Redis create_task error: {e}")
        raise


def update_task_sync(task_id: str, status: str, data: Any = None, error: str = None):
    """[Sync] 更新任务状态并推送流式事件 (Service层后台任务调用)"""
    key = f"task:{task_id}"
    channel = f"task_channel:{task_id}"
    payload = {"status": status}

    if data:
        payload["data"] = _serialize_data(data) 
    if error:
        payload["error"] = error

    try:
        # 1. 更新静态状态 (使用 hset)
        redis_sync.hset(key, mapping=payload)
        redis_sync.expire(key, TASK_TTL)
        
        # 2. 触发 SSE 广播
        # 将整个 payload 发出去，前端拿到即可解析渲染
        redis_sync.publish(channel, json.dumps(payload, ensure_ascii=False, default=str))
    except Exception as e:
        logger.error(f"Redis error update_task_sync for {task_id}: {e}")


async def update_task_async(task_id: str, status: str, data: Any = None, error: str = None):
    """[Async] 更新任务状态并推送流式事件 (Controller/异步任务调用)"""
    key = f"task:{task_id}"
    channel = f"task_channel:{task_id}"
    
    payload = {"status": status}
    if data:
        payload["data"] = _serialize_data(data)
    else:
        payload["data"] = ""
    if error:
        payload["error"] = error
    else:
        payload["error"] = ""


    try:
        # 1. 更新静态状态
        await redis_async.hset(key, mapping=payload)
        await redis_async.expire(key, TASK_TTL)
        
        # 2. 触发 SSE 广播
        await redis_async.publish(channel, json.dumps(payload, ensure_ascii=False, default=str))
    except Exception as e:
        logger.error(f"Redis error in update_task_async for {task_id}: {e}")


async def get_task_async(task_id: str) -> Optional[Dict[str, Any]]:
    """[Async] 获取任务详情 (API层查询接口兜底调用)"""
    key = f"task:{task_id}"
    try:
        raw_data = await redis_async.hgetall(key)
        if not raw_data:
            return None

        if "data" in raw_data and raw_data["data"]:
            try:
                raw_data["data"] = json.loads(raw_data["data"])
            except json.JSONDecodeError:
                pass # 保持原样

        return raw_data
    except Exception as e:
        logger.error(f"Redis get_task error: {e}")
        return None