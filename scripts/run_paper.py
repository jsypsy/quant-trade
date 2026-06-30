"""모의투자 자동매매 진입점 (한국).

실행:
  uv run python scripts/run_paper.py

환경변수:
  DRY_RUN=false   → 실제 모의 주문 전송 (기본: true = 로그만)
  INTERVAL_SEC=N  → 장 중 주기 (기본: 300초)
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from config.settings import settings
from src.data.market import MarketData
from src.data.universe import MARKET_KOSPI, UniverseProvider
from src.execution.order import OrderExecutor
from src.execution.order_manager import OrderManager
from src.kis.auth import KISAuth
from src.kis.client import KISClient
from src.portfolio.account import AccountQuery
from src.risk.guard import RiskGuard
from src.risk.position_monitor import PositionMonitor
from src.scheduler.runner import PaperTrader
from src.signal.engine import SignalEngine
from src.strategy.base import Strategy
from src.strategy.golden_cross import GoldenCrossStrategy
from src.utils.logging import setup_logging

DRY_RUN              = settings.dry_run
INTERVAL             = int(os.getenv("INTERVAL_SEC", "30"))        # 사이클 주기(초)
RUN_MINUTES          = int(os.getenv("RUN_MINUTES", "0"))          # 0 = 무제한
UNIVERSE_TOP_N       = int(os.getenv("UNIVERSE_TOP_N", "10"))      # 동적 유니버스 종목 수 (공격적: 후보 확대)
UNIVERSE_REFRESH_SEC = int(os.getenv("UNIVERSE_REFRESH_SEC", "300"))  # 5분마다 종목 재선정


def make_strategy(ticker: str) -> Strategy:
    """동적 유니버스 종목에 적용할 전략 (분봉 골든크로스)."""
    return GoldenCrossStrategy(
        ticker, short_window=3, long_window=10, bar_type="minute",
        band_pct=settings.cross_band_pct,
        state_entry=True,        # 공격적: 정배열(상승추세) 종목 즉시 진입
        exit_on_reversal=False,  # 역배열 churn 매도 안 함 — 청산은 손절/익절에 위임(수수료 ↓)
    )


def main() -> None:
    setup_logging()
    logger.info(
        "환경: {}  거래소: {} (시세 {})  dry_run={}  주기={}초",
        settings.kis_env, settings.exchange_id, settings.market_div_code, DRY_RUN, INTERVAL,
    )
    if settings.is_nxt:
        logger.info("🌙 NXT/통합 모드 — 애프터마켓 ~20:00, EOD 청산 19:50.")
    if not DRY_RUN:
        logger.warning("⚠️  실제 모의 주문 모드 — KIS 에 주문이 전송됩니다.")
    tg_ok = bool(settings.telegram_bot_token and settings.telegram_chat_id)
    logger.info("텔레그램 알림: {}", "활성화" if tg_ok else "비활성화 (토큰/챗ID 미설정)")

    auth    = KISAuth()
    client  = KISClient(auth)
    market  = MarketData(client)
    account = AccountQuery(client)

    guard    = RiskGuard()
    # 스윙형: 장마감 강제청산 OFF → 손절/익절 미도달 종목은 오버나이트 보유
    monitor  = PositionMonitor(eod_liquidate=False)
    executor = OrderExecutor(client, dry_run=DRY_RUN)
    manager  = OrderManager(executor)
    engine   = SignalEngine(make_strategy, market)
    universe = UniverseProvider(
        client, market=MARKET_KOSPI, top_n=UNIVERSE_TOP_N,
        pool_size=30,             # 거래대금 풀 확대(필터 후 후보 확보)
        min_change_rate=2.0,      # 모멘텀 필터 ON — 등락률 +2% 이상(실제 오르는 종목만)
    )

    trader = PaperTrader(
        signal_engine=engine,
        market=market,
        guard_kr=guard,
        order_manager=manager,
        account=account,
        universe=universe,
        position_monitor=monitor,
        interval=INTERVAL,
        universe_refresh_sec=UNIVERSE_REFRESH_SEC,
        reentry_cooldown_sec=settings.reentry_cooldown_sec,
        trading_capital=settings.trading_capital,
        slot_count=UNIVERSE_TOP_N,   # 균등배분 — 종목당 자본 = 운용자본/유니버스수
    )
    trader.run(max_seconds=RUN_MINUTES * 60 if RUN_MINUTES else None)


if __name__ == "__main__":
    main()
