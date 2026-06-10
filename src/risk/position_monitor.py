"""포지션 모니터 — 전략 신호와 무관한 강제 청산.

매 사이클 전략 신호보다 먼저 실행한다. 우선순위:
  1. 장 마감 청산 — 15:20 이후 전량 (단타 포지션의 오버나이트 갭 리스크 차단)
  2. 손절 — 수익률 ≤ -stop_loss_pct
  3. 익절 — 수익률 ≥ +take_profit_pct

청산 주문은 시장가로 제출해야 한다 (지정가 미체결 = 손실 확대).
"""
from dataclasses import dataclass
from datetime import datetime, time as dtime

from loguru import logger

from config.settings import settings as _global_settings
from src.portfolio.account import Position
from src.utils.time import now_kst

_EOD_EXIT = dtime(15, 20)


@dataclass
class ExitOrder:
    ticker: str
    qty: int
    price: int    # 잔고 조회 시점 현재가 (시장가 주문이므로 로깅·검증용)
    reason: str


class PositionMonitor:
    def __init__(
        self,
        stop_loss_pct: float | None = None,
        take_profit_pct: float | None = None,
        eod_exit: dtime = _EOD_EXIT,
    ) -> None:
        self.stop_loss_pct = (
            stop_loss_pct if stop_loss_pct is not None else _global_settings.stop_loss_pct
        )
        self.take_profit_pct = (
            take_profit_pct if take_profit_pct is not None else _global_settings.take_profit_pct
        )
        self.eod_exit = eod_exit

    def eod_active(self, now: datetime | None = None) -> bool:
        """장 마감 청산 구간 여부. 이 구간에는 신규 매수도 차단해야 한다."""
        return (now or now_kst()).time() >= self.eod_exit

    def check(self, positions: list[Position], now: datetime | None = None) -> list[ExitOrder]:
        eod = self.eod_active(now)
        exits: list[ExitOrder] = []
        for p in positions:
            if p.orderable_qty <= 0:
                continue
            if eod:
                reason = f"장 마감 청산 ({p.pnl_rate:+.2f}%)"
            elif p.pnl_rate <= -self.stop_loss_pct:
                reason = f"손절 {p.pnl_rate:+.2f}% ≤ -{self.stop_loss_pct}%"
            elif p.pnl_rate >= self.take_profit_pct:
                reason = f"익절 {p.pnl_rate:+.2f}% ≥ +{self.take_profit_pct}%"
            else:
                continue
            logger.warning("[MONITOR] {} 강제 청산: {}", p.ticker, reason)
            exits.append(ExitOrder(p.ticker, p.orderable_qty, p.current_price, reason))
        return exits
