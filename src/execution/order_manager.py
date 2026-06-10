"""주문 매니저.

OrderExecutor 위에서 미체결 추적과 중복 방지를 담당한다.

흐름:
  submit() → 미체결 목록에 ticker 추가 → OrderExecutor.submit()
  sync_fills() → KIS 미체결 조회 → 체결 완료된 ticker 를 목록에서 제거  (T10 에서 주기적으로 호출)
"""
from loguru import logger

from src.execution.order import OrderExecutor, OrderRequest, OrderResult, OrderType
from src.risk.guard import RiskDecision
from src.strategy.base import Action
from src.notify.telegram import notify_kill, notify_order  # noqa: F401 (notify_cycle imported by runner)
from src.utils.trade_log import log_trade


class OrderManager:
    def __init__(self, executor: OrderExecutor) -> None:
        self._executor = executor
        self._pending: set[str] = set()   # 미체결 종목 집합

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def submit(
        self,
        decision: RiskDecision,
        price: float,
    ) -> OrderResult | None:
        """RiskDecision 을 받아 주문을 제출한다."""
        if not decision.approved or decision.action == Action.HOLD:
            if not decision.approved:
                log_trade(
                    market="KR", side=decision.action.value, ticker=decision.ticker,
                    qty=decision.qty, price=price, dry_run=self._executor.dry_run,
                    approved=False, reject_reason=decision.reason,
                )
                if "킬스위치" in decision.reason:
                    notify_kill(reason=decision.reason, daily_pnl=0.0)
            return None

        if decision.ticker in self._pending:
            logger.warning("[OM] {} 미체결 주문 존재 — 중복 제출 차단", decision.ticker)
            log_trade(
                market="KR", side=decision.action.value, ticker=decision.ticker,
                qty=decision.qty, price=price, dry_run=self._executor.dry_run,
                approved=False, reject_reason="미체결 중복 차단",
            )
            return None

        req = OrderRequest(
            ticker=decision.ticker,
            side=decision.action.value,
            qty=decision.qty,
            price=price,
            order_type=OrderType.LIMIT,
        )
        result = self._executor.submit(req)

        log_trade(
            market="KR", side=decision.action.value, ticker=decision.ticker,
            qty=result.qty, price=result.price, dry_run=result.dry_run,
            approved=True, order_no=result.order_no, error=result.error,
        )

        if result.success:
            self._pending.add(decision.ticker)
            logger.info("[OM] {} 미체결 등록 (총 {}건)", decision.ticker, len(self._pending))
            notify_order(
                market="KR", side=result.side, ticker=result.ticker,
                qty=result.qty, price=result.price,
                order_no=result.order_no, dry_run=result.dry_run,
            )

        return result

    def get_pending_tickers(self) -> set[str]:
        return set(self._pending)

    def sync_fills(self) -> set[str]:
        """KIS 미체결 조회 후 체결 완료된 종목을 pending에서 제거한다.

        이번 호출에서 새로 체결된 종목 집합을 반환한다 (없으면 빈 집합).
        """
        if not self._pending:
            return set()
        unfilled = self._executor.get_unfilled_tickers()
        if unfilled is None:
            return set()  # API 실패 — 기존 목록 유지
        filled = self._pending - unfilled
        for ticker in filled:
            logger.info("[OM] {} 체결 확인 — pending 제거", ticker)
        self._pending &= unfilled
        return filled
