"""微信 dispatch 端点

由 Node bot (weixin-agent-sdk) 转发用户文本到这里，统一在 Python 端做指令路由。
"""
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel
from loguru import logger

from app.core.config import settings
from app.services.wechat_command import dispatch as cmd_dispatch


router = APIRouter()


class DispatchRequest(BaseModel):
    conversation_id: str
    text: str


class DispatchData(BaseModel):
    text: str


class DispatchResponse(BaseModel):
    errCode: int = 0
    errMsg: str = "success"
    data: DispatchData


@router.post("/dispatch", response_model=DispatchResponse)
async def dispatch_command(
    request: Request,
    payload: DispatchRequest,
    x_dispatch_token: str | None = Header(default=None, alias="X-Dispatch-Token"),
):
    expected = settings.WECHAT_DISPATCH_TOKEN
    if not expected:
        logger.error("WECHAT_DISPATCH_TOKEN 未配置，拒绝所有 dispatch 请求")
        raise HTTPException(status_code=503, detail="dispatch token not configured")
    if x_dispatch_token != expected:
        raise HTTPException(status_code=401, detail="invalid dispatch token")

    http_client = request.app.state.http_client
    reply = await cmd_dispatch(http_client, payload.text)

    logger.info(
        f"wechat dispatch | conv={payload.conversation_id} | "
        f"text={payload.text!r} | reply_len={len(reply)}"
    )
    return DispatchResponse(data=DispatchData(text=reply))
