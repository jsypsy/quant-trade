"""GoldenCrossStrategy 단위 테스트 — 크로스 밴드(whipsaw 억제) 검증."""
import pandas as pd

from src.strategy.base import Action
from src.strategy.golden_cross import GoldenCrossStrategy


def _action(closes: list[float], band_pct: float) -> Action:
    strat = GoldenCrossStrategy("A", short_window=2, long_window=3, band_pct=band_pct)
    df = pd.DataFrame({"close": closes})
    return strat.generate_signals(df)["A"].action


# ------------------------------------------------------------------
# band=0 — 기존 단순 크로스 동작 보존
# ------------------------------------------------------------------

def test_buy_on_cross_no_band():
    assert _action([100, 100, 100, 100, 100, 101], 0.0) == Action.BUY

def test_sell_on_cross_no_band():
    assert _action([100, 100, 100, 100, 100, 99], 0.0) == Action.SELL


# ------------------------------------------------------------------
# band=1% — 미세한(노이즈) 크로스는 HOLD 로 억제
# ------------------------------------------------------------------

def test_small_cross_suppressed_by_band():
    # 약 0.17% 격차 → 1% 밴드 안 → HOLD
    assert _action([100, 100, 100, 100, 100, 101], 0.01) == Action.HOLD
    assert _action([100, 100, 100, 100, 100, 99], 0.01) == Action.HOLD


# ------------------------------------------------------------------
# band=1% — 결정적 크로스는 통과
# ------------------------------------------------------------------

def test_decisive_cross_passes_band():
    assert _action([100, 100, 100, 100, 100, 110], 0.01) == Action.BUY
    assert _action([100, 100, 100, 100, 100, 90], 0.01) == Action.SELL


# ------------------------------------------------------------------
# 데이터 부족 → HOLD
# ------------------------------------------------------------------

def test_insufficient_data_holds():
    assert _action([100, 100], 0.01) == Action.HOLD
