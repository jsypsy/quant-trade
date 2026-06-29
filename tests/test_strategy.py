"""GoldenCrossStrategy 단위 테스트 — 크로스 밴드(whipsaw 억제) 검증."""
import pandas as pd

from src.strategy.base import Action
from src.strategy.golden_cross import GoldenCrossStrategy


def _action(closes: list[float], band_pct: float) -> Action:
    strat = GoldenCrossStrategy("A", short_window=2, long_window=3, band_pct=band_pct)
    df = pd.DataFrame({"close": closes})
    return strat.generate_signals(df)["A"].action


def _action_state(closes: list[float], band_pct: float = 0.0) -> Action:
    strat = GoldenCrossStrategy("A", short_window=2, long_window=3, band_pct=band_pct, state_entry=True)
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
# 상태 기반 진입(state_entry) — 이미 추세인 종목도 잡는다 (공격적)
# ------------------------------------------------------------------

def test_state_entry_buys_existing_uptrend():
    # 이미 정배열(상승추세). 크로스 '순간'은 지났음.
    closes = [100, 101, 102, 103, 104]
    assert _action(closes, 0.0) == Action.HOLD        # 크로스 기반: 이미 위 → 신호 없음
    assert _action_state(closes) == Action.BUY        # 상태 기반: 정배열 → 즉시 BUY

def test_state_entry_sells_existing_downtrend():
    closes = [104, 103, 102, 101, 100]
    assert _action_state(closes) == Action.SELL       # 역배열 → SELL


def test_state_entry_no_exit_on_reversal_holds():
    """exit_on_reversal=False: 역배열에도 매도 안 함(보유유지), 정배열엔 여전히 매수."""
    strat = GoldenCrossStrategy("A", short_window=2, long_window=3, state_entry=True, exit_on_reversal=False)
    down = strat.generate_signals(pd.DataFrame({"close": [104, 103, 102, 101, 100]}))["A"]
    up = strat.generate_signals(pd.DataFrame({"close": [100, 101, 102, 103, 104]}))["A"]
    assert down.action == Action.HOLD   # 역배열인데 매도 안 함
    assert up.action == Action.BUY      # 정배열은 매수


# ------------------------------------------------------------------
# 데이터 부족 → HOLD
# ------------------------------------------------------------------

def test_insufficient_data_holds():
    assert _action([100, 100], 0.01) == Action.HOLD
