"""微信指令路由层

把用户文本映射到对应数据源的抓取函数，统一返回格式化为微信纯文本的 str。
所有 fetch_* 函数复用 app/services/investment.py，绝不重复抓取。
"""
from typing import Awaitable, Callable, Dict, Tuple

import httpx
from loguru import logger

from app.services.investment import (
    fetch_cnn_fear_greed,
    fetch_hstech_fundamental,
    fetch_sp500_fundamental,
    fetch_sse_index,
    get_investment_snapshot,
)


Handler = Callable[[httpx.AsyncClient], Awaitable[str]]


def _fmt_pct(v) -> str:
    return f"{v:.2f}%" if v is not None else "—"


def _fmt_num(v, digits: int = 2) -> str:
    return f"{v:.{digits}f}" if v is not None else "—"


def _trend_arrow(history) -> str:
    """从历史序列推断短期趋势箭头"""
    if not history or len(history) < 2:
        return "—"
    first, last = history[0].value, history[-1].value
    if last > first + 0.5:
        return "↗"
    if last < first - 0.5:
        return "↘"
    return "→"


async def handle_sp500(http_client: httpx.AsyncClient) -> str:
    d = await fetch_sp500_fundamental(http_client)
    return (
        "📊 标普500 (.INX)\n"
        f"收盘 {_fmt_num(d.latest_close_price)}\n"
        f"PE {_fmt_num(d.pe_current)} (10年分位 {_fmt_pct(d.pe_percentile)} {_trend_arrow(d.pe_history)})\n"
        f"PB {_fmt_num(d.pb_current)} (10年分位 {_fmt_pct(d.pb_percentile)})\n"
        f"PS {_fmt_num(d.ps_current)} (10年分位 {_fmt_pct(d.ps_percentile)})"
    )


async def handle_hstech(http_client: httpx.AsyncClient) -> str:
    d = await fetch_hstech_fundamental(http_client)
    return (
        "📊 恒生科技 (HSTECH)\n"
        f"收盘 {_fmt_num(d.latest_close_price)}\n"
        f"PE {_fmt_num(d.pe_current)} (上市以来分位 {_fmt_pct(d.pe_percentile)} {_trend_arrow(d.pe_history)})\n"
        f"PB {_fmt_num(d.pb_current)} (分位 {_fmt_pct(d.pb_percentile)})\n"
        f"PS {_fmt_num(d.ps_current)} (分位 {_fmt_pct(d.ps_percentile)})"
    )


async def handle_sse(http_client: httpx.AsyncClient) -> str:
    d = await fetch_sse_index(http_client)
    if d.current is None:
        return "📈 上证指数\n数据暂不可用"
    arrow = "↗" if (d.change_pct or 0) > 0 else ("↘" if (d.change_pct or 0) < 0 else "→")
    return (
        f"📈 {d.name or '上证指数'}\n"
        f"当前 {_fmt_num(d.current)} {arrow}\n"
        f"涨跌 {_fmt_num(d.change_amt)} ({_fmt_pct(d.change_pct)})\n"
        f"昨收 {_fmt_num(d.prev_close)}"
    )


async def handle_fg(http_client: httpx.AsyncClient) -> str:
    d = await fetch_cnn_fear_greed(http_client)
    return (
        "🌡️ CNN 恐惧贪婪指数\n"
        f"当前 {d.latest_score:.1f} ({d.latest_rating_cn})"
    )


async def handle_snapshot(http_client: httpx.AsyncClient) -> str:
    snap = await get_investment_snapshot(http_client)

    sp = snap.sp500
    hs = snap.hstech
    sse = snap.sse
    cnn = snap.cnn_fear_greed

    sse_line = (
        f"当前 {_fmt_num(sse.current)} ({_fmt_pct(sse.change_pct)})"
        if sse.current is not None else "数据暂不可用"
    )

    return (
        "🗂 投资快照\n"
        "—————————\n"
        f"📊 标普500: {_fmt_num(sp.latest_close_price)}\n"
        f"  PE {_fmt_num(sp.pe_current)} / 10年分位 {_fmt_pct(sp.pe_percentile)}\n"
        f"📊 恒生科技: {_fmt_num(hs.latest_close_price)}\n"
        f"  PE {_fmt_num(hs.pe_current)} / 分位 {_fmt_pct(hs.pe_percentile)}\n"
        f"📈 上证指数: {sse_line}\n"
        f"🌡️ 恐惧贪婪: {cnn.latest_score:.1f} ({cnn.latest_rating_cn})"
    )


async def handle_help(_: httpx.AsyncClient) -> str:
    return (
        "🤖 可用指令\n"
        "/快照     - 全部数据一览\n"
        "/标普     - 标普500 PE 分位\n"
        "/恒科     - 恒生科技 PE 分位\n"
        "/上证     - 上证指数实时行情\n"
        "/恐贪     - CNN 恐惧贪婪指数\n"
        "/help    - 显示本帮助"
    )


COMMAND_TABLE: Dict[Tuple[str, ...], Handler] = {
    ("/快照", "/snapshot", "快照", "全部"): handle_snapshot,
    ("/sp500", "/标普", "标普500", "标普"): handle_sp500,
    ("/恒科", "/恒生科技", "恒生科技", "hstech"): handle_hstech,
    ("/上证", "/上证指数", "上证"): handle_sse,
    ("/恐贪", "/fg", "恐惧贪婪"): handle_fg,
    ("/help", "/h", "?", "帮助"): handle_help,
}


def _resolve(text: str) -> Handler:
    normalized = text.strip().lower()
    for keys, handler in COMMAND_TABLE.items():
        for k in keys:
            if normalized == k.lower():
                return handler
    return handle_help


async def dispatch(http_client: httpx.AsyncClient, text: str) -> str:
    handler = _resolve(text)
    try:
        return await handler(http_client)
    except Exception as e:
        logger.exception(f"wechat_command handler error: {e}")
        return "服务繁忙，请稍后再试"
