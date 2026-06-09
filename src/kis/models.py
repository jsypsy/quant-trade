"""KIS API 응답 DTO (pydantic).

숫자 필드는 KIS가 JSON에서 문자열로 내려주므로 lax 모드 coercion 으로 처리.
빈 문자열("")은 before-validator 에서 0으로 변환.
"""
from pydantic import BaseModel, field_validator


class CurrentPriceOutput(BaseModel):
    stck_prpr: int   # 현재가
    prdy_vrss: int   # 전일 대비
    prdy_ctrt: float # 전일 대비율 (%)
    stck_oprc: int   # 시가
    stck_hgpr: int   # 고가
    stck_lwpr: int   # 저가
    acml_vol: int    # 누적 거래량

    @field_validator("stck_prpr", "prdy_vrss", "stck_oprc", "stck_hgpr", "stck_lwpr", "acml_vol", mode="before")
    @classmethod
    def _int_or_zero(cls, v: object) -> object:
        return 0 if v == "" or v is None else v


class OHLCVItem(BaseModel):
    stck_bsop_date: str  # 기준일자 YYYYMMDD
    stck_oprc: int       # 시가
    stck_hgpr: int       # 고가
    stck_lwpr: int       # 저가
    stck_clpr: int       # 종가
    acml_vol: int        # 거래량

    @field_validator("stck_oprc", "stck_hgpr", "stck_lwpr", "stck_clpr", "acml_vol", mode="before")
    @classmethod
    def _int_or_zero(cls, v: object) -> object:
        return 0 if v == "" or v is None else v
