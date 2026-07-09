"""PaperTrader 운용 자본 한도 헬퍼 테스트."""
from src.scheduler.runner import (
    _affordable_qty,
    _already_committed,
    _cash_qty,
    _market_bearish,
    _slot_qty,
    _stop_limit_reached,
)


def test_room_within_capital():
    # 자본 1천만, 700만 투입됨, 가격 1000 → 남은 300만 / 1000 = 3000주
    assert _affordable_qty(10_000_000, 7_000_000, 1_000) == 3_000


def test_capital_exhausted_returns_zero():
    # 이미 자본 이상 투입 → 0
    assert _affordable_qty(10_000_000, 10_000_000, 1_000) == 0
    assert _affordable_qty(10_000_000, 12_000_000, 1_000) == 0


def test_zero_price_returns_zero():
    assert _affordable_qty(10_000_000, 0, 0) == 0


def test_full_capital_when_nothing_deployed():
    assert _affordable_qty(10_000_000, 0, 2_000) == 5_000


# ------------------------------------------------------------------
# 균등배분 슬롯
# ------------------------------------------------------------------

def test_slot_qty_even_split():
    # 자본 1천만, 10슬롯 → 종목당 100만. 가격 1000 → 1000주
    assert _slot_qty(10_000_000, 10, 1_000) == 1_000


def test_slot_qty_caps_big_position():
    # 자본 1천만, 10슬롯=100만, 고가주 50만 → 2주만 (한 종목 독식 방지)
    assert _slot_qty(10_000_000, 10, 500_000) == 2


def test_slot_qty_edge():
    assert _slot_qty(10_000_000, 0, 1_000) == 0
    assert _slot_qty(10_000_000, 10, 0) == 0


# ------------------------------------------------------------------
# 미수 방지 — 예수금 상한
# ------------------------------------------------------------------

def test_cash_qty_within_deposit():
    # 예수금 100만, 가격 1000 → 1000주
    assert _cash_qty(1_000_000, 1_000) == 1_000


def test_cash_qty_negative_deposit_blocks_buy():
    # 이미 미수(예수금 마이너스) → 신규 매수 0
    assert _cash_qty(-784_008, 1_000) == 0
    assert _cash_qty(0, 1_000) == 0


def test_cash_qty_zero_price():
    assert _cash_qty(1_000_000, 0) == 0


# ------------------------------------------------------------------
# 1종목 1포지션 — 잔고 지연에도 몰빵(피라미딩) 차단
# ------------------------------------------------------------------

def test_committed_when_held_in_balance():
    assert _already_committed("002990", {"002990": 71}, set()) is True


def test_committed_when_bought_but_balance_lags():
    # 잔고엔 아직 미반영(빈 dict)이지만 이미 매수함 → 차단 (금호건설 284주 버그 재현 방지)
    assert _already_committed("002990", {}, {"002990"}) is True


def test_not_committed_for_new_ticker():
    # 다른 종목은 매수 허용
    assert _already_committed("005930", {"002990": 71}, {"002990"}) is False


def test_not_committed_when_flat():
    assert _already_committed("002990", {}, set()) is False


# ------------------------------------------------------------------
# 하락 국면 필터 — 시장 약세 시 신규 매수 정지
# ------------------------------------------------------------------

def test_market_bearish_blocks_in_downtrend():
    assert _market_bearish(-1.2) is True    # 시장 -1.2% → 하락 국면


def test_market_bearish_allows_in_uptrend():
    assert _market_bearish(0.8) is False


def test_market_bearish_failsafe_when_unknown():
    # 데이터 없으면(None) 매수 허용 — 데이터 오류로 전량 정지되는 것 방지
    assert _market_bearish(None) is False


def test_market_bearish_threshold_boundary():
    assert _market_bearish(-0.5) is False   # 임계값과 같으면 허용(미만이어야 차단)
    assert _market_bearish(-0.51) is True


# ------------------------------------------------------------------
# 하루 손절 한도 — churn(회전율 폭증) 차단
# ------------------------------------------------------------------

def test_stop_limit_blocks_at_threshold():
    assert _stop_limit_reached(4, 4) is True     # 한도 도달 → 매수 중단
    assert _stop_limit_reached(5, 4) is True


def test_stop_limit_allows_below_threshold():
    assert _stop_limit_reached(0, 4) is False
    assert _stop_limit_reached(3, 4) is False    # 한도 미만 → 매수 허용


def test_stop_limit_disabled_when_zero():
    assert _stop_limit_reached(99, 0) is False   # max<=0 → 비활성
