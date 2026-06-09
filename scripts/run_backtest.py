"""골든크로스 백테스트 진입점.

사용법:
  uv run python scripts/run_backtest.py --ticker 005930 --start 20230101 --end 20241231

옵션:
  --ticker      종목 코드 (예: 005930)
  --start       시작일 YYYYMMDD (기본 1년 전)
  --end         종료일 YYYYMMDD (기본 오늘)
  --short       단기 이동평균 기간 (기본 5)
  --long        장기 이동평균 기간 (기본 20)
  --capital     초기 자본금 (기본 10,000,000)
  --buy-fee     매수 수수료율 (기본 0.00015)
  --sell-fee    매도 수수료율 + 거래세 (기본 0.00215)

OOS 권장: 전체 데이터의 뒤 20~30%는 별도 검증 구간으로 사용하세요.
"""
import argparse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from loguru import logger

_KST = ZoneInfo("Asia/Seoul")


def _parse_args() -> argparse.Namespace:
    today = datetime.now(tz=_KST).strftime("%Y%m%d")
    year_ago = (datetime.now(tz=_KST) - timedelta(days=365)).strftime("%Y%m%d")

    p = argparse.ArgumentParser(description="골든크로스 백테스트")
    p.add_argument("--ticker",    default="005930")
    p.add_argument("--start",     default=year_ago)
    p.add_argument("--end",       default=today)
    p.add_argument("--short",     type=int, default=5)
    p.add_argument("--long",      type=int, default=20)
    p.add_argument("--capital",   type=float, default=10_000_000)
    p.add_argument("--buy-fee",   type=float, default=0.00015, dest="buy_fee")
    p.add_argument("--sell-fee",  type=float, default=0.00215, dest="sell_fee")
    return p.parse_args()


def _print_report(result, ticker: str, start: str, end: str) -> None:
    sep = "─" * 50
    print(f"\n{sep}")
    print(f"  백테스트 결과  [{ticker}]  {start} ~ {end}")
    print(sep)
    print(f"  초기 자본금   : {result.initial_capital:>15,.0f} 원")
    print(f"  최종 자본금   : {result.final_capital:>15,.0f} 원")
    print(f"  총 수익률     : {result.total_return_pct:>+14.2f} %")
    print(f"  최대 낙폭(MDD): {result.max_drawdown_pct:>14.2f} %")
    print(f"  샤프 비율     : {result.sharpe_ratio:>14.3f}")
    print(f"  승률          : {result.win_rate_pct:>14.1f} %")
    print(f"  총 거래 횟수  : {result.trade_count:>14} 건")
    print(sep)

    if result.trades:
        print("\n  ── 거래 내역 ──")
        for t in result.trades:
            pnl_str = f"  손익: {t.pnl:+,.0f}원" if "SELL" in t.side else ""
            print(f"  {t.date}  {t.side:<10}  {t.price:>10,.0f}  {t.qty:>6}주{pnl_str}")
    print()


def main() -> None:
    args = _parse_args()

    from config.settings import settings
    from src.backtest.engine import BacktestEngine
    from src.data.market import MarketData
    from src.kis.client import KISClient
    from src.kis.models import KISAuth
    from src.strategy.golden_cross import GoldenCrossStrategy

    auth = KISAuth(
        app_key=settings.app_key,
        app_secret=settings.app_secret,
        base_url=settings.base_url,
    )
    client = KISClient(auth)
    market_data = MarketData(client)

    logger.info("일봉 데이터 조회 중: {} {} ~ {}", args.ticker, args.start, args.end)
    ohlcv = market_data.get_daily_ohlcv(args.ticker, args.start, args.end)

    if ohlcv.empty:
        logger.error("OHLCV 데이터 없음 — 기간/티커를 확인하세요.")
        return

    logger.info("데이터 {}행 수신", len(ohlcv))

    strategy = GoldenCrossStrategy(
        ticker=args.ticker,
        short_window=args.short,
        long_window=args.long,
    )
    engine = BacktestEngine(strategy, buy_fee_rate=args.buy_fee, sell_fee_rate=args.sell_fee)
    result = engine.run(ohlcv, initial_capital=args.capital)

    _print_report(result, args.ticker, args.start, args.end)


if __name__ == "__main__":
    main()
