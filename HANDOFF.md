# Session Handoff
_Last updated: 2026-06-10_

## 이번 세션에서 완료한 것

- **포트폴리오 알림 정확도 수정** — 주문 체결 후 텔레그램에 표시되는 포트폴리오가 실제 보유와 달랐던 문제 해결
  - 원인: 사이클 시작 시 조회한 낡은 `balance` 객체를 주문 후에도 그대로 사용
  - 수정: `sync_fills()` 후 잔고 재조회 → `notify_portfolio` 전달 ([src/scheduler/runner.py:162-167](src/scheduler/runner.py#L162-L167))

## 진행 중이거나 미완료

### 🔲 cron 자동 트리거 미설정
- 현재 workflow_dispatch(수동)만 있음
- 09:00 KST 자동 실행 원하면 cron 추가 필요
- GitHub Actions job 최대 6시간 → 09:00 정각 트리거 시 15:00에 잘릴 수 있음

## 핵심 결정 사항

- **주문 후 잔고 재조회**: 체결 후 포트폴리오 알림은 반드시 새로 조회한 balance 사용. 재조회 실패 시 기존 balance fallback.

## 알아두어야 할 맥락

- GitHub Secrets: `DOT_ENV`(설정값), `KIS_CONFIG_YAML`(KIS 인증), `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- 모의투자 `inquire-psbl-rvsecncl` 미지원 — vps에서 "90000000" 에러 시 `set()` 반환 처리
- 1회 주문 한도: `MAX_ORDER_AMOUNT=1,000,000원`, 종목 비중: `MAX_POSITION_PCT=0.2`
- 코드 변경 후에는 GitHub Actions job 재시작 필요 (Cancel → workflow_dispatch 재실행)

## 다음 작업 제안

1. **[선택] cron 자동 트리거** — 매 거래일 09:00 KST 자동 실행
2. **[선택] 포트폴리오 알림에 당일 실현손익** — `notify_portfolio`에 `daily_pnl` 추가
3. **[선택] EGW00201 스로틀링 개선** — 8종목 순차 조회 간 딜레이 늘리기

## 관련 파일

- [src/scheduler/runner.py](src/scheduler/runner.py) — 주문 후 잔고 재조회 추가
