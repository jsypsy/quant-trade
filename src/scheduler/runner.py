"""모의투자 메인 루프 — 한국 + 미국 듀얼 마켓.

포트폴리오 배분:
  - 한국 장(09:00~15:30 KST): 총 자산의 50%
  - 미국 장(22:30~05:00 KST): 총 자산의 50%
  두 시장은 겹치지 않으므로 단일 루프로 처리한다.

한 사이클:
  1. 어느 시장이 열려있는지 확인
  2. 잔고 조회 → 배분 금액 산출
  3. 해당 시장 전략으로 시그널 산출
  4. RiskGuard 검증 → 주문 제출
  5. sync_fills()
"""
import time

from loguru import logger

from src.data.market import MarketData
from src.execution.order_manager import OrderManager
from src.notify.telegram import notify_error
from src.utils.trade_log import log_trade
from src.portfolio.account import AccountQuery, Balance
from src.risk.guard import RiskContext, RiskGuard
from src.signal.engine import SignalEngine
from src.strategy.base import Action, Strategy
from src.utils.time import (
    is_market_open,
    is_us_market_open,
    is_us_premarket_open,
    seconds_until_open,
)

_DEFAULT_INTERVAL   = 300   # 장 중 주기 (초)
_CLOSED_CHECK       = 60    # 장 외 대기 단위 (초)
_ALLOC_KR           = 0.5   # 한국 주식 배분 비율
_ALLOC_US           = 0.5   # 미국 주식 배분 비율


class PaperTrader:
    def __init__(
        self,
        signal_engine: SignalEngine,
        market: MarketData,
        guard_kr: RiskGuard,
        guard_us: RiskGuard,
        order_manager: OrderManager,
        account: AccountQuery,
        interval: int = _DEFAULT_INTERVAL,
    ) -> None:
        self._engine    = signal_engine
        self._market    = market
        self._guard_kr  = guard_kr
        self._guard_us  = guard_us
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

    def run_once(self, force_market: str | None = None) -> dict:
        """단회 실행 (테스트·검증용).

        force_market: "KR" | "US" | None(자동감지)
        """
        if force_market == "KR" or (force_market is None and is_market_open()):
            return self._cycle("KR")
        if force_market == "US" or (force_market is None and is_us_market_open()):
            return self._cycle("US")
        logger.info("현재 장 외 시간 — 스킵")
        return {}

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _tick(self) -> None:
        if is_market_open():
            self._cycle("KR")
            time.sleep(self._interval)
        elif is_us_market_open():
            self._cycle("US")
            time.sleep(self._interval)
        elif is_us_premarket_open():
            self._cycle("US")
            time.sleep(self._interval)
        else:
            wait = min(seconds_until_open(), _CLOSED_CHECK)
            logger.info("장 외 시간 — {:.0f}초 대기", wait)
            time.sleep(wait)

    def _cycle(self, market: str) -> dict:
        self._cycle_no += 1
        logger.info("━━ [{}] 사이클 #{} 시작 ━━", market, self._cycle_no)

        # 잔고 조회 + 배분
        alloc_ratio = _ALLOC_KR if market == "KR" else _ALLOC_US
        try:
            balance: Balance = self._account.get_balance()
            total_value = balance.portfolio_value or 10_000_000
        except Exception as exc:
            logger.warning("잔고 조회 실패 (fallback): {}", exc)
            total_value = 10_000_000
            balance = None

        allocated = total_value * alloc_ratio
        position_values: dict[str, float] = {}
        if balance:
            position_values = {p.ticker: float(p.current_value) for p in balance.positions}

        # 해당 시장 전략만 필터
        strategies = [
            s for s in self._engine._strategies
            if getattr(s, "market_type", "KR") == market
        ]
        if not strategies:
            logger.info("[{}] 등록된 전략 없음", market)
            return {}

        # 시그널
        sub_engine = self._engine.__class__(strategies, self._market)
        signals = sub_engine.run()

        # 주문 제출
        guard = self._guard_kr if market == "KR" else self._guard_us
        pending = self._manager.get_pending_tickers()
        results = {}

        for ticker, signal in signals.items():
            if signal.action == Action.SELL and position_values.get(ticker, 0.0) <= 0:
                logger.debug("[{}][{}] 보유 없음 — SELL 스킵", market, ticker)
                continue

            if signal.action == Action.HOLD:
                log_trade(
                    market=market, side="HOLD", ticker=ticker,
                    qty=0, price=0.0, dry_run=self._manager._executor.dry_run,
                    approved=True, reject_reason=signal.reason,
                )
                continue

            try:
                if market == "US":
                    excd = next(
                        (getattr(s, "excd", "NAS") for s in strategies if s.ticker == ticker),
                        "NAS",
                    )
                    current_price = self._market.get_us_current_price(ticker, excd)
                else:
                    excd = "KR"
                    current_price = float(self._market.get_current_price(ticker).stck_prpr)
            except Exception as exc:
                logger.error("[{}][{}] 현재가 조회 실패: {}", market, ticker, exc)
                continue

            ctx = RiskContext(
                current_price=current_price,
                portfolio_value=allocated,
                daily_pnl=self._daily_pnl,
                pending_tickers=pending,
                position_value=position_values.get(ticker, 0.0),
            )
            decision = guard.check(ticker, signal, ctx)

            result = self._manager.submit(decision, current_price, market=market, excd=excd)
            if result and result.success:
                results[ticker] = result

        self._manager.sync_fills()
        logger.info("━━ [{}] 사이클 #{} 완료 (주문={}건) ━━", market, self._cycle_no, len(results))
        return results
