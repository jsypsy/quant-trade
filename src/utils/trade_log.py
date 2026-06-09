"""매매 이력 CSV 로거.

trades/YYYY-MM-DD.csv 에 날짜별로 누적 기록한다.
파일이 없으면 헤더를 자동 생성한다.
"""
import csv
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

_KST = ZoneInfo("Asia/Seoul")
_TRADES_DIR = Path(__file__).parent.parent.parent / "trades"
_FIELDS = [
    "timestamp",    # KST ISO-8601
    "market",       # KR
    "side",         # BUY | SELL
    "ticker",
    "qty",
    "price",
    "currency",     # KRW | USD
    "dry_run",      # True | False
    "approved",     # True | False
    "reject_reason",
    "order_no",
    "error",
]


def log_trade(
    *,
    market: str,
    side: str,
    ticker: str,
    qty: int,
    price: float,
    dry_run: bool,
    approved: bool,
    reject_reason: str = "",
    order_no: str = "",
    error: str = "",
) -> None:
    _TRADES_DIR.mkdir(exist_ok=True)
    now = datetime.now(tz=_KST)
    path = _TRADES_DIR / f"{now.strftime('%Y-%m-%d')}.csv"

    row = {
        "timestamp":     now.isoformat(timespec="seconds"),
        "market":        market,
        "side":          side,
        "ticker":        ticker,
        "qty":           qty,
        "price":         str(int(price)),
        "currency":      "KRW",
        "dry_run":       dry_run,
        "approved":      approved,
        "reject_reason": reject_reason,
        "order_no":      order_no,
        "error":         error,
    }

    write_header = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)
