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


def test_fetch_filters_and_ranks_by_trade_value():
    client = MagicMock()
    client.get.return_value = {
        "output": [
            _row("000001", "중간거래대금", 5000, 3.0, 100, trade_value=20_000_000_000),
            _row("000002", "동전주",       500,  9.0, 300, trade_value=99_000_000_000),  # 가격<min 제외
            _row("000003", "최대거래대금", 8000, 7.5, 50,  trade_value=50_000_000_000),
            _row("000004", "하락주",       3000, -2.0, 400, trade_value=80_000_000_000), # 등락<0 제외
        ]
    }
    provider = UniverseProvider(client, top_n=10, min_price=1000, min_change_rate=0.0)
    result = provider.fetch()

    # 동전주(가격)·하락주(등락률) 제외 후 거래대금 내림차순: 000003(50B) > 000001(20B)
    assert result == ["000003", "000001"]


def test_max_change_rate_excludes_rockets():
    client = MagicMock()
    client.get.return_value = {
        "output": [
            _row("000001", "대형안정", 5000, 3.0,  100, trade_value=50_000_000_000),
            _row("000002", "급등주",   5000, 15.0, 100, trade_value=90_000_000_000),  # +15% > 상한
        ]
    }
    provider = UniverseProvider(client, top_n=10, min_price=1000, max_change_rate=8.0)
    result = provider.fetch()

    # 급등주(+15%)는 거래대금 1등이어도 상한 초과로 제외
    assert result == ["000001"]


def test_fetch_respects_top_n():
    client = MagicMock()
    client.get.return_value = {
        "output": [
            _row(f"00000{i}", f"종목{i}", 5000, 3.0, 100, trade_value=i * 1_000_000_000)
            for i in range(1, 6)
        ]
    }
    provider = UniverseProvider(client, top_n=2, min_price=1000)
    result = provider.fetch()

    assert len(result) == 2
    # 거래대금 5B, 4B 인 종목이 상위
    assert result == ["000005", "000004"]


def test_market_change_is_pool_median():
    client = MagicMock()
    client.get.return_value = {
        "output": [
            _row("000001", "A", 5000, 1.0,  100, trade_value=30_000_000_000),
            _row("000002", "B", 5000, -1.0, 100, trade_value=20_000_000_000),
            _row("000003", "C", 5000, -3.0, 100, trade_value=10_000_000_000),
        ]
    }
    provider = UniverseProvider(client, min_price=1000)
    provider.fetch()

    # 풀 전체 등락률 중앙값 median(1, -1, -3) = -1.0 (필터 전 표본)
    assert provider.market_change == -1.0


def test_market_change_none_before_fetch():
    provider = UniverseProvider(MagicMock(), min_price=1000)
    assert provider.market_change is None


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
