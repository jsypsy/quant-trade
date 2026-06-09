# Session Handoff
_Last updated: 2026-06-10_

## 이번 세션에서 완료한 것

- **미국 주식(US) 코드 완전 제거** — 13개 파일에서 US 관련 코드 전부 삭제
  - `src/utils/time.py` — `is_us_market_open`, `is_us_premarket_open` 및 US 시간 상수 제거
  - `src/data/market.py` — `yfinance` import, US 버퍼/메서드 전부 제거, `us_client` 파라미터 제거
  - `src/execution/order.py` — `_US_TR_ID`, `_EXCD_ORDER`, `_us_body()`, `market_type`/`excd` 필드 제거
  - `src/execution/order_manager.py` — `submit()`에서 `market`, `excd` 파라미터 제거 (KR 하드코딩)
  - `src/scheduler/runner.py` — `guard_us`, `_ALLOC_US`, US 분기 전부 제거, KR 전용으로 재작성
  - `src/strategy/golden_cross.py` — `market_type`, `excd` 파라미터 제거
  - `src/signal/engine.py` — US 분기 제거
  - `config/settings.py` — `max_us_order_usd`, `max_us_position_pct` 제거
  - `scripts/run_paper.py`, `run_backtest.py`, `compute_universe_metrics.py` — US 코드 전부 제거
- **구 프로세스(PID 67334) 종료** — 구 코드로 돌던 봇 kill

## 진행 중이거나 미완료

### 🔲 봇 재시작 필요
- `~/.local/bin/uv run python scripts/run_paper.py`로 신규 코드 기동 필요
- 08:00 KST NXT 개장 이후 `[KR] 사이클 #1 시작` 로그 확인

### 🔲 KR 첫 주문 미확인
- 아직 신규 코드로 장 중 사이클 미실행
- `[ORDER][KR] BUY XXXXXX` + `[OM] XXXXXX 체결 확인 — pending 제거` 메시지 확인 필요

## 핵심 결정 사항

- **US 완전 제거** — 코드베이스에서 흔적 없이 삭제. 재추가 시 git log에서 복구 가능
- **배분 비율**: `allocated = total_value` (KR 100%, US 50% 분리 개념 없음)
- **`OrderManager.submit()`**: `market`, `excd` 파라미터 제거, "KR" 하드코딩

## 알아두어야 할 맥락

- KR 8종목 운용 중, 모의투자(vps), 장 중 20초 주기
- NXT 포함 운영시간: 08:00~20:00 KST
- KIS 미체결 TR_ID: `VTTC8036R`(vps) / `TTTC8036R`(prod)
- `yfinance` 의존성은 `compute_universe_metrics.py`에서 KR 종목(.KS/.KQ) 조회에 여전히 사용

## 다음 작업 제안

1. **[즉시] 봇 재시작** — `~/.local/bin/uv run python scripts/run_paper.py &`
2. **[장 중] 주문 로그 확인** — `tail -f logs/paper_run.log`
3. **[선택] 유니버스 교체** — `compute_universe_metrics.py` 재실행 후 신규 종목 선정

## 관련 파일

- [src/scheduler/runner.py](src/scheduler/runner.py) — 메인 루프 (KR 전용)
- [src/execution/order.py](src/execution/order.py) — KR 주문 + `get_unfilled_tickers()`
- [src/execution/order_manager.py](src/execution/order_manager.py) — `sync_fills()` KIS 연동
- [scripts/run_paper.py](scripts/run_paper.py) — 진입점, KR 8종목 유니버스
