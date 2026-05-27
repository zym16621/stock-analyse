

import traceback

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException


def register_exception_handlers(app: FastAPI):
    """
    注册全局异常处理
    """

    # 1. 捕获 参数校验错误 (422)
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """
        重写参数校验异常，将 Pydantic 的复杂错误简化为友好提示
        """
        # exc.errors() 返回的是一个列表，包含所有错误详情
        # 我们这里只取第一个错误提示给前端，或者你可以拼接所有错误
        errors = exc.errors()
        first_error = errors[0]
        
        # 拼接更友好的错误信息，例如: "token_type: Input should be a valid string"
        field = first_error.get("loc")[-1]  # 获取出错的字段名
        msg = first_error.get("msg")        # 获取错误信息
        
        error_msg = f"参数校验失败: {field} - {msg}"
        
        logger.warning(f"参数校验错误 | URL: {request.url} | Error: {error_msg}")

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "errCode": 422,
                "errMsg": error_msg,
                "data": None
            }
        )

    # 2. 捕获 主动抛出的 HTTPException (400, 401, 403, 404 等)
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """
        捕获代码中 raise HTTPException(...) 的异常
        """
        logger.warning(f"HTTP异常 | URL: {request.url} | Code: {exc.status_code} | Msg: {exc.detail}")
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "errCode": exc.status_code,
                "errMsg": exc.detail, # 这里直接使用你 raise 时写的 detail
                "data": None
            }
        )

    # 3. 捕获 所有未知的服务器内部错误 (500)
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """
        兜底捕获所有未知异常（代码Bug、数据库连不上等）
        """
        # 打印完整的堆栈跟踪，方便开发者排查
        logger.error(f"系统崩溃 | URL: {request.url} | Error: {str(exc)}")
        logger.error(traceback.format_exc())

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "errCode": 500,
                "errMsg": "系统内部错误，请联系管理员", # 不向前端展示具体的 Python 错误堆栈
                "data": None
            }
        )