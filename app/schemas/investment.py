"""量化定投数据看板响应模型"""
from typing import List, Optional
from pydantic import BaseModel


class DailyDataPoint(BaseModel):
    """单日数据点"""
    date: str
    value: float


class CNNFearGreedData(BaseModel):
    """CNN 恐惧贪婪指数数据"""
    latest_score: float
    latest_rating: str
    latest_rating_cn: str
    history: List[DailyDataPoint]  # 最近7天数据


class AssetFundamentalData(BaseModel):
    """资产基本面数据"""
    latest_close_price: Optional[float] = None
    # PE 估值
    pe_current: Optional[float] = None
    pe_percentile: Optional[float] = None
    pe_history: List[DailyDataPoint] = []  # PE分位点7天趋势
    # PB 估值
    pb_current: Optional[float] = None
    pb_percentile: Optional[float] = None
    pb_history: List[DailyDataPoint] = []  # PB分位点7天趋势
    # PS 估值
    ps_current: Optional[float] = None
    ps_percentile: Optional[float] = None
    ps_history: List[DailyDataPoint] = []  # PS分位点7天趋势


class InvestmentSnapshotData(BaseModel):
    """投资快照数据"""
    cnn_fear_greed: CNNFearGreedData
    sp500: AssetFundamentalData
    hstech: AssetFundamentalData
    sse: "SSEIndexData"


class SSEIndexData(BaseModel):
    """上证指数实时行情（来源：新浪财经）"""
    name: Optional[str] = None
    current: Optional[float] = None
    prev_close: Optional[float] = None
    change_amt: Optional[float] = None
    change_pct: Optional[float] = None
    volume: Optional[float] = None  # 单位：手


InvestmentSnapshotData.model_rebuild()


class InvestmentSnapshotResponse(BaseModel):
    """投资快照响应"""
    errCode: int = 0
    errMsg: str = "success"
    data: InvestmentSnapshotData