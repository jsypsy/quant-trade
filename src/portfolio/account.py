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
    orderable_qty: int
    avg_price: int
    current_price: int
    current_value: int    # 평가금액
    purchase_amount: int  # 매입금액
    pnl: int              # 평가손익
    pnl_rate: float       # 수익률 (%)


@dataclass
class Balance:
    cash: int             # 예수금 (D+0)
    settle_cash: int      # 가수도정산 예수금 (D+2) — 미정산 매도대금 제외한 실제 현금
    portfolio_value: int  # 총 평가금액
    purchase_amount: int  # 총 매입금액
    pnl: int              # 총 평가손익
    pnl_rate: float       # 총 수익률 (%)
    positions: list[Position]


def _settle_cash(summary: dict, fallback_cash: int) -> int:
    """D+2 정산 예수금(가수도정산금액). 미제공/공란이면 D+0 예수금으로 폴백(거래 중단 방지)."""
    raw = str(summary.get("prvs_rcdl_excc_amt", "")).strip()
    return int(float(raw)) if raw else fallback_cash


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
                orderable_qty=int(row.get("ord_psbl_qty", 0) or 0),
                avg_price=int(float(row.get("pchs_avg_pric", 0) or 0)),
                current_price=int(row.get("prpr", 0) or 0),
                current_value=int(row.get("evlu_amt", 0) or 0),
                purchase_amount=int(row.get("pchs_amt", 0) or 0),
                pnl=int(row.get("evlu_pfls_amt", 0) or 0),
                pnl_rate=float(row.get("evlu_erng_rt", 0) or 0),
            )
            for row in data.get("output1", [])
            if int(row.get("hldg_qty", 0) or 0) > 0
        ]

        summary = data.get("output2", [{}])
        summary = summary[0] if isinstance(summary, list) else summary
        cash = int(summary.get("dnca_tot_amt", 0) or 0)
        settle_cash = _settle_cash(summary, cash)
        total = int(summary.get("tot_evlu_amt", 0) or 0)
        purchase = int(summary.get("pchs_amt_smtl_amt", 0) or 0)
        pnl = int(summary.get("evlu_pfls_smtl_amt", 0) or 0)
        pnl_rate = float(summary.get("evlu_erng_rt1", 0) or 0)

        logger.info(
            "잔고 조회: 예수금={:,}원 (D+2 {:,}원)  총평가={:,}원  보유종목={}개",
            cash, settle_cash, total, len(positions),
        )
        return Balance(
            cash=cash, settle_cash=settle_cash, portfolio_value=total,
            purchase_amount=purchase, pnl=pnl, pnl_rate=pnl_rate,
            positions=positions,
        )
