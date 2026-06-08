"""모의투자 연결 검증 스크립트.

실행: python scripts/check_auth.py
성공 기준: 토큰 발급 OK + 삼성전자(005930) 현재가 출력 OK
"""
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from loguru import logger

from config.settings import settings
from src.kis.auth import KISAuth

# TODO: TR_ID·파라미터명은 공식 예제 examples_llm/주식현재가시세/ 기준으로 확인
_PRICE_URL = "/uapi/domestic-stock/v1/quotations/inquire-price"
_PRICE_TR_ID = "FHKST01010100"


def main() -> None:
    logger.info("환경: {} | {}", settings.kis_env, settings.base_url)

    # ── Step 1: 액세스 토큰 발급 ─────────────────────────────────────
    logger.info("Step 1: 액세스 토큰 발급")
    auth = KISAuth()
    try:
        token = auth.get_access_token()
    except httpx.HTTPStatusError as e:
        logger.error("토큰 발급 실패 HTTP {}: {}", e.response.status_code, e.response.text)
        sys.exit(1)
    except Exception as e:
        logger.error("토큰 발급 실패: {}", e)
        sys.exit(1)

    logger.success("토큰 발급 OK (앞 20자: {}...)", token[:20])

    # ── Step 2: 삼성전자 현재가 조회 ─────────────────────────────────
    logger.info("Step 2: 삼성전자(005930) 현재가 조회")
    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": settings.app_key,
        "appsecret": settings.app_secret,
        "tr_id": _PRICE_TR_ID,
    }
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": "005930",
    }

    try:
        resp = httpx.get(
            settings.base_url + _PRICE_URL,
            headers=headers,
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as e:
        logger.error("HTTP {}: {}", e.response.status_code, e.response.text)
        sys.exit(1)
    except Exception as e:
        logger.error("현재가 조회 실패: {}", e)
        sys.exit(1)

    if data.get("rt_cd") != "0":
        logger.error("API 오류 [{}]: {}", data.get("msg_cd"), data.get("msg1"))
        sys.exit(1)

    out = data["output"]
    price = int(out["stck_prpr"])
    change_pct = out["prdy_ctrt"]
    logger.success("삼성전자(005930) 현재가: {:,}원 (전일 대비 {}%)", price, change_pct)
    logger.success("연결 검증 완료 ✓")


if __name__ == "__main__":
    main()
