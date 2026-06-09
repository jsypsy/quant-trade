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
from src.execution.order import OrderExecutor
from src.execution.order_manager import OrderManager
from src.kis.auth import KISAuth
from src.kis.client import KISClient
from src.portfolio.account import AccountQuery
from src.risk.guard import RiskGuard
from src.scheduler.runner import PaperTrader
from src.signal.engine import SignalEngine
from src.strategy.golden_cross import GoldenCrossStrategy
from src.utils.logging import setup_logging

DRY_RUN     = settings.dry_run
INTERVAL    = int(os.getenv("INTERVAL_SEC", "20"))  # 20초 단타
RUN_MINUTES = int(os.getenv("RUN_MINUTES", "0"))    # 0 = 무제한

# ── 전략 유니버스 ────────────────────────────────────────────────
# KR: 20초 간격 — 알고리즘 선정 2026-06-09, scalping_score 기반 MA 윈도우
UNIVERSE = [
    GoldenCrossStrategy("005930", short_window=4, long_window=12, bar_type="minute"),  # 삼성전자   score=314.9 mom=-7.7%
    GoldenCrossStrategy("000660", short_window=4, long_window=12, bar_type="minute"),  # SK하이닉스 score=150.3 mom=-6.3%
    GoldenCrossStrategy("035420", short_window=5, long_window=18, bar_type="minute"),  # NAVER      score=85.4  mom=-5.3%
    GoldenCrossStrategy("005380", short_window=5, long_window=18, bar_type="minute"),  # 현대차     score=74.4  mom=-14.8%
    GoldenCrossStrategy("028260", short_window=5, long_window=18, bar_type="minute"),  # 삼성물산   score=60.6  mom=-5.7%
    GoldenCrossStrategy("000270", short_window=5, long_window=18, bar_type="minute"),  # 기아       score=55.9  mom=-3.3%
    GoldenCrossStrategy("055550", short_window=6, long_window=20, bar_type="minute"),  # 신한지주   score=36.6  mom=+9.3%
    GoldenCrossStrategy("105560", short_window=6, long_window=20, bar_type="minute"),  # KB금융     score=36.8  mom=+1.8%
]


def main() -> None:
    setup_logging()
    logger.info("환경: {}  dry_run={}  주기={}초", settings.kis_env, DRY_RUN, INTERVAL)
    if not DRY_RUN:
        logger.warning("⚠️  실제 모의 주문 모드 — KIS 에 주문이 전송됩니다.")

    auth    = KISAuth()
    client  = KISClient(auth)
    market  = MarketData(client)
    account = AccountQuery(client)

    guard    = RiskGuard()
    executor = OrderExecutor(client, dry_run=DRY_RUN)
    manager  = OrderManager(executor)
    engine   = SignalEngine(UNIVERSE, market)

    trader = PaperTrader(
        signal_engine=engine,
        market=market,
        guard_kr=guard,
        order_manager=manager,
        account=account,
        interval=INTERVAL,
    )
    trader.run(max_seconds=RUN_MINUTES * 60 if RUN_MINUTES else None)


if __name__ == "__main__":
    main()
