"""종목코드 → 종목명 레지스트리.

유니버스 조회 시 종목명을 등록(register)하고, 알림 등에서 조회(name_of)한다.
하드코딩 사전에 없는 동적 유니버스 종목도 실제 이름으로 표시하기 위함.
"""
_NAMES: dict[str, str] = {}


def register(mapping: dict[str, str]) -> None:
    """ticker→name 매핑을 등록한다 (빈 이름은 무시)."""
    for ticker, name in mapping.items():
        if name:
            _NAMES[ticker] = name


def name_of(ticker: str) -> str:
    """종목명을 반환. 미등록이면 종목코드 그대로."""
    return _NAMES.get(ticker, ticker)
