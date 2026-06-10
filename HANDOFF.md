# Session Handoff
_Last updated: 2026-06-10_

## 이번 세션에서 완료한 것

- **미체결 조회 데드락 버그 수정** — `inquire-psbl-rvsecncl`이 모의투자 미지원 → 028260이 영구 pending으로 BUY 영구 차단됐던 문제. vps + "90000000" 에러 시 `set()` 반환으로 수정
- **텔레그램 알림 수신 해결** — DOT_ENV 시크릿에서 토큰이 3글자로 파싱되는 문제. TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID를 별도 GitHub Secret으로 분리해 `env:`로 직접 주입
- **텔레그램 알림 개선** — 종목명 추가(8종목 _KR_NAMES), BUY/SELL → 매수/매도, [KR] 제거
- **포트폴리오 현황 알림** — 주문 발생 사이클 끝에 자동 전송 (`notify_portfolio`)

## 진행 중이거나 미완료

### 🔲 cron 자동 트리거 미설정
- 현재 workflow_dispatch(수동)만 있음
- 09:00 KST 자동 실행 원하면 cron 추가 필요
- GitHub Actions job 최대 6시간 제한 → 09:00 트리거 시 15:00에 잘릴 수 있음

## 핵심 결정 사항

- **TELEGRAM 시크릿 분리** — DOT_ENV 파싱 불안정, 민감한 토큰은 별도 시크릿으로 관리
- **모의투자 미체결 조회** — vps에서 `inquire-psbl-rvsecncl` 미지원 확정. "90000000" 에러 시 pending 전체 해제로 처리
- **포트폴리오 알림 시점** — 매 사이클이 아닌 주문이 나간 사이클에만 전송

## 알아두어야 할 맥락

- GitHub Secret: `DOT_ENV`(설정값), `KIS_CONFIG_YAML`(KIS 인증), `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (별도)
- GitHub Actions job 최대 6시간 → `timeout-minutes: 420` 설정되어 있지만 실제론 360분 상한
- 텔레그램 테스트용 워크플로우: `telegram-test.yml` (workflow_dispatch)

## 다음 작업 제안

1. **[선택] cron 자동 트리거** — 매 거래일 09:00 KST 자동 실행 설정
2. **[선택] 포트폴리오 알림에 당일 실현손익** — `daily_pnl` 추가
3. **[선택] EGW00201 스로틀링 개선** — 8종목 순차 조회 간 딜레이 늘리기

## 관련 파일

- [src/execution/order.py](src/execution/order.py) — 미체결 조회 버그 수정 (vps 예외 처리)
- [src/notify/telegram.py](src/notify/telegram.py) — 종목명, 한글화, notify_portfolio
- [src/scheduler/runner.py](src/scheduler/runner.py) — notify_portfolio 호출
- [.github/workflows/trade.yml](.github/workflows/trade.yml) — TELEGRAM 시크릿 env 추가
- [.github/workflows/telegram-test.yml](.github/workflows/telegram-test.yml) — 텔레그램 테스트
- [scripts/test_telegram.py](scripts/test_telegram.py) — 텔레그램 테스트 스크립트
