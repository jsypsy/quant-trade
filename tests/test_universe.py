"""동적 유니버스 선정 프로세스 테스트."""
from unittest.mock import MagicMock

from src.data.universe import UniverseProvider
from src.signal.engine import SignalEngine


def _row(ticker, name, price, change, vol_inrt, trade_value=10_000_000_000):
    return {
        "mksc_shrn_iscd": ticker,
        "hts_kor_isnm": name,
        "stck_prpr": str(price),
        "prdy_ctrt": str(change),
        "vol_inrt": str(vol_inrt),
        "acml_tr_pbmn": str(trade_value),
        "acml_vol": "1000000",
    }


def test_fetch_filters_and_ranks_by_change_rate():
    client = MagicMock()
    client.get.return_value = {
        "output": [
            _row("000001", "상승중간", 5000, 3.0, 100),
            _row("000002", "동전주",   500,  9.0, 300),   # 가격 < min_price 제외
            _row("000003", "상승1등",  8000, 7.5, 50),    # 상승률 최상위
            _row("000004", "하락주",   3000, -2.0, 400),  # 등락률 < 0 제외
        ]
    }
    provider = UniverseProvider(client, top_n=10, min_price=1000, min_change_rate=0.0)
    result = provider.fetch()

    # 동전주(가격)·하락주(등락률) 제외, 상승률 내림차순
    assert result == ["000003", "000001"]


def test_fetch_respects_top_n():
    client = MagicMock()
    client.get.return_value = {
        "output": [_row(f"00000{i}", f"종목{i}", 5000, float(i), 100) for i in range(1, 6)]
    }
    provider = UniverseProvider(client, top_n=2, min_price=1000)
    result = provider.fetch()

    assert len(result) == 2
    # 등락률 5.0, 4.0 인 종목이 상위
    assert result == ["000005", "000004"]


def test_set_universe_adds_and_removes_strategies():
    market = MagicMock()
    made = {}

    def factory(ticker):
        s = MagicMock()
        s.ticker = ticker
        made[ticker] = s
        return s

    engine = SignalEngine(factory, market)

    engine.set_universe(["A", "B"])
    assert set(engine._strategies) == {"A", "B"}
    a_instance = engine._strategies["A"]

    # B 제거, C 추가 — 기존 A 인스턴스는 유지(재생성 안 함)
    engine.set_universe(["A", "C"])
    assert set(engine._strategies) == {"A", "C"}
    assert engine._strategies["A"] is a_instance
