"""잔고·보유종목·예수금 조회.

엔드포인트: /uapi/domestic-stock/v1/trading/inquire-balance
TR_ID: Paper=VTTC8434R  Real=TTTC8434R

TODO: 응답 필드명(output1/output2)은 공식 examples_llm/잔고조회/ 에서 재확인 권장.
"""
from dataclasses import dataclass

from loguru import logger

from config.settings import settings
from src.kis.client import KISClient

_BALANCE_PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"
_TR_ID = {"vps": "VTTC8434R", "prod": "TTTC8434R"}

_COMMON_PARAMS = {
    "AFHR_FLPR_YN": "N",
    "OFL_YN": "N",
    "INQR_DVSN": "02",
    "UNPR_DVSN": "01",
    "FUND_STTL_ICLD_YN": "N",
    "FNCG_AMT_AUTO_RDPT_YN": "N",
    "PRCS_DVSN": "01",
    "CTX_AREA_FK100": "",
    "CTX_AREA_NK100": "",
}


@dataclass
class Position:
    ticker: str
    name: str
    qty: int
    avg_price: int
    current_value: int   # 평가금액 (원)


@dataclass
class Balance:
    cash: int             # 예수금 (원)
    portfolio_value: int  # 총 평가금액 (원)
    positions: list[Position]


class AccountQuery:
    def __init__(self, client: KISClient) -> None:
        self._client = client

    def get_balance(self) -> Balance:
        tr_id = _TR_ID[settings.kis_env]
        params = {
            "CANO": settings.account_no,
            "ACNT_PRDT_CD": settings.account_product_code,
            **_COMMON_PARAMS,
        }
        data = self._client.get(_BALANCE_PATH, tr_id, params)

        positions = [
            Position(
                ticker=row.get("pdno", ""),
                name=row.get("prdt_name", ""),
                qty=int(row.get("hldg_qty", 0) or 0),
                avg_price=int(float(row.get("pchs_avg_pric", 0) or 0)),
                current_value=int(row.get("evlu_amt", 0) or 0),
            )
            for row in data.get("output1", [])
            if int(row.get("hldg_qty", 0) or 0) > 0
        ]

        summary = data.get("output2", [{}])
        summary = summary[0] if isinstance(summary, list) else summary
        cash = int(summary.get("dnca_tot_amt", 0) or 0)
        total = int(summary.get("tot_evlu_amt", 0) or 0)

        logger.info("잔고 조회: 예수금={:,}원  총평가={:,}원  보유종목={}개", cash, total, len(positions))
        return Balance(cash=cash, portfolio_value=total, positions=positions)
