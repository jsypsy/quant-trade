# Session Handoff
_Last updated: 2026-06-10_

## 이번 세션에서 완료한 것

- **시스템 전체 검수 (FABLE5_REVIEW.md 기반)**: 치명적 결함 5개 식별 — daily_pnl 미갱신(킬스위치 불능), 손절 부재, 잔고 실패 시 비대칭 동작, OrderType 코드 반전, 신호 유실(300s 루프 + 2봉 비교 구조)
- **3대 안전장치 구현** (커밋 `abf5be2`, 푸시 완료):
  - `src/risk/position_monitor.py` (신규): 손절 -2% / 익절 +4% / 15:20 EOD 전량 청산 — 시장가, 전략 신호보다 우선
  - `daily_pnl` 실계산: 장 시작 스냅샷 기반, 킬스위치 실제 작동
  - 잔고 조회 실패 시 사이클 전체 스킵 (fallback 1천만원 제거)
- **OrderType 버그 수정**: LIMIT/MARKET 코드 반전 (`"01"`↔`"00"`) — dry_run=False 전환 시 실전 직결 버그
- `config/settings.py`에 `stop_loss_pct=2.0`, `take_profit_pct=4.0` 추가 (.env로 재정의 가능)
- `tests/test_position_monitor.py` 신규 (9케이스), 전체 pytest 22개 통과

## 진행 중이거나 미완료

- **신호 유실 문제 미수정**: 300s 루프에서 1분봉 마지막 2봉만 비교 → 크로스 80% 유실. 루프를 60s로 낮추고 `ohlcv.iloc[:-1]`(완성봉)만 쓰도록 수정 필요 (체크리스트 4번)
- **미체결 주문 관리 미구현**: `sync_fills()` 부분체결 오인, 취소 TR 없음 (체크리스트 5번)
- **`_pending` 영속화 미구현**: 재시작 시 중복 주문 위험 (체크리스트 6번)
- **유니버스 등락률 상한 밴드 미적용**: 과열 종목 추격 차단 (`max_change_rate` 파라미터 추가 필요)
- **`acml_tr_pbmn`/`vol_inrt` 단위 확인 및 필터 활성화** (체크리스트 7번)
- **백테스트 없음**: 분봉 데이터 적재 → 전략 수익성 검증 (체크리스트 8번)

## 핵심 결정 사항

- 강제 청산(손절/익절/EOD)은 별도 `PositionMonitor` 모듈로 분리, runner에서 전략 신호보다 먼저 실행
- 청산 주문은 시장가 — 지정가 미체결로 손실 확대 방지
- 잔고 조회 실패 시 "아무것도 하지 않는다" — 매수/매도 모두 차단
- `daily_pnl`은 미실현 손익 포함한 포트폴리오 전체 기준 (개별 체결 추적 불필요)

## 알아두어야 할 맥락

- 현재 `dry_run=True`가 기본 — 모의투자 실주문은 `DRY_RUN=false` 환경변수 필요
- `PositionMonitor` 강제 청산도 `dry_run=True`면 로그만 남기고 KIS에 전송 안 됨
- KRX `ORD_DVSN`: `"00"` = 지정가, `"01"` = 시장가 (이전 코드가 반전되어 있었음, 수정됨)
- 실전 전환 전 체크리스트 잔여 항목(4~8번) 중 최소 4~6번이 완료 조건

## 다음 작업 제안 (우선순위)

1. **루프 60s + 완성봉만 사용** — `runner.py` `_DEFAULT_INTERVAL=60`, `engine.py`에서 `ohlcv.iloc[:-1]` (영향 큰 1일 작업)
2. **유니버스 `max_change_rate` 필터** — `universe.py` `_select()` 한 줄 추가, 과열 추격 차단
3. **`_pending` 영속화** — 재시작 안전, 10줄 작업
4. `sync_fills()` 수량 기반 비교 + 주문 취소 TR 추가
5. 모의투자로 손절/EOD 실제 발동 확인 후 실전 전환 검토

## 관련 파일

- `src/risk/position_monitor.py` — 신규: 강제 청산 로직
- `src/scheduler/runner.py` — daily_pnl 실계산, 사이클 스킵, 강제 청산 연결
- `src/execution/order.py` — OrderType 버그 수정
- `src/execution/order_manager.py` — submit()에 order_type 파라미터 추가
- `config/settings.py` — stop_loss_pct, take_profit_pct 추가
- `tests/test_position_monitor.py` — 신규 테스트
