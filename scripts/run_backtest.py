"""스윙 전략 백테스트 — KIS 일봉 데이터 (Actions에서 실행).

라이브와 동일 구조(정배열 진입 + 손절/익절 청산)를 비용 반영해 검증한다.

사용법 (KIS 키 필요 → GitHub Actions 권장):
  uv run python scripts/run_backtest.py
  uv run python scripts/run_backtest.py --tickers 005930,000660 --tp 0.05 --sl 0.03

데이터 한계: KIS 일봉만(분봉 과거 미제공). 일봉 기준 = 스윙(다일 보유) 검증엔 적합.
OOS 권장: 결과를 과신하지 말 것 — 과적합·일봉↔분봉 괴리 존재.
"""
import argparse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from loguru import logger

_KST = ZoneInfo("Asia/Seoul")

# 최근 봇이 매매한 종목 바스켓 (거래대금 상위 주도주)
_DEFAULT_BASKET = {
    "034020": "두산에너빌리티",
    "373220": "LG에너지솔루션",
    "006400": "삼성SDI",
    "042660": "한화오션",
    "047040": "대우건설",
    "010120": "LS ELECTRIC",
    "000660": "SK하이닉스",
    "005930": "삼성전자",
}


def _parse_args() -> argparse.Namespace:
    today = datetime.now(tz=_KST).strftime("%Y%m%d")
    ago = (datetime.now(tz=_KST) - timedelta(days=200)).strftime("%Y%m%d")
    p = argparse.ArgumentParser(description="스윙 백테스트")
    p.add_argument("--tickers", default="", help="쉼표구분 종목코드 (미지정=기본 바스켓)")
    p.add_argument("--start", default=ago)
    p.add_argument("--end", default=today)
    p.add_argument("--short", type=int, default=3)
    p.add_argument("--long", type=int, default=10)
    p.add_argument("--band", type=float, default=0.001)   # 0.1%
    p.add_argument("--tp", type=float, default=0.04)      # 익절 +4%
    p.add_argument("--sl", type=float, default=0.02)      # 손절 -2%
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    from src.backtest.engine import CostModel, backtest_bracket
    from src.data.market import MarketData
    from src.kis.auth import KISAuth
    from src.kis.client import KISClient

    if args.tickers:
        basket = {t.strip(): t.strip() for t in args.tickers.split(",") if t.strip()}
    else:
        basket = _DEFAULT_BASKET

    market = MarketData(KISClient(KISAuth()))
    cost = CostModel()

    print("─" * 78)
    print(f"  스윙 백테스트  {args.start}~{args.end}  | MA {args.short}/{args.long} "
          f"밴드 {args.band*100:.2f}% 익절 +{args.tp*100:.0f}% 손절 -{args.sl*100:.0f}% "
          f"| 왕복비용 {cost.round_trip*100:.2f}%")
    print("─" * 78)

    rets, n_trades_total = [], 0
    for code, name in basket.items():
        try:
            ohlcv = market.get_daily_ohlcv(code, args.start, args.end)
        except Exception as exc:
            print(f"  {name}({code}): 데이터 조회 실패 — {exc}")
            continue
        if ohlcv.empty or len(ohlcv) < args.long + 2:
            print(f"  {name}({code}): 데이터 부족({len(ohlcv)}행)")
            continue
        r = backtest_bracket(
            ohlcv, short=args.short, long=args.long, band_pct=args.band,
            take_profit=args.tp, stop_loss=args.sl, cost=cost,
        )
        rets.append(r.total_return)
        n_trades_total += r.n_trades
        print(f"  {name}({code}) [{len(ohlcv)}일]  {r.line()}")

    print("─" * 78)
    if rets:
        avg = sum(rets) / len(rets)
        wins = sum(1 for x in rets if x > 0)
        print(f"  종목 {len(rets)}개 | 총거래 {n_trades_total}회 | "
              f"종목평균 순수익 {avg*100:+.2f}% | +종목 {wins}/{len(rets)}")
        print(f"  → 해석: 평균 순수익이 +면 비용 반영 후에도 엣지 가능성. -면 이 설정은 못 버는 것.")
    else:
        print("  유효 결과 없음")
    print("─" * 78)


if __name__ == "__main__":
    main()
