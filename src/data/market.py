"""시세 / 차트 데이터 조회 (한국 주식).

KIS 국내 엔드포인트:
  현재가:   /uapi/domestic-stock/v1/quotations/inquire-price                  (TR: FHKST01010100)
  일봉차트:  /uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice  (TR: FHKST03010100)
  분봉차트:  /uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice   (TR: FHKST03010200)

일봉차트는 한 번에 최대 30 영업일을 반환합니다.
분봉차트는 당일 데이터만 제공합니다.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from src.kis.client import KISClient
from src.kis.models import CurrentPriceOutput, OHLCVItem

_KST = ZoneInfo("Asia/Seoul")

_PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-price"
_PRICE_TR_ID = "FHKST01010100"
_DAILY_PATH = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
_DAILY_TR_ID = "FHKST03010100"
_MINUTE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
_MINUTE_TR_ID = "FHKST03010200"


class MarketData:
    def __init__(self, client: KISClient) -> None:
        self._client = client

    # ------------------------------------------------------------------
    # 국내 주식
    # ------------------------------------------------------------------

    def get_current_price(self, ticker: str) -> CurrentPriceOutput:
        data = self._client.get(
            _PRICE_PATH,
            _PRICE_TR_ID,
            params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": ticker},
        )
        return CurrentPriceOutput(**data["output"])

    def get_daily_ohlcv(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        """국내 일봉 OHLCV. start/end: "YYYYMMDD". 오름차순 반환."""
        data = self._client.get(
            _DAILY_PATH,
            _DAILY_TR_ID,
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": ticker,
                "FID_INPUT_DATE_1": start,
                "FID_INPUT_DATE_2": end,
                "FID_PERIOD_DIV_CODE": "D",
                "FID_ORG_ADJ_PRC": "0",
            },
        )
        items = [OHLCVItem(**row) for row in data["output2"]]
        return _kr_to_dataframe(items)

    def get_minute_ohlcv(self, ticker: str, cnt: int = 30) -> pd.DataFrame:
        """국내 1분봉 OHLCV. 당일 데이터, 최근 cnt 봉 반환."""
        now_str = datetime.now(tz=_KST).strftime("%H%M%S")
        data = self._client.get(
            _MINUTE_PATH,
            _MINUTE_TR_ID,
            params={
                "FID_ETC_CLS_CODE": "0",
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": ticker,
                "FID_INPUT_HOUR_1": now_str,
                "FID_PW_DATA_INCU_YN": "Y",
            },
        )
        rows = data.get("output2", [])
        return _kr_minute_to_dataframe(rows, cnt)



# ------------------------------------------------------------------
# 내부 변환 함수
# ------------------------------------------------------------------

def _kr_to_dataframe(items: list[OHLCVItem]) -> pd.DataFrame:
    if not items:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    rows = [
        {
            "date": item.stck_bsop_date,
            "open": item.stck_oprc,
            "high": item.stck_hgpr,
            "low": item.stck_lwpr,
            "close": item.stck_clpr,
            "volume": item.acml_vol,
        }
        for item in items
    ]
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
    return df.sort_values("date").reset_index(drop=True)


def _kr_minute_to_dataframe(rows: list[dict], cnt: int) -> pd.DataFrame:
    """국내 분봉 응답 → DataFrame. 응답은 최신순이므로 역순 정렬."""
    if not rows:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    parsed = []
    for r in rows[:cnt]:
        try:
            date_str = r.get("stck_bsop_date", "")
            time_str = r.get("stck_cntg_hour", "000000")
            parsed.append({
                "date":   pd.Timestamp(f"{date_str} {time_str[:2]}:{time_str[2:4]}:{time_str[4:6]}"),
                "open":   int(r.get("stck_oprc", 0) or 0),
                "high":   int(r.get("stck_hgpr", 0) or 0),
                "low":    int(r.get("stck_lwpr", 0) or 0),
                "close":  int(r.get("stck_prpr", 0) or 0),
                "volume": int(r.get("cntg_vol", 0) or 0),
            })
        except (ValueError, TypeError):
            continue
    if not parsed:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    df = pd.DataFrame(parsed)
    return df.sort_values("date").reset_index(drop=True)


