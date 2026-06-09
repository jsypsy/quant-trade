"""텔레그램 알림.

설정 필요:
  .env 에 TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID 추가
  토큰이 없으면 조용히 스킵한다 (실패해도 매매 루프를 중단하지 않음).

이벤트:
  notify_order   — BUY/SELL 주문 제출 시
  notify_kill    — 킬스위치(일손실 한도 초과) 시
  notify_error   — 예기치 못한 오류 시
"""
import httpx
from loguru import logger

from config.settings import settings

_API = "https://api.telegram.org/bot{token}/sendMessage"


def _send(text: str) -> None:
    token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id
    if not token or not chat_id:
        return
    try:
        url = _API.format(token=token)
        httpx.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=5)
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
    emoji = "🟢" if side == "BUY" else "🔴"
    _send(
        f"{tag} [{market}]\n"
        f"{emoji} <b>{side}</b> {ticker} {qty}주 @ {price_str}\n"
        f"주문번호: {order_no or '-'}"
    )


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
