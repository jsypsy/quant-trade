"""리스크 가드.

시그널이 실제 주문으로 나가기 전에 아래 항목을 순서대로 검사한다.

1. HOLD → 즉시 통과
2. 킬스위치 — 일일 누적 손실이 한도 초과 시 BUY 차단 (SELL 은 허용)
3. 중복 주문 방지 — 동일 종목 미체결 주문 존재 시 차단
4. 수량 조정 — 1회 주문 금액 한도 / 종목 비중 한도 중 작은 쪽으로 감축
5. 조정 후 qty == 0 → 거부

한도값은 기본적으로 settings 에서 읽되, 생성 시 직접 주입 가능 (테스트 편의).
"""
from dataclasses import dataclass, field

from loguru import logger

from config.settings import settings as _global_settings
from src.strategy.base import Action, Signal


@dataclass
class RiskContext:
    current_price: float        # 현재가 (KRW 또는 USD)
    portfolio_value: float      # 총 포트폴리오 가치
    daily_pnl: float            # 오늘 실현 손익 (손실은 음수)
    pending_tickers: set[str] = field(default_factory=set)
    position_value: float = 0.0 # 해당 종목 현재 보유금액


@dataclass
class RiskDecision:
    approved: bool
    ticker: str
    action: Action
    qty: int
    reason: str


class RiskGuard:
    def __init__(
        self,
        max_daily_loss: int | None = None,
        max_order_amount: int | None = None,
        max_position_pct: float | None = None,
    ) -> None:
        self.max_daily_loss = max_daily_loss if max_daily_loss is not None else _global_settings.max_daily_loss
        self.max_order_amount = max_order_amount if max_order_amount is not None else _global_settings.max_order_amount
        self.max_position_pct = max_position_pct if max_position_pct is not None else _global_settings.max_position_pct

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def check(self, ticker: str, signal: Signal, ctx: RiskContext) -> RiskDecision:
        if signal.action == Action.HOLD:
            return RiskDecision(True, ticker, Action.HOLD, 0, "HOLD")

        # ① 킬스위치 (SELL 은 포지션 정리를 위해 허용)
        if signal.action == Action.BUY and ctx.daily_pnl <= -self.max_daily_loss:
            return self._reject(
                ticker, signal.action,
                f"킬스위치: 일일 손실 {ctx.daily_pnl:,}원 ≥ 한도 {self.max_daily_loss:,}원",
            )

        # ② 중복 주문 방지
        if ticker in ctx.pending_tickers:
            return self._reject(ticker, signal.action, f"미체결 주문 존재 ({ticker})")

        # ③ 수량 조정
        if signal.action == Action.BUY:
            qty = self._adjusted_buy_qty(ctx)
        else:
            qty = signal.qty  # SELL: 보유 수량은 runner 에서 실제 보유량으로 주입

        if qty == 0:
            return self._reject(ticker, signal.action, "한도 적용 후 주문 수량 0")

        return RiskDecision(True, ticker, signal.action, qty, f"승인 qty={qty}")

    def kill_switch_active(self, daily_pnl: int) -> bool:
        return daily_pnl <= -self.max_daily_loss

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _adjusted_buy_qty(self, ctx: RiskContext) -> int:
        price = ctx.current_price
        if price <= 0:
            return 0

        # 한도 ①: 1회 주문 금액
        max_by_amount = int(self.max_order_amount / price)

        # 한도 ②: 단일 종목 비중
        max_position_value = ctx.portfolio_value * self.max_position_pct
        room = max(0.0, max_position_value - ctx.position_value)
        max_by_pct = int(room / price)

        allowed = min(max_by_amount, max_by_pct)
        logger.debug("[RISK] BUY 수량 결정: {} (금액한도={}, 비중한도={})", allowed, max_by_amount, max_by_pct)
        return max(0, allowed)

    def _reject(self, ticker: str, action: Action, reason: str) -> RiskDecision:
        logger.warning("[RISK] {} {} 거부: {}", ticker, action.value, reason)
        return RiskDecision(False, ticker, action, 0, reason)
