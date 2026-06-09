"""KIS REST 공통 클라이언트.

- 헤더 자동 구성 (Bearer 토큰 · appkey · appsecret · tr_id)
- 유량제한(EGW00201) + HTTP 4xx/5xx + 네트워크 오류 → 지수 백오프 재시도
- 호출 간 최소 간격 보장 (스로틀)
"""
import time
import threading
from typing import Any

import httpx
from loguru import logger

from config.settings import settings
from src.kis.auth import KISAuth

_RATE_LIMIT_CODE = "EGW00201"
_MAX_RETRIES = 3
_MIN_INTERVAL = 0.12   # ~8 req/s (모의투자 안전 마진 포함)
_RETRY_HTTP_CODES = {429, 500, 502, 503}


class KISAPIError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"[{code}] {message}")


class KISClient:
    def __init__(self, auth: KISAuth, base_url: str | None = None) -> None:
        self._auth = auth
        self._base_url = base_url  # None → settings.base_url 사용
        self._lock = threading.Lock()
        self._last_call: float = 0.0

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def get(self, path: str, tr_id: str, params: dict[str, Any]) -> dict:
        return self._request("GET", path, tr_id, params=params)

    def post(self, path: str, tr_id: str, body: dict[str, Any]) -> dict:
        return self._request("POST", path, tr_id, json=body)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, tr_id: str, **kwargs: Any) -> dict:
        url = (self._base_url or settings.base_url) + path

        for attempt in range(_MAX_RETRIES):
            self._throttle()
            headers = self._build_headers(tr_id)

            try:
                resp = httpx.request(method, url, headers=headers, timeout=10, **kwargs)
                resp.raise_for_status()
                data: dict = resp.json()
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt < _MAX_RETRIES - 1:
                    wait = 2 ** attempt
                    logger.warning("네트워크 오류, {}초 후 재시도 ({}/{}): {}", wait, attempt + 1, _MAX_RETRIES, exc)
                    time.sleep(wait)
                    continue
                raise
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in _RETRY_HTTP_CODES and attempt < _MAX_RETRIES - 1:
                    wait = 2 ** attempt
                    logger.warning("HTTP {}, {}초 후 재시도 ({}/{})\n응답 본문: {}", exc.response.status_code, wait, attempt + 1, _MAX_RETRIES, exc.response.text[:500])
                    time.sleep(wait)
                    continue
                raise

            if data.get("msg_cd") == _RATE_LIMIT_CODE and attempt < _MAX_RETRIES - 1:
                wait = 2 ** attempt
                logger.warning("유량제한(EGW00201), {}초 후 재시도 ({}/{})", wait, attempt + 1, _MAX_RETRIES)
                time.sleep(wait)
                continue

            if data.get("rt_cd") != "0":
                raise KISAPIError(data.get("msg_cd", ""), data.get("msg1", ""))

            return data

        raise KISAPIError("MAX_RETRY", f"최대 재시도 횟수 초과 ({_MAX_RETRIES}회)")

    def _build_headers(self, tr_id: str) -> dict[str, str]:
        return {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self._auth.get_access_token()}",
            "appkey": self._auth.app_key,
            "appsecret": self._auth.app_secret,
            "tr_id": tr_id,
        }

    def _throttle(self) -> None:
        with self._lock:
            elapsed = time.time() - self._last_call
            if elapsed < _MIN_INTERVAL:
                time.sleep(_MIN_INTERVAL - elapsed)
            self._last_call = time.time()
