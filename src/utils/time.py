"""장 운영시간 / 영업일 판단 (KST 기준).

한국 공휴일 캘린더는 미포함 — 토·일 제외만 처리.
공휴일 대응이 필요하면 KIS 영업일 조회 API 또는 holidays 패키지를 연동하세요.

KR 운영시간:
  - KRX 정규장        09:00~15:30.
  - NXT 애프터마켓     09:00~20:00 (KR_EXCHANGE=NXT/SOR, prod 전용). 모의(vps)는 NXT 미지원.
"""
import datetime as _dt
import zoneinfo
from datetime import datetime, time as dtime

from config.settings import settings

_KST = zoneinfo.ZoneInfo("Asia/Seoul")
_OPEN      = dtime(9, 0)
_CLOSE     = dtime(15, 30)
_CLOSE_NXT = dtime(20, 0)   # NXT 애프터마켓 마감


def _close_time() -> dtime:
    """현재 거래소 마감 시각. NXT/SOR → 20:00, KRX → 15:30."""
    return _CLOSE_NXT if settings.is_nxt else _CLOSE


def now_kst() -> datetime:
    return datetime.now(tz=_KST)


def is_weekday() -> bool:
    return now_kst().weekday() < 5   # 0=월 … 4=금


def is_market_open() -> bool:
    """현재 KST 시각이 장중(09:00~마감) 안에 있으면 True. 마감은 거래소별(_close_time)."""
    if not is_weekday():
        return False
    t = now_kst().time()
    return _OPEN <= t < _close_time()


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
    """장 마감까지 남은 초. 마감됐으면 0. 마감 시각은 거래소별(_close_time)."""
    now = now_kst()
    close = _close_time()
    close_today = now.replace(hour=close.hour, minute=close.minute, second=0, microsecond=0)
    remaining = (close_today - now).total_seconds()
    return max(0.0, remaining)
