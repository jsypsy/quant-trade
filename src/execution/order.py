"""주문 실행.

dry_run=True(기본) 이면 API 를 호출하지 않고 로그만 남긴다.
실제 주문은 dry_run=False 로 명시해야 한다.

TR_ID (모의/실전 × 매수/매도):
  KRX 단독(구버전):  vps BUY VTTC0802U · SELL VTTC0801U / prod BUY TTTC0802U · SELL TTTC0801U
  NXT/SOR(신버전):   vps BUY VTTC0012U · SELL VTTC0011U / prod BUY TTTC0012U · SELL TTTC0011U
                     + body 에 EXCG_ID_DVSN_CD(KRX/NXT/SOR)·SLL_TYPE·CNDT_PRIC 필요.

거래소(EXCG_ID_DVSN_CD)는 settings.exchange_id 로 결정한다. 모의(vps)는 NXT 미지원 → 항상 KRX.
"""
from dataclasses import dataclass
from enum import Enum

from loguru import logger

from config.settings import settings
from src.kis.client import KISClient

_KR_ORDER_PATH = "/uapi/domestic-stock/v1/trading/order-cash"
_NCCS_PATH     = "/uapi/domestic-stock/v1/trading/inquire-psbl-rvsecncl"
_NCCS_TR_ID    = {"vps": "VTTC8036R", "prod": "TTTC8036R"}

_KR_TR_ID: dict[tuple[str, str], str] = {
    ("vps",  "BUY"):  "VTTC0802U",
    ("vps",  "SELL"): "VTTC0801U",
    ("prod", "BUY"):  "TTTC0802U",
    ("prod", "SELL"): "TTTC0801U",
}

# NXT/SOR(통합) 주문용 신버전 TR_ID. body 에 EXCG_ID_DVSN_CD 포함 필수.
_KR_TR_ID_NXT: dict[tuple[str, str], str] = {
    ("vps",  "BUY"):  "VTTC0012U",
    ("vps",  "SELL"): "VTTC0011U",
    ("prod", "BUY"):  "TTTC0012U",
    ("prod", "SELL"): "TTTC0011U",
}


class OrderType(Enum):
    LIMIT  = "00"   # 지정가 (기본)
    MARKET = "01"   # 시장가 (명시적으로만)


@dataclass
class OrderRequest:
    ticker: str
    side: str               # "BUY" | "SELL"
    qty: int
    price: float            # 지정가 금액; 시장가일 때는 0
    order_type: OrderType = OrderType.LIMIT


@dataclass
class OrderResult:
    success: bool
    ticker: str
    side: str
    qty: int
    price: float
    order_no: str = ""
    dry_run: bool = False
    error: str = ""


class OrderExecutor:
    def __init__(self, client: KISClient, dry_run: bool = True) -> None:
        self._client = client
        self.dry_run = dry_run

    def submit(self, req: OrderRequest) -> OrderResult:
        if self.dry_run:
            return self._dry_run(req)
        return self._send(req)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _dry_run(self, req: OrderRequest) -> OrderResult:
        logger.info(
            "[DRY-RUN][KR] {} {} {}주 @{:.0f}원  ({})",
            req.side, req.ticker, req.qty, req.price, req.order_type.name,
        )
        return OrderResult(
            success=True, ticker=req.ticker, side=req.side,
            qty=req.qty, price=req.price, order_no="DRY-RUN", dry_run=True,
        )

    def _send(self, req: OrderRequest) -> OrderResult:
        key = (settings.kis_env, req.side)
        tr_map = _KR_TR_ID_NXT if settings.is_nxt else _KR_TR_ID
        tr_id = tr_map.get(key)
        if tr_id is None:
            raise ValueError(f"TR_ID 미정의: env={settings.kis_env}, side={req.side}")
        body = self._kr_body_nxt(req) if settings.is_nxt else self._kr_body(req)

        try:
            data = self._client.post(_KR_ORDER_PATH, tr_id, body)
            order_no = data.get("output", {}).get("ODNO", "")
            logger.info("[ORDER][KR] {} {} {}주 → 주문번호 {}", req.side, req.ticker, req.qty, order_no)
            return OrderResult(
                success=True, ticker=req.ticker, side=req.side,
                qty=req.qty, price=req.price, order_no=order_no,
            )
        except Exception as exc:
            logger.error("[ORDER][KR] {} {} 실패: {}", req.side, req.ticker, exc)
            return OrderResult(
                success=False, ticker=req.ticker, side=req.side,
                qty=req.qty, price=req.price, error=str(exc),
            )

    def _kr_body(self, req: OrderRequest) -> dict:
        return {
            "CANO":         settings.account_no,
            "ACNT_PRDT_CD": settings.account_product_code,
            "PDNO":         req.ticker,
            "ORD_DVSN":     req.order_type.value,
            "ORD_QTY":      str(req.qty),
            "ORD_UNPR":     str(int(req.price)) if req.order_type == OrderType.LIMIT else "0",
        }

    def _kr_body_nxt(self, req: OrderRequest) -> dict:
        """NXT/SOR(통합) 주문 body. KRX body + 거래소구분·매도유형·조건가격."""
        body = self._kr_body(req)
        body["EXCG_ID_DVSN_CD"] = settings.exchange_id   # KRX | NXT | SOR
        body["SLL_TYPE"] = ""                             # 일반 매도/매수 (공매도 아님)
        body["CNDT_PRIC"] = ""                            # 조건가 (조건부지정가만 사용)
        return body

    def get_unfilled_tickers(self) -> set[str] | None:
        """KIS 미체결 조회 → 현재 미체결 종목 코드 집합 반환.

        dry_run=True 이면 set() 반환 (전부 체결된 것으로 간주).
        API 실패 시 None 반환 → 호출자는 pending 유지.
        """
        if self.dry_run:
            return set()
        tr_id = _NCCS_TR_ID.get(settings.kis_env, "VTTC8036R")
        params = {
            "CANO":           settings.account_no,
            "ACNT_PRDT_CD":   settings.account_product_code,
            "INQR_DVSN_1":    "1",
            "INQR_DVSN_2":    "0",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }
        try:
            data = self._client.get(_NCCS_PATH, tr_id, params)
            return {row["pdno"] for row in data.get("output", []) if row.get("pdno")}
        except Exception as exc:
            # 모의투자는 inquire-psbl-rvsecncl 미지원 → pending 강제 해제
            if settings.is_paper and "90000000" in str(exc):
                logger.info("[OM] 모의투자 미체결 조회 미지원 — pending 전체 해제")
                return set()
            logger.warning("[OM] 미체결 조회 실패 — pending 유지: {}", exc)
            return None

