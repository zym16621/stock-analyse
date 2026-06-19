"""量化定投数据抓取服务"""
from datetime import datetime, timedelta
from typing import List

import httpx
from loguru import logger

from app.core.config import settings
from app.schemas.investment import (
    DailyDataPoint,
    CNNFearGreedData,
    AssetFundamentalData,
    InvestmentSnapshotData,
    SSEIndexData,
)


# CNN 恐惧贪婪状态翻译
RATING_CN_MAP = {
    "extreme greed": "极度贪婪",
    "greed": "贪婪",
    "neutral": "中性",
    "fear": "恐惧",
    "extreme fear": "极度恐惧",
}


def extract_history(sorted_results: List[dict], metric_key: str, days: int = 7) -> List[DailyDataPoint]:
    """从排序后的结果中提取指定指标的最近N天历史数据"""
    valid_data = []
    for item in sorted_results:
        date_str = item.get("date", "")[:10]
        value = item.get(metric_key)
        if value is not None:
            valid_data.append(DailyDataPoint(date=date_str, value=value * 100))
    return valid_data[-days:] if len(valid_data) >= days else valid_data


async def fetch_sp500_fundamental(http_client: httpx.AsyncClient) -> AssetFundamentalData:
    """
    获取标普500 (.INX) 最近10天的基本面数据
    使用 10 年历史分位点 (y10)
    """
    url = "https://open.lixinger.com/api/us/index/fundamental"

    end_date = datetime.now()
    start_date = end_date - timedelta(days=10)

    payload = {
        "token": settings.LIXINGER_TOKEN,
        "stockCodes": [".INX"],
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
        "metricsList": [
            "cp",
            "pe_ttm.mcw",
            "pe_ttm.y10.mcw.cvpos",
            "pb.mcw",
            "pb.y10.mcw.cvpos",
            "ps_ttm.mcw",
            "ps_ttm.y10.mcw.cvpos"
        ]
    }

    try:
        response = await http_client.post(url, json=payload, timeout=30.0)
        response.raise_for_status()
        data = response.json()

        if data.get("code") == 1 and data.get("data"):
            results = data["data"]
            sorted_results = sorted(results, key=lambda x: x.get("date", ""))
            latest_item = sorted_results[-1] if sorted_results else {}

            return AssetFundamentalData(
                latest_close_price=latest_item.get("cp"),
                pe_current=latest_item.get("pe_ttm.mcw"),
                pe_percentile=latest_item.get("pe_ttm.y10.mcw.cvpos", 0) * 100,
                pe_history=extract_history(sorted_results, "pe_ttm.y10.mcw.cvpos"),
                pb_current=latest_item.get("pb.mcw"),
                pb_percentile=latest_item.get("pb.y10.mcw.cvpos", 0) * 100,
                pb_history=extract_history(sorted_results, "pb.y10.mcw.cvpos"),
                ps_current=latest_item.get("ps_ttm.mcw"),
                ps_percentile=latest_item.get("ps_ttm.y10.mcw.cvpos", 0) * 100,
                ps_history=extract_history(sorted_results, "ps_ttm.y10.mcw.cvpos"),
            )
        else:
            logger.warning(f"SP500 API returned: code={data.get('code')}, message={data.get('message')}")
            return AssetFundamentalData()

    except Exception as e:
        logger.error(f"Failed to fetch SP500 data: {e}")
        return AssetFundamentalData()


async def fetch_hstech_fundamental(http_client: httpx.AsyncClient) -> AssetFundamentalData:
    """
    获取恒生科技 (HSTECH) 最近10天的基本面数据
    使用上市以来历史分位点 (fs)
    """
    url = "https://open.lixinger.com/api/hk/index/fundamental"

    end_date = datetime.now()
    start_date = end_date - timedelta(days=10)

    payload = {
        "token": settings.LIXINGER_TOKEN,
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
        "stockCodes": ["HSTECH"],
        "metricsList": [
            "cp",
            "pe_ttm.mcw",
            "pe_ttm.fs.mcw.cvpos",
            "pb.mcw",
            "pb.fs.mcw.cvpos",
            "ps_ttm.mcw",
            "ps_ttm.fs.mcw.cvpos"
        ]
    }

    try:
        response = await http_client.post(url, json=payload, timeout=30.0)
        response.raise_for_status()
        data = response.json()

        if data.get("code") == 1 and data.get("data"):
            results = data["data"]
            sorted_results = sorted(results, key=lambda x: x.get("date", ""))
            latest_item = sorted_results[-1] if sorted_results else {}

            return AssetFundamentalData(
                latest_close_price=latest_item.get("cp"),
                pe_current=latest_item.get("pe_ttm.mcw"),
                pe_percentile=latest_item.get("pe_ttm.fs.mcw.cvpos", 0) * 100,
                pe_history=extract_history(sorted_results, "pe_ttm.fs.mcw.cvpos"),
                pb_current=latest_item.get("pb.mcw"),
                pb_percentile=latest_item.get("pb.fs.mcw.cvpos", 0) * 100,
                pb_history=extract_history(sorted_results, "pb.fs.mcw.cvpos"),
                ps_current=latest_item.get("ps_ttm.mcw"),
                ps_percentile=latest_item.get("ps_ttm.fs.mcw.cvpos", 0) * 100,
                ps_history=extract_history(sorted_results, "ps_ttm.fs.mcw.cvpos"),
            )
        else:
            logger.warning(f"HSTECH API returned: code={data.get('code')}, message={data.get('message')}")
            return AssetFundamentalData()

    except Exception as e:
        logger.error(f"Failed to fetch HSTECH data: {e}")
        return AssetFundamentalData()


