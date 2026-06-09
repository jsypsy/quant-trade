"""장 운영시간 / 영업일 판단 (KST 기준).

한국 공휴일 캘린더는 미포함 — 토·일 제외만 처리.
공휴일 대응이 필요하면 KIS 영업일 조회 API 또는 holidays 패키지를 연동하세요.

KR 운영시간: KRX 정규장 09:00~15:30.
  - KIS 모의투자(vps)는 NXT 미지원 → 정규장 시간만 사용.
"""
import datetime as _dt
import zoneinfo
from datetime import datetime, time as dtime

_KST = zoneinfo.ZoneInfo("Asia/Seoul")
_OPEN  = dtime(9, 0)
_CLOSE = dtime(15, 30)


def now_kst() -> datetime:
    return datetime.now(tz=_KST)


def is_weekday() -> bool:
    return now_kst().weekday() < 5   # 0=월 … 4=금


def is_market_open() -> bool:
    """현재 KST 시각이 KRX 정규장(09:00~15:30) 안에 있으면 True."""
    if not is_weekday():
        return False
    t = now_kst().time()
    return _OPEN <= t < _CLOSE


def seconds_until_open() -> float:
    """다음 정규장 개장까지 남은 초. 이미 열려있으면 0."""
    now = now_kst()
    if is_market_open():
        return 0.0

    open_today = now.replace(hour=9, minute=0, second=0, microsecond=0)
    if now < open_today and is_weekday():
        return (open_today - now).total_seconds()

    days_ahead = 1
    while True:
        candidate = (now + _dt.timedelta(days=days_ahead)).replace(
            hour=9, minute=0, second=0, microsecond=0
        )
        if candidate.weekday() < 5:
            return (candidate - now).total_seconds()
        days_ahead += 1


def seconds_until_close() -> float:
    """장 마감까지 남은 초. 마감됐으면 0."""
    now = now_kst()
    close_today = now.replace(hour=15, minute=30, second=0, microsecond=0)
    remaining = (close_today - now).total_seconds()
    return max(0.0, remaining)
