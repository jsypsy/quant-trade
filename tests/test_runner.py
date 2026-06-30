"""PaperTrader 운용 자본 한도 헬퍼 테스트."""
from src.scheduler.runner import _affordable_qty, _slot_qty


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
