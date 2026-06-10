"""모의투자 메인 루프 — 한국 주식.

한 사이클:
  1. 잔고 조회 → 배분 금액 산출
  2. 전략 시그널 산출
  3. RiskGuard 검증 → 주문 제출
  4. sync_fills()
"""
import time

from loguru import logger

from src.data.market import MarketData
from src.execution.order_manager import OrderManager
from src.notify.telegram import notify_error, notify_portfolio
from src.utils.trade_log import log_trade
from src.portfolio.account import AccountQuery, Balance
from src.risk.guard import RiskContext, RiskGuard
from src.signal.engine import SignalEngine
from src.strategy.base import Action, Signal, Strategy
from src.utils.time import (
    is_market_open,
    seconds_until_open,
)

_DEFAULT_INTERVAL   = 300   # 장 중 주기 (초)
_CLOSED_CHECK       = 60    # 장 외 대기 단위 (초)


class PaperTrader:
    def __init__(
        self,
        signal_engine: SignalEngine,
        market: MarketData,
        guard_kr: RiskGuard,
        order_manager: OrderManager,
        account: AccountQuery,
        interval: int = _DEFAULT_INTERVAL,
    ) -> None:
        self._engine    = signal_engine
        self._market    = market
        self._guard     = guard_kr
        self._manager   = order_manager
        self._account   = account
        self._interval  = interval
        self._daily_pnl: float = 0.0
        self._cycle_no: int = 0

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def run(self, max_seconds: int | None = None) -> None:
        """메인 루프. max_seconds 지정 시 해당 초 후 자동 종료. Ctrl+C 로도 종료."""
        deadline = time.monotonic() + max_seconds if max_seconds else None
        logger.info(
            "PaperTrader 시작 (주기={}초, dry_run={}, 제한={})",
            self._interval, self._manager._executor.dry_run,
            f"{max_seconds}초" if max_seconds else "무제한",
        )
        while True:
            if deadline and time.monotonic() >= deadline:
                logger.info("설정된 실행 시간 종료 — 자동 종료합니다.")
                break
            try:
                self._tick()
            except KeyboardInterrupt:
                logger.info("사용자 중단 — 종료합니다.")
                break
            except Exception as exc:
                logger.error("루프 오류 (30초 후 재시도): {}", exc)
                notify_error(context="메인 루프", error=str(exc))
                time.sleep(30)

    def run_once(self) -> dict:
        """단회 실행 (테스트·검증용)."""
        if not is_market_open():
            logger.info("현재 장 외 시간 — 스킵")
            return {}
        return self._cycle()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _tick(self) -> None:
        if is_market_open():
            self._cycle()
            time.sleep(self._interval)
        else:
            wait = min(seconds_until_open(), _CLOSED_CHECK)
            logger.info("장 외 시간 — {:.0f}초 대기", wait)
            time.sleep(wait)

    def _cycle(self) -> dict:
        self._cycle_no += 1
        logger.info("━━ [KR] 사이클 #{} 시작 ━━", self._cycle_no)

        # 잔고 조회 + 배분
        try:
            balance: Balance = self._account.get_balance()
            total_value = balance.portfolio_value or 10_000_000
        except Exception as exc:
            logger.warning("잔고 조회 실패 (fallback): {}", exc)
            total_value = 10_000_000
            balance = None

        allocated = total_value
        position_values: dict[str, float] = {}
        position_qtys: dict[str, int] = {}
        if balance:
            position_values = {p.ticker: float(p.current_value) for p in balance.positions}
            position_qtys = {p.ticker: p.qty for p in balance.positions}

        if not self._engine._strategies:
            logger.info("[KR] 등록된 전략 없음")
            return {}

        # 시그널
        signals = self._engine.run()

        # 주문 제출
        pending = self._manager.get_pending_tickers()
        results = {}

        for ticker, signal in signals.items():
            if signal.action == Action.SELL and position_values.get(ticker, 0.0) <= 0:
                logger.debug("[KR][{}] 보유 없음 — SELL 스킵", ticker)
                continue

            # SELL: 전략의 qty(=1 플레이스홀더)를 실제 보유 수량으로 교체
            if signal.action == Action.SELL and ticker in position_qtys:
                signal = Signal(signal.action, position_qtys[ticker], signal.reason)

            if signal.action == Action.HOLD:
                log_trade(
                    market="KR", side="HOLD", ticker=ticker,
                    qty=0, price=0.0, dry_run=self._manager._executor.dry_run,
                    approved=True, reject_reason=signal.reason,
                )
                continue

            try:
                current_price = float(self._market.get_current_price(ticker).stck_prpr)
            except Exception as exc:
                logger.error("[KR][{}] 현재가 조회 실패: {}", ticker, exc)
                continue

            ctx = RiskContext(
                current_price=current_price,
                portfolio_value=allocated,
                daily_pnl=self._daily_pnl,
                pending_tickers=pending,
                position_value=position_values.get(ticker, 0.0),
            )
            decision = self._guard.check(ticker, signal, ctx)

            result = self._manager.submit(decision, current_price)
            if result and result.success:
                results[ticker] = result

        # 실제 체결이 확인된 종목이 있을 때만, 최신 잔고를 다시 조회해 현황 전송.
        filled = self._manager.sync_fills()
        if filled:
            try:
                fresh = self._account.get_balance()
                notify_portfolio(fresh, filled=filled)
            except Exception as exc:
                logger.warning("체결 후 잔고 조회 실패 — 포트폴리오 알림 스킵: {}", exc)
        logger.info("━━ [KR] 사이클 #{} 완료 (주문={}건) ━━", self._cycle_no, len(results))
        return results
