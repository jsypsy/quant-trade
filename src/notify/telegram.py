"""텔레그램 알림.

설정 필요:
  .env 에 TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID 추가
  토큰이 없으면 조용히 스킵한다 (실패해도 매매 루프를 중단하지 않음).

이벤트:
  notify_order     — BUY/SELL 주문 제출 시
  notify_portfolio — 사이클 종료 후 포트폴리오 현황
  notify_kill      — 킬스위치(일손실 한도 초과) 시
  notify_error     — 예기치 못한 오류 시
"""
from __future__ import annotations

import httpx
from loguru import logger

from config.settings import settings
from src.portfolio.account import Balance

_API = "https://api.telegram.org/bot{token}/sendMessage"

_KR_NAMES: dict[str, str] = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "035420": "NAVER",
    "005380": "현대차",
    "028260": "삼성물산",
    "000270": "기아",
    "055550": "신한지주",
    "105560": "KB금융",
}


def _send(text: str) -> None:
    token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id
    if not token or not chat_id:
        logger.warning("[TG] TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID 미설정 — 알림 스킵")
        return
    try:
        url = _API.format(token=token)
        resp = httpx.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=5)
        if not resp.json().get("ok"):
            logger.warning("[TG] 알림 전송 실패: {}", resp.text[:200])
    except Exception as exc:
        logger.warning("[TG] 알림 전송 실패: {}", exc)


def notify_order(
    *,
    market: str,
    side: str,
    ticker: str,
    qty: int,
    price: float,
    order_no: str,
    dry_run: bool,
) -> None:
    tag = "📋 DRY-RUN" if dry_run else "✅ 주문체결"
    price_str = f"{int(price):,}원"
    side_kr = "매수" if side == "BUY" else "매도"
    emoji = "🟢" if side == "BUY" else "🔴"
    name = _KR_NAMES.get(ticker, ticker)
    _send(
        f"{tag}\n"
        f"{emoji} <b>{side_kr}</b> {name}({ticker}) {qty}주 @ {price_str}\n"
        f"주문번호: {order_no or '-'}"
    )


def notify_portfolio(balance: Balance) -> None:
    """주문 발생 후 포트폴리오 현황 요약 전송."""
    lines = ["📊 <b>포트폴리오 현황</b>"]
    if balance.positions:
        for p in balance.positions:
            sign = "+" if p.pnl >= 0 else ""
            lines.append(
                f"• {p.name} {p.qty}주 @ {p.avg_price:,}원"
                f"  {sign}{p.pnl_rate:.1f}%"
            )
    else:
        lines.append("보유 종목 없음")
    lines.append("─────────────")
    sign = "+" if balance.pnl_rate >= 0 else ""
    stocks_value = sum(p.current_value for p in balance.positions)
    cash = balance.portfolio_value - stocks_value
    lines.append(f"총 매입: {balance.purchase_amount:,}원")
    lines.append(f"총 평가: {balance.portfolio_value:,}원")
    lines.append(f"총 수익률: {sign}{balance.pnl_rate:.2f}%")
    lines.append(f"예수금: {cash:,}원")
    _send("\n".join(lines))


def notify_kill(*, reason: str, daily_pnl: float) -> None:
    _send(
        f"🚨 <b>킬스위치 발동</b>\n"
        f"사유: {reason}\n"
        f"일손실: {daily_pnl:,.0f}원"
    )


def notify_error(*, context: str, error: str) -> None:
    _send(
        f"⚠️ <b>오류 발생</b>\n"
        f"위치: {context}\n"
        f"내용: {error}"
    )


def notify_cycle(*, market: str, cycle_no: int, signals: list[dict]) -> None:
    """매 사이클 분석 결과 전송. signals: [{"ticker", "action", "reason"}, ...]"""
    icons = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}
    lines = [f"🔍 <b>[{market}]</b> #{cycle_no} 사이클"]
    for s in signals:
        icon = icons.get(s["action"], "⚪")
        lines.append(f"{icon} {s['ticker']}: {s['action']} — {s['reason']}")
    _send("\n".join(lines))
