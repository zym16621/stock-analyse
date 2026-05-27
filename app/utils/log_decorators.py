import functools
import inspect
import uuid

from loguru import logger


def ai_trace(func):
    """
    AI 日志追踪装饰器
    1. 自动生成 req_uuid
    2. 将日志 channel 切换为 'ai' (写入独立文件)
    3. 兼容同步(def)、异步(async def) 和 异步生成器(async yield)
    """
    
    # --- 1. 针对异步生成器 (带 yield 的 async def) ---
    @functools.wraps(func)
    async def async_gen_wrapper(*args, **kwargs):
        request_id = str(uuid.uuid4())
        
        # 手动获取生成器对象
        gen = func(*args, **kwargs)
        
        while True:
            try:
                with logger.contextualize(channel="ai", req_uuid=request_id):
                    item = await gen.__anext__() 
            except StopAsyncIteration:
                break
            
            yield item

    # --- 2. 针对普通异步方法 (带 return 的 async def) ---
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        request_id = str(uuid.uuid4())
        with logger.contextualize(channel="ai", req_uuid=request_id):
            return await func(*args, **kwargs)

    # --- 3. 针对普通同步方法 (带 return 的 def) ---
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        request_id = str(uuid.uuid4())
        with logger.contextualize(channel="ai", req_uuid=request_id):
            return func(*args, **kwargs)

    # 自动识别并路由到正确的 wrapper
    if inspect.isasyncgenfunction(func):
        return async_gen_wrapper
    elif inspect.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper