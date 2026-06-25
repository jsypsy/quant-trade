from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_DOMAINS = {
    "vps":  "https://openapivts.koreainvestment.com:29443",
    "prod": "https://openapi.koreainvestment.com:9443",
}


class KISSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    kis_env: str = Field(default="vps")
    kis_config_path: str = Field(default="~/KIS/config/kis_devlp.yaml")

    initial_balance: int = Field(default=10_000_000)
    trading_capital: int = Field(default=10_000_000)  # 봇 운용 자본 (계좌가 커도 이 한도로만 매매)
    max_daily_loss: int = Field(default=1_000_000)    # 킬스위치 (운용자본 10%)
    max_order_amount: int = Field(default=10_000_000) # 1회 주문 한도 = 운용자본
    max_position_pct: float = Field(default=1.0)       # 단일 종목 100% 허용 (집중)
    stop_loss_pct: float = Field(default=2.0)    # 종목별 손절 한도 (%)
    take_profit_pct: float = Field(default=4.0)  # 종목별 익절 기준 (%)
    cross_band_pct: float = Field(default=0.002)    # 크로스 최소 격차 (0.2%, whipsaw 억제)
    reentry_cooldown_sec: int = Field(default=300)  # 매도 후 재진입 금지 (초)

    dry_run: bool = Field(default=True)

    telegram_bot_token: str = Field(default="")
    telegram_chat_id: str = Field(default="")

    # ------------------------------------------------------------------
    # 파생 속성 — KIS_ENV 기준
    # ------------------------------------------------------------------

    @property
    def is_paper(self) -> bool:
        return self.kis_env == "vps"

    @property
    def base_url(self) -> str:
        if self.kis_env not in _DOMAINS:
            raise ValueError(f"KIS_ENV must be 'vps' or 'prod', got '{self.kis_env}'")
        return _DOMAINS[self.kis_env]

    # ------------------------------------------------------------------
    # YAML 계정 정보 (lazy load, 1회 파싱)
    # ------------------------------------------------------------------

    def _load_yaml(self) -> dict[str, Any]:
        path = Path(self.kis_config_path).expanduser()
        if not path.exists():
            raise FileNotFoundError(
                f"KIS 설정 파일 없음: {path}\n"
                "config/kis_devlp.yaml.example 을 참고해 파일을 생성하세요."
            )
        with path.open(encoding="utf-8") as f:
            return yaml.safe_load(f)

    @property
    def app_key(self) -> str:
        cfg = self._load_yaml()
        key = "paper_app" if self.is_paper else "my_app"
        return cfg[key]

    @property
    def app_secret(self) -> str:
        cfg = self._load_yaml()
        key = "paper_sec" if self.is_paper else "my_sec"
        return cfg[key]

    @property
    def account_no(self) -> str:
        cfg = self._load_yaml()
        key = "my_paper_stock" if self.is_paper else "my_acct_stock"
        return cfg[key]

    @property
    def account_product_code(self) -> str:
        return self._load_yaml().get("my_prod", "01")

    @property
    def hts_id(self) -> str:
        return self._load_yaml().get("my_htsid", "")


settings = KISSettings()
