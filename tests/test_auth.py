"""KISAuth 토큰 발급 재시도 테스트 — 네트워크 타임아웃에 봇이 죽지 않아야 한다."""
import httpx
import pytest

from src.kis.auth import KISAuth


class _FakeResp:
    def __init__(self, data: dict) -> None:
        self._data = data

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._data


def test_post_token_retries_then_succeeds(monkeypatch):
    auth = KISAuth(env="vps")
    calls = {"n": 0}

    def fake_post(url, json=None, timeout=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectTimeout("timed out")
        return _FakeResp({"access_token": "tok"})

    monkeypatch.setattr("src.kis.auth.httpx.post", fake_post)
    monkeypatch.setattr("src.kis.auth.time.sleep", lambda *_: None)

    data = auth._post_token("http://x/oauth2/tokenP", {})
    assert data["access_token"] == "tok"
    assert calls["n"] == 3   # 2회 실패 후 3번째 성공


def test_post_token_raises_after_max_retries(monkeypatch):
    auth = KISAuth(env="vps")

    def always_timeout(url, json=None, timeout=None):
        raise httpx.ConnectTimeout("timed out")

    monkeypatch.setattr("src.kis.auth.httpx.post", always_timeout)
    monkeypatch.setattr("src.kis.auth.time.sleep", lambda *_: None)

    with pytest.raises(httpx.ConnectTimeout):
        auth._post_token("http://x/oauth2/tokenP", {})
