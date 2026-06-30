"""백테스트 엔진 테스트 — 비용모델 + 브라켓(손절/익절)."""
import pandas as pd

from src.backtest.engine import CostModel, backtest_bracket


def _ramp(start: float, step: float, n: int) -> pd.DataFrame:
    """단조 상승/하락 OHLCV. high/low = close ± 0.05%."""
    closes = [start + step * i for i in range(n)]
    return pd.DataFrame({
        "open": closes,
        "high": [c * 1.0005 for c in closes],
        "low": [c * 0.9995 for c in closes],
        "close": closes,
    })


def test_round_trip_cost_default():
    c = CostModel()
    # 0.015%*2 + 0.18% + 0.1%*2 = 0.41%
    assert abs(c.round_trip - 0.0041) < 1e-9


def test_uptrend_takes_profit():
    # 꾸준한 상승 → 정배열 진입 후 +4% 익절이 떠야 함
    df = _ramp(100.0, 1.0, 40)
    r = backtest_bracket(df, short=3, long=10, take_profit=0.04, stop_loss=0.02)
    assert r.n_trades >= 1
    assert r.n_tp >= 1            # 익절 발생


def test_downtrend_no_entry_or_loss():
    # 꾸준한 하락 → 정배열 진입 자체가 거의 없음(매수 안 함)
    df = _ramp(200.0, -1.0, 40)
    r = backtest_bracket(df, short=3, long=10)
    assert r.n_tp == 0           # 익절은 없음


def test_no_trades_empty_result():
    df = _ramp(100.0, 0.0, 5)    # 데이터 부족(long+1 미만 유효)
    r = backtest_bracket(df, short=3, long=10)
    assert r.n_trades == 0 and r.total_return == 0.0
