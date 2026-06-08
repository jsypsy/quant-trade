import json
import time
import zoneinfo
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from loguru import logger

from config.settings import settings

_CACHE_FILE = Path.home() / ".kis_token_cache.json"
_MIN_REISSUE_INTERVAL = 60.0  # KIS: 1분 1회 재발급 제한
_EXPIRY_BUFFER = 600           # 만료 10분 전 갱신
_KST = zoneinfo.ZoneInfo("Asia/Seoul")


class KISAuth:
    def __init__(self) -> None:
        self._last_issue_time: float = 0.0

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def get_access_token(self) -> str:
        cached = self._load_cache()
        if cached and self._is_valid(cached):
            return cached["access_token"]
        return self._issue_token()

    def get_websocket_key(self) -> str:
        # TODO: 공식 예제(oauth2/Approval) body 파라미터명 확인 필요
        url = f"{settings.base_url}/oauth2/Approval"
        body = {
            "grant_type": "client_credentials",
            "appkey": settings.app_key,
            "secretkey": settings.app_secret,
        }
        resp = httpx.post(url, json=body, timeout=10)
        resp.raise_for_status()
        return resp.json()["approval_key"]

    # ------------------------------------------------------------------
    # Private — cache
    # ------------------------------------------------------------------

    def _load_cache(self) -> Optional[dict]:
        if not _CACHE_FILE.exists():
            return None
        try:
            return json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def _is_valid(self, cached: dict) -> bool:
        if cached.get("env") != settings.kis_env:
            return False
        return time.time() < cached.get("expires_at", 0) - _EXPIRY_BUFFER

    def _save_cache(self, token: str, expires_at: float) -> None:
        data = {"access_token": token, "expires_at": expires_at, "env": settings.kis_env}
        _CACHE_FILE.write_text(json.dumps(data), encoding="utf-8")

    # ------------------------------------------------------------------
    # Private — issue
    # ------------------------------------------------------------------

    def _issue_token(self) -> str:
        self._wait_rate_limit()

        url = f"{settings.base_url}/oauth2/tokenP"
        body = {
            "grant_type": "client_credentials",
            "appkey": settings.app_key,
            "appsecret": settings.app_secret,
        }

        resp = httpx.post(url, json=body, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        self._last_issue_time = time.time()

        expires_at = self._parse_expires(data.get("access_token_token_expired", ""))
        self._save_cache(data["access_token"], expires_at)

        logger.info("KIS 액세스 토큰 발급 완료 (env={})", settings.kis_env)
        return data["access_token"]

    def _wait_rate_limit(self) -> None:
        elapsed = time.time() - self._last_issue_time
        if elapsed < _MIN_REISSUE_INTERVAL:
            wait = _MIN_REISSUE_INTERVAL - elapsed
            logger.warning("토큰 재발급 대기: {:.1f}초 (1분 1회 제한)", wait)
            time.sleep(wait)

    def _parse_expires(self, expires_str: str) -> float:
        try:
            dt = datetime.strptime(expires_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=_KST)
            return dt.timestamp()
        except Exception:
            # 파싱 실패 시 fallback: 현재 + 23시간
            return time.time() + 23 * 3600
