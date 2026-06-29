"""동적 유니버스 — 전문 데이트레이딩 종목 선정 프로세스.

KIS 거래량순위 API:
  /uapi/domestic-stock/v1/quotations/volume-rank   (TR_ID: FHPST01710000)
  FID_BLNG_CLS_CODE: "0"=평균거래량  "1"=거래증가율  "3"=거래금액(거래대금)순

실전 4단계 단타 선정 프로세스 중 '데이터로 자동화 가능한' 부분을 구현한다.
  1. 거래대금 상위 풀 — 거래대금순 상위 pool_size(≈1~20위). 환금성(체결가능성) 우선.
                        min_trade_value 로 절대 거래대금 하한(예: 500억) 추가 가능.
  2. 가격 필터        — min_price ≤ 현재가 ≤ max_price. 동전주·초고가 제외.
  3. 모멘텀 필터      — 등락률 ≥ min_change_rate. 상승 종목만 (역배열/하락주 배제 근사).
  4. RVOL 필터        — 거래증가율 ≥ min_rvol. 평소 대비 자금 유입('stock in play').
  5. 랭킹             — 등락률(상승률) 내림차순 → 상위 top_n ('1등 대장주' 휴리스틱).

자동화 못 하는 단계(한계, 별도 데이터/계층 필요):
  · 주도 테마·뉴스/공시 연계 '1등주'  → 뉴스·테마 피드 없음. 상승률 1등으로 근사만 함.
  · 차트 타점(신고가 돌파·장대양봉·눌림목) → 유니버스가 아닌 전략(진입) 계층.
  · 체결강도≥100%·호가창 검증           → 진입 직전 검증. 호가/체결 API 별도 필요.
  · 시가총액 하한·정배열/역배열 필터     → volume-rank 응답에 없음. 추후 보강 대상.

TODO: 응답 필드명·거래증가율(vol_inrt) 단위·거래대금(acml_tr_pbmn) 단위는 KIS 공식
      examples_llm/거래량순위/ 와 실거래 응답으로 재확인 후 임계값 보정 권장.
      (min_rvol·min_trade_value 는 단위 확인 전까지 기본 0=비활성. 랭킹은 단위와 무관.)
"""
from dataclasses import dataclass

from loguru import logger

from src.kis.client import KISClient
from src.utils.names import register as _register_names

_VOLUME_RANK_PATH = "/uapi/domestic-stock/v1/quotations/volume-rank"
_VOLUME_RANK_TR_ID = "FHPST01710000"

# 시장 구분 (FID_INPUT_ISCD)
MARKET_KOSPI = "0001"
MARKET_KOSDAQ = "1001"
MARKET_ALL = "0000"

# 소속 구분 (FID_BLNG_CLS_CODE)
SORT_AVG_VOL = "0"       # 평균거래량
SORT_VOL_INCREASE = "1"  # 거래증가율
SORT_TRADE_VALUE = "3"   # 거래금액(거래대금)순

# 거래대금 하한 참고값 (단위: 원). acml_tr_pbmn 단위 확인 후 min_trade_value 로 사용.
TRADE_VALUE_50B = 50_000_000_000    # 500억
TRADE_VALUE_100B = 100_000_000_000  # 1,000억


@dataclass
class RankedStock:
    ticker: str
    name: str
    price: int           # 현재가
    volume: int          # 누적거래량
    trade_value: int     # 누적거래대금
    change_rate: float   # 등락률 (%)        = prdy_ctrt
    vol_increase: float  # 거래증가율(RVOL)  = vol_inrt


class UniverseProvider:
    """장중 주기적으로 실전 단타 기준에 따라 매매 후보를 선정한다."""

    def __init__(
        self,
        client: KISClient,
        *,
        market: str = MARKET_KOSPI,
        pool_size: int = 20,
        top_n: int = 10,
        min_price: int = 1000,
        max_price: int = 0,            # 0 = 상한 없음
        min_change_rate: float = 0.0,  # 등락률 % 하한 (상승 종목 위주)
        min_rvol: float = 0.0,         # 거래증가율 하한 (단위 확인 후 보정)
        min_trade_value: int = 0,      # 거래대금 하한 원 (단위 확인 후 보정, 예: TRADE_VALUE_50B)
    ) -> None:
        self._client = client
        self._market = market
        self._pool_size = pool_size
        self._top_n = top_n
        self._min_price = min_price
        self._max_price = max_price
        self._min_change_rate = min_change_rate
        self._min_rvol = min_rvol
        self._min_trade_value = min_trade_value

    def fetch(self) -> list[str]:
        """선정 프로세스를 거친 유니버스 종목코드 리스트(상위 top_n)를 반환한다."""
        pool = self._fetch_pool()
        _register_names({s.ticker: s.name for s in pool})   # 알림용 종목명 등록
        selected = self._select(pool)
        logger.info(
            "[유니버스] 거래대금 풀 {}건 → 필터·상승률순 상위 {} 선정: {}",
            len(pool), len(selected),
            ", ".join(f"{s.name}({s.ticker}) {s.change_rate:+.1f}%" for s in selected),
        )
        return [s.ticker for s in selected]

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _select(self, pool: list[RankedStock]) -> list[RankedStock]:
        filtered = [
            s for s in pool
            if s.price >= self._min_price
            and (self._max_price == 0 or s.price <= self._max_price)
            and s.change_rate >= self._min_change_rate
            and s.vol_increase >= self._min_rvol
            and s.trade_value >= self._min_trade_value
        ]
        filtered.sort(key=lambda s: s.change_rate, reverse=True)
        return filtered[: self._top_n]

    def _fetch_pool(self) -> list[RankedStock]:
        """거래대금 상위로 유동성 풀을 구성한다 (상위 pool_size개)."""
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_COND_SCR_DIV_CODE": "20171",
            "FID_INPUT_ISCD": self._market,
            "FID_DIV_CLS_CODE": "0",
            "FID_BLNG_CLS_CODE": SORT_TRADE_VALUE,
            "FID_TRGT_CLS_CODE": "111111111",
            "FID_TRGT_EXLS_CLS_CODE": "000000000",
            "FID_INPUT_PRICE_1": "",
            "FID_INPUT_PRICE_2": "",
            "FID_VOL_CNT": "",
            "FID_INPUT_DATE_1": "",
        }
        data = self._client.get(_VOLUME_RANK_PATH, _VOLUME_RANK_TR_ID, params)
        rows = data.get("output", []) or []

        pool: list[RankedStock] = []
        for row in rows[: self._pool_size]:
            ticker = row.get("mksc_shrn_iscd", "")
            if not ticker:
                continue
            pool.append(
                RankedStock(
                    ticker=ticker,
                    name=row.get("hts_kor_isnm", ""),
                    price=int(row.get("stck_prpr", 0) or 0),
                    volume=int(row.get("acml_vol", 0) or 0),
                    trade_value=int(row.get("acml_tr_pbmn", 0) or 0),
                    change_rate=float(row.get("prdy_ctrt", 0) or 0),
                    vol_increase=float(row.get("vol_inrt", 0) or 0),
                )
            )
        return pool