async def fetch_cnn_fear_greed(http_client: httpx.AsyncClient) -> CNNFearGreedData:
    """
    获取 CNN 恐惧贪婪指数最近10天的历史数据
    """
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://edition.cnn.com/markets/fear-and-greed",
    }

    try:
        response = await http_client.get(url, headers=headers, timeout=15.0)
        response.raise_for_status()
        data = response.json()

        historical_data = data.get("fear_and_greed_historical", {}).get("data", [])

        if not historical_data:
            logger.warning("CNN API returned no historical data")
            return CNNFearGreedData(
                latest_score=0,
                latest_rating="unknown",
                latest_rating_cn="未知",
                history=[],
            )

        recent_7_days = historical_data[-7:]

        history_points = []
        for item in recent_7_days:
            timestamp = item.get("x", 0) / 1000.0
            date_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
            score = item.get("y", 0)
            history_points.append(DailyDataPoint(date=date_str, value=score))

        latest_item = recent_7_days[-1] if recent_7_days else {}
        latest_score = latest_item.get("y", 0)
        latest_rating = latest_item.get("rating", "unknown")
        latest_rating_cn = RATING_CN_MAP.get(latest_rating.lower(), latest_rating)

        return CNNFearGreedData(
            latest_score=latest_score,
            latest_rating=latest_rating,
            latest_rating_cn=latest_rating_cn,
            history=history_points,
        )

    except Exception as e:
        logger.error(f"Failed to fetch CNN Fear & Greed data: {e}")
        return CNNFearGreedData(
            latest_score=0,
            latest_rating="unknown",
            latest_rating_cn="未知",
            history=[],
        )


async def fetch_sse_index(http_client: httpx.AsyncClient) -> SSEIndexData:
    """
    获取上证指数 (sh000001) 实时行情，来源：新浪财经
    返回 GBK 编码文本，格式如：
    var hq_str_sh000001="上证指数,3204.5,3210.7,3198.4,...";
    字段索引：1=名称, 2=今开, 3=昨收, 4=当前价, 5=最高, 6=最低, ..., 9=成交量(手)
    注意：sina 的字段顺序与香港/美股略有差异，下标须以指数为准
    """
    url = "https://hq.sinajs.cn/list=sh000001"
    headers = {
        "Referer": "https://finance.sina.com.cn",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    try:
        response = await http_client.get(url, headers=headers, timeout=10.0)
        response.raise_for_status()
        text = response.content.decode("gbk", errors="ignore")

        if "=" not in text or '"' not in text:
            logger.warning(f"SSE index unexpected format: {text[:80]}")
            return SSEIndexData()

        payload = text.split('"', 2)[1]
        parts = payload.split(",")
        if len(parts) < 10:
            logger.warning(f"SSE index field count too short: {len(parts)}")
            return SSEIndexData()

        # 索引参考：0=名称, 1=今开价, 2=昨收价, 3=当前价, 4=最高, 5=最低, 8=成交量(手)
        name = parts[0] or "上证指数"
        prev_close = float(parts[2]) if parts[2] else None
        current = float(parts[3]) if parts[3] else None
        volume = float(parts[8]) if len(parts) > 8 and parts[8] else None

        change_amt = None
        change_pct = None
        if current is not None and prev_close not in (None, 0):
            change_amt = round(current - prev_close, 2)
            change_pct = round((current - prev_close) / prev_close * 100, 2)

        return SSEIndexData(
            name=name,
            current=current,
            prev_close=prev_close,
            change_amt=change_amt,
            change_pct=change_pct,
            volume=volume,
        )

    except Exception as e:
        logger.error(f"Failed to fetch SSE index: {e}")
        return SSEIndexData()


async def get_investment_snapshot(http_client: httpx.AsyncClient) -> InvestmentSnapshotData:
    """
    并发抓取三个数据源，返回聚合后的投资快照数据
    """
    import asyncio

    sp500_task = fetch_sp500_fundamental(http_client)
    hstech_task = fetch_hstech_fundamental(http_client)
    cnn_task = fetch_cnn_fear_greed(http_client)
    sse_task = fetch_sse_index(http_client)

    sp500_data, hstech_data, cnn_data, sse_data = await asyncio.gather(
        sp500_task, hstech_task, cnn_task, sse_task, return_exceptions=True
    )

    if isinstance(sp500_data, Exception):
        logger.error(f"SP500 task failed: {sp500_data}")
        sp500_data = AssetFundamentalData()

    if isinstance(hstech_data, Exception):
        logger.error(f"HSTECH task failed: {hstech_data}")
        hstech_data = AssetFundamentalData()

    if isinstance(cnn_data, Exception):
        logger.error(f"CNN task failed: {cnn_data}")
        cnn_data = CNNFearGreedData(
            latest_score=0,
            latest_rating="unknown",
            latest_rating_cn="未知",
            history=[],
        )

    if isinstance(sse_data, Exception):
        logger.error(f"SSE task failed: {sse_data}")
        sse_data = SSEIndexData()

    return InvestmentSnapshotData(
        cnn_fear_greed=cnn_data,
        sp500=sp500_data,
        hstech=hstech_data,
        sse=sse_data,
    )