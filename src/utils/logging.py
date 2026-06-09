"""loguru 구조적 로깅 설정.

setup_logging() 을 앱 진입점에서 한 번 호출하면:
  - 콘솔: INFO 이상
  - logs/app.log: DEBUG 이상, 일 단위 로테이션, 30일 보관
"""
import sys
from pathlib import Path

from loguru import logger


def setup_logging(log_dir: str = "logs", level: str = "DEBUG") -> None:
    logger.remove()

    # 콘솔 — INFO 이상
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}",
        colorize=True,
    )

    # 파일 — DEBUG 이상, 일 로테이션
    Path(log_dir).mkdir(exist_ok=True)
    logger.add(
        f"{log_dir}/app.log",
        level=level,
        rotation="00:00",
        retention="30 days",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{line} | {message}",
    )

    logger.info("로깅 초기화 완료 (log_dir={})", log_dir)
