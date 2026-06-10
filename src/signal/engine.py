"""시그널 엔진.

유니버스(종목코드 목록)에 맞춰 전략 인스턴스를 동적으로 구성하고,
각 전략에 시장 데이터를 공급해 BUY/SELL/HOLD 신호를 산출한다.
각 전략은 `ticker` 속성을 가져야 한다.

bar_type:
  "daily"  — 일봉 (스윙/포지션 트레이딩)
  "minute" — 1분봉 (당일 단타)
"""
from collections.abc import Callable
from datetime import date, timedelta

from loguru import logger

from src.data.market import MarketData
from src.strategy.base import Signal, Strategy

# 일봉 조회 기간 (60 영업일 ≈ 달력 90일)
_LOOKBACK_CALENDAR_DAYS = 90
# 분봉 조회 봉 수 (MA20 계산에 최소 21봉 필요, 여유 있게 30봉)
_MINUTE_CNT = 30


class SignalEngine:
    def __init__(self, strategy_factory: Callable[[str], Strategy], market: MarketData) -> None:
        self._make_strategy = strategy_factory
        self._market = market
        self._strategies: dict[str, Strategy] = {}

    def set_universe(self, tickers: list[str]) -> None:
        """현재 유니버스에 맞춰 전략을 추가/제거한다 (기존 인스턴스는 유지)."""
        wanted = set(tickers)
        current = set(self._strategies)
        for ticker in wanted - current:
            self._strategies[ticker] = self._make_strategy(ticker)
        for ticker in current - wanted:
            del self._strategies[ticker]

    def run(self) -> dict[str, Signal]:
        """모든 전략을 실행하고 종목코드 → Signal 매핑을 반환한다."""
        end = date.today().strftime("%Y%m%d")
        start = (date.today() - timedelta(days=_LOOKBACK_CALENDAR_DAYS)).strftime("%Y%m%d")

        signals: dict[str, Signal] = {}
        for strategy in self._strategies.values():
            ticker = getattr(strategy, "ticker", None)
            if ticker is None:
                logger.warning("전략 {}에 ticker 속성 없음 — 스킵", type(strategy).__name__)
                continue

            bar_type = getattr(strategy, "bar_type", "daily")
            try:
                if bar_type == "minute":
                    ohlcv = self._market.get_minute_ohlcv(ticker, cnt=_MINUTE_CNT)
                else:
                    ohlcv = self._market.get_daily_ohlcv(ticker, start, end)
                new_signals = strategy.generate_signals(ohlcv)
            except Exception as exc:
                logger.error("[{}] 시그널 산출 실패: {}", ticker, exc)
                continue

            for tkr, sig in new_signals.items():
                logger.info("[{}] {} qty={} ({})", tkr, sig.action.value, sig.qty, sig.reason)

            signals.update(new_signals)

        return signals
