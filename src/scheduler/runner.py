"""모의투자 메인 루프 — 한국 주식.

한 사이클:
  1. 잔고 조회 → 일일 손익 갱신 → 배분 금액 산출
  2. 강제 청산 (손절/익절/장 마감) — 시장가
  3. 전략 시그널 산출
  4. RiskGuard 검증 → 주문 제출
  5. sync_fills()
"""
import time

from loguru import logger

from src.data.market import MarketData
from src.data.universe import UniverseProvider
from src.execution.order import OrderType
from src.execution.order_manager import OrderManager
from src.notify.telegram import notify_error, notify_portfolio
from src.utils.trade_log import log_trade
from src.portfolio.account import AccountQuery, Balance
from src.risk.guard import RiskContext, RiskGuard
from src.risk.position_monitor import PositionMonitor
from src.signal.engine import SignalEngine
from src.strategy.base import Action, Signal, Strategy
from src.utils.time import (
    is_market_open,
    now_kst,
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
        universe: UniverseProvider,
        position_monitor: PositionMonitor | None = None,
        interval: int = _DEFAULT_INTERVAL,
        universe_refresh_sec: int = 300,
        reentry_cooldown_sec: int = 300,
    ) -> None:
        self._engine    = signal_engine
        self._market    = market
        self._guard     = guard_kr
        self._manager   = order_manager
        self._account   = account
        self._universe  = universe
        self._monitor   = position_monitor or PositionMonitor()
        self._interval  = interval
        self._universe_refresh_sec = universe_refresh_sec
        self._reentry_cooldown_sec = reentry_cooldown_sec
        self._daily_pnl: float = 0.0
        self._pnl_date = None                 # 일일 손익 기준일 (KST)
        self._day_start_value: int = 0        # 장 시작 시점 총 평가금액 스냅샷
        self._cycle_no: int = 0
        self._universe_tickers: list[str] = []
        self._universe_ts: float = 0.0
        self._cooldown_until: dict[str, float] = {}   # ticker → 재진입 가능 시각(monotonic)

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

    def _refresh_universe(self, held: list[str]) -> None:
        """주기적으로 유니버스를 갱신하고, 보유 종목을 합쳐 전략을 구성한다.

        보유 종목은 유니버스에서 빠져도 매도(청산) 관리를 위해 항상 포함한다.
        """
        now = time.monotonic()
        if not self._universe_tickers or now - self._universe_ts >= self._universe_refresh_sec:
            try:
                self._universe_tickers = self._universe.fetch()
                self._universe_ts = now
            except Exception as exc:
                logger.warning("[유니버스] 갱신 실패 — 기존 유지: {}", exc)
        effective = list(dict.fromkeys(self._universe_tickers + held))
        self._engine.set_universe(effective)

    def _cycle(self) -> dict:
        self._cycle_no += 1
        logger.info("━━ [KR] 사이클 #{} 시작 ━━", self._cycle_no)

        # 잔고 조회 — 실패 시 사이클 전체 스킵.
        # (가짜 잔고로 매수하거나, 보유 정보 없이 SELL 이 전부 스킵되는 비대칭 방지)
        try:
            balance: Balance = self._account.get_balance()
        except Exception as exc:
            logger.warning("잔고 조회 실패 — 사이클 스킵: {}", exc)
            return {}

        # 일일 손익 갱신 (당일 첫 잔고 스냅샷 대비, 미실현 포함) — 킬스위치 입력
        today = now_kst().date()
        if self._pnl_date != today:
            self._pnl_date = today
            self._day_start_value = balance.portfolio_value
        self._daily_pnl = float(balance.portfolio_value - self._day_start_value)

        allocated = balance.portfolio_value
        position_values = {p.ticker: float(p.current_value) for p in balance.positions}
        position_qtys = {p.ticker: p.qty for p in balance.positions}

        now = time.monotonic()

        # 강제 청산 (손절/익절/장 마감) — 전략 신호보다 우선, 시장가 제출
        exit_results = {}
        for exit_order in self._monitor.check(balance.positions):
            ctx = RiskContext(
                current_price=float(exit_order.price),
                portfolio_value=allocated,
                daily_pnl=self._daily_pnl,
                pending_tickers=self._manager.get_pending_tickers(),
                position_value=position_values.get(exit_order.ticker, 0.0),
            )
            decision = self._guard.check(
                exit_order.ticker,
                Signal(Action.SELL, exit_order.qty, exit_order.reason),
                ctx,
            )
            if decision.approved:
                self._cooldown_until[exit_order.ticker] = now + self._reentry_cooldown_sec
            result = self._manager.submit(
                decision, float(exit_order.price), order_type=OrderType.MARKET,
            )
            if result and result.success:
                exit_results[exit_order.ticker] = result

        # 유니버스 갱신 (보유 종목은 매도 관리 위해 항상 포함)
        self._refresh_universe(list(position_qtys.keys()))

        if not self._engine._strategies:
            logger.info("[KR] 유니버스 비어있음 — 스킵")
            return exit_results

        # 시그널
        signals = self._engine.run()

        # 주문 제출
        pending = self._manager.get_pending_tickers()
        results = dict(exit_results)
        eod = self._monitor.eod_active()

        for ticker, signal in signals.items():
            if signal.action == Action.BUY and eod:
                logger.info("[KR][{}] 장 마감 청산 구간 — 신규 매수 차단", ticker)
                continue

            # 재진입 쿨다운 — 최근 매도 종목의 BUY 차단
            if signal.action == Action.BUY and now < self._cooldown_until.get(ticker, 0.0):
                logger.info("[KR][{}] 재진입 쿨다운 — BUY 스킵", ticker)
                continue

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

            # 매도 승인 시 재진입 쿨다운 설정
            if decision.approved and decision.action == Action.SELL:
                self._cooldown_until[ticker] = now + self._reentry_cooldown_sec

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
