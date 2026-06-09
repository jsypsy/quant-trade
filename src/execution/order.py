"""주문 실행.

dry_run=True(기본) 이면 API 를 호출하지 않고 로그만 남긴다.
실제 주문은 dry_run=False 로 명시해야 한다.

TR_ID (모의/실전 × 매수/매도):
  vps  BUY  → VTTC0802U
  vps  SELL → VTTC0801U
  prod BUY  → TTTC0802U   # TODO: 공식 examples_llm/주식주문/ 에서 재확인
  prod SELL → TTTC0801U   # TODO: 동일
"""
from dataclasses import dataclass, field
from enum import Enum

from loguru import logger

from config.settings import settings
from src.kis.client import KISClient

_KR_ORDER_PATH = "/uapi/domestic-stock/v1/trading/order-cash"
_US_ORDER_PATH = "/uapi/overseas-stock/v1/trading/order"
_NCCS_PATH     = "/uapi/domestic-stock/v1/trading/inquire-nccs"
_NCCS_TR_ID    = {"vps": "VTTC8036R", "prod": "TTTC8036R"}

# 국내
_KR_TR_ID: dict[tuple[str, str], str] = {
    ("vps",  "BUY"):  "VTTC0802U",
    ("vps",  "SELL"): "VTTC0801U",
    ("prod", "BUY"):  "TTTC0802U",
    ("prod", "SELL"): "TTTC0801U",
}
# 해외 (미국)  # TODO: 공식 examples_llm/해외주식주문/ 에서 재확인 권장
_US_TR_ID: dict[tuple[str, str], str] = {
    ("vps",  "BUY"):  "VTTT1002U",
    ("vps",  "SELL"): "VTTT1001U",  # 모의투자 매도 TR_ID (VTTT1006U 는 실전 매도용)
    ("prod", "BUY"):  "TTTT1002U",
    ("prod", "SELL"): "TTTT1006U",
}
# 시세 API는 3자리(NAS), 주문 API는 4자리(NASD) — KIS API 비일관성 대응
_EXCD_ORDER: dict[str, str] = {"NAS": "NASD", "NYS": "NYSE", "AME": "AMEX"}


class OrderType(Enum):
    LIMIT  = "01"   # 지정가 (기본)
    MARKET = "00"   # 시장가 (명시적으로만)


@dataclass
class OrderRequest:
    ticker: str
    side: str               # "BUY" | "SELL"
    qty: int
    price: float            # 지정가 금액; 시장가일 때는 0
    order_type: OrderType = OrderType.LIMIT
    market_type: str = "KR" # "KR" | "US"
    excd: str = "NAS"       # 해외 거래소 코드 (US 전용)


@dataclass
class OrderResult:
    success: bool
    ticker: str
    side: str
    qty: int
    price: float
    order_no: str = ""
    dry_run: bool = False
    market_type: str = "KR"
    error: str = ""


class OrderExecutor:
    def __init__(self, client: KISClient, dry_run: bool = True, us_client: KISClient | None = None) -> None:
        self._client = client
        self._us_client = us_client  # US 주문은 PROD URL 필요 (VPS 서버 미지원)
        self.dry_run = dry_run

    def submit(self, req: OrderRequest) -> OrderResult:
        if self.dry_run:
            return self._dry_run(req)
        return self._send(req)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _dry_run(self, req: OrderRequest) -> OrderResult:
        unit = "USD" if req.market_type == "US" else "원"
        logger.info(
            "[DRY-RUN][{}] {} {} {}주 @{:.2f}{}  ({})",
            req.market_type, req.side, req.ticker, req.qty, req.price, unit, req.order_type.name,
        )
        return OrderResult(
            success=True, ticker=req.ticker, side=req.side,
            qty=req.qty, price=req.price, order_no="DRY-RUN",
            dry_run=True, market_type=req.market_type,
        )

    def _send(self, req: OrderRequest) -> OrderResult:
        key = (settings.kis_env, req.side)
        if req.market_type == "US":
            tr_id  = _US_TR_ID.get(key)
            path   = _US_ORDER_PATH
            body   = self._us_body(req)
            client = self._us_client or self._client  # US 주문은 PROD URL 클라이언트 사용
        else:
            tr_id  = _KR_TR_ID.get(key)
            path   = _KR_ORDER_PATH
            body   = self._kr_body(req)
            client = self._client

        if tr_id is None:
            raise ValueError(f"TR_ID 미정의: env={settings.kis_env}, side={req.side}, market={req.market_type}")

        try:
            data = client.post(path, tr_id, body)
            order_no = data.get("output", {}).get("ODNO", "")
            logger.info("[ORDER][{}] {} {} {}주 → 주문번호 {}", req.market_type, req.side, req.ticker, req.qty, order_no)
            return OrderResult(
                success=True, ticker=req.ticker, side=req.side,
                qty=req.qty, price=req.price, order_no=order_no, market_type=req.market_type,
            )
        except Exception as exc:
            logger.error("[ORDER][{}] {} {} 실패: {}", req.market_type, req.side, req.ticker, exc)
            return OrderResult(
                success=False, ticker=req.ticker, side=req.side,
                qty=req.qty, price=req.price, market_type=req.market_type, error=str(exc),
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
            "INQR_DVSN_1":    "0",
            "INQR_DVSN_2":    "0",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }
        try:
            data = self._client.get(_NCCS_PATH, tr_id, params)
            return {row["pdno"] for row in data.get("output", []) if row.get("pdno")}
        except Exception as exc:
            logger.warning("[OM] 미체결 조회 실패 — pending 유지: {}", exc)
            return None

    def _us_body(self, req: OrderRequest) -> dict:
        return {
            "CANO":           settings.account_no,
            "ACNT_PRDT_CD":   settings.account_product_code,
            "OVRS_EXCG_CD":   _EXCD_ORDER.get(req.excd, req.excd),
            "PDNO":           req.ticker,
            "ORD_DVSN":       "00",           # 미국은 시장가 기본
            "ORD_QTY":        str(req.qty),
            "OVRS_ORD_UNPR":  f"{req.price:.2f}" if req.order_type == OrderType.LIMIT else "0",
            "ORD_SVR_DVSN_CD": "0",
        }
