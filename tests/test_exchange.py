"""거래소(KRX/NXT/SOR) 결정 로직 테스트.

핵심 안전장치: 모의(vps)는 NXT 미지원 → 어떤 KR_EXCHANGE 값이 와도 KRX 로 강제.
"""
from config.settings import KISSettings


def _s(env: str, exch: str) -> KISSettings:
    return KISSettings(kis_env=env, kr_exchange=exch)


# ------------------------------------------------------------------
# 실전(prod) — 설정대로
# ------------------------------------------------------------------

def test_prod_krx_default():
    s = _s("prod", "KRX")
    assert s.exchange_id == "KRX"
    assert s.is_nxt is False
    assert s.market_div_code == "J"


def test_prod_sor_uses_unified_quote():
    s = _s("prod", "SOR")
    assert s.exchange_id == "SOR"
    assert s.is_nxt is True
    assert s.market_div_code == "UN"


def test_prod_nxt():
    s = _s("prod", "NXT")
    assert s.exchange_id == "NXT"
    assert s.is_nxt is True
    assert s.market_div_code == "UN"


def test_prod_lowercase_normalized():
    assert _s("prod", "sor").exchange_id == "SOR"


def test_prod_invalid_falls_back_to_krx():
    s = _s("prod", "NASDAQ")
    assert s.exchange_id == "KRX"
    assert s.is_nxt is False


# ------------------------------------------------------------------
# 모의(vps) — 무조건 KRX 강제 (NXT 미지원)
# ------------------------------------------------------------------

def test_vps_forces_krx_even_if_sor_requested():
    s = _s("vps", "SOR")
    assert s.exchange_id == "KRX"
    assert s.is_nxt is False
    assert s.market_div_code == "J"


def test_vps_forces_krx_even_if_nxt_requested():
    assert _s("vps", "NXT").exchange_id == "KRX"
