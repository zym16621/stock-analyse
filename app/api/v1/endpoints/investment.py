"""量化定投数据看板 API 端点"""
from fastapi import APIRouter, Request

from app.schemas.investment import InvestmentSnapshotResponse
from app.services.investment import get_investment_snapshot

router = APIRouter()


@router.get("/snapshot", response_model=InvestmentSnapshotResponse)
async def get_snapshot(request: Request):
    """
    获取量化定投数据快照

    并发抓取三个数据源：
    - 标普500 (.INX) 最近7天的PE分位点数据
    - 恒生科技 (HSTECH) 最近7天的PE分位点数据
    - CNN 恐惧贪婪指数最近7天的数据
    """
    http_client = request.app.state.http_client
    data = await get_investment_snapshot(http_client)

    return InvestmentSnapshotResponse(data=data)