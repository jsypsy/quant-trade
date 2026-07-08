"""잔고 파싱 — D+2 정산 예수금(가수도정산금액) 추출."""
from src.portfolio.account import _settle_cash


def test_settle_cash_uses_d2_field():
    # D+2(가수도정산) 값이 있으면 그걸 사용 (미정산 매도대금 제외한 실제 현금)
    assert _settle_cash({"prvs_rcdl_excc_amt": "3000000"}, 5_000_000) == 3_000_000


def test_settle_cash_negative_kept():
    # D+2가 마이너스(미수)면 그대로 유지 → 매수 상한 0 유도
    assert _settle_cash({"prvs_rcdl_excc_amt": "-2400000"}, 100_000) == -2_400_000


def test_settle_cash_fallback_when_missing():
    # 필드 없으면 D+0 예수금으로 폴백 (거래 중단 방지)
    assert _settle_cash({}, 7_000_000) == 7_000_000


def test_settle_cash_fallback_when_blank():
    assert _settle_cash({"prvs_rcdl_excc_amt": ""}, 7_000_000) == 7_000_000


def test_settle_cash_parses_decimal():
    assert _settle_cash({"prvs_rcdl_excc_amt": "3000000.00"}, 0) == 3_000_000
