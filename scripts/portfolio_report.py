"""포트폴리오 현황 조회 및 리포트 출력.

실행:
  uv run python scripts/portfolio_report.py

GitHub Actions에서 실행 시 $GITHUB_STEP_SUMMARY 에 Markdown 테이블로 출력됩니다.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.kis.auth import KISAuth
from src.kis.client import KISClient
from src.notify.telegram import notify_portfolio
from src.portfolio.account import AccountQuery, Balance
from src.utils.logging import setup_logging


def _pnl_str(v: int) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:,}"


def _rate_str(r: float) -> str:
    sign = "+" if r >= 0 else ""
    return f"{sign}{r:.2f}%"


def build_markdown(balance: Balance) -> str:
    lines = []

    # ── 요약 ──────────────────────────────────────────────────
    lines.append("## 포트폴리오 현황\n")
    lines.append("| 항목 | 금액 |")
    lines.append("|---|---:|")
    lines.append(f"| 매입금액 | {balance.purchase_amount:,}원 |")
    lines.append(f"| 평가금액 | {balance.portfolio_value:,}원 |")
    lines.append(f"| 평가손익 | {_pnl_str(balance.pnl)}원 |")
    lines.append(f"| 수익률 | {_rate_str(balance.pnl_rate)} |")
    lines.append(f"| 예수금 | {balance.cash:,}원 |")

    if not balance.positions:
        lines.append("\n_보유 종목 없음_")
        return "\n".join(lines)

    # ── 종목별 ────────────────────────────────────────────────
    lines.append("\n## 보유 종목\n")
    lines.append("| 종목 | 보유 | 주문가능 | 평균단가 | 현재가 | 매입금액 | 평가금액 | 평가손익 | 수익률 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for p in balance.positions:
        lines.append(
            f"| {p.name} ({p.ticker}) "
            f"| {p.qty:,}주 "
            f"| {p.orderable_qty:,}주 "
            f"| {p.avg_price:,}원 "
            f"| {p.current_price:,}원 "
            f"| {p.purchase_amount:,}원 "
            f"| {p.current_value:,}원 "
            f"| {_pnl_str(p.pnl)}원 "
            f"| {_rate_str(p.pnl_rate)} |"
        )

    return "\n".join(lines)


def main() -> None:
    setup_logging()
    auth = KISAuth()
    client = KISClient(auth)
    account = AccountQuery(client)
    balance = account.get_balance()

    notify_portfolio(balance)

    md = build_markdown(balance)
    print(md)

    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(md + "\n")


if __name__ == "__main__":
    main()
