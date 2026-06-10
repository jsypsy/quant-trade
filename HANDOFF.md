# Session Handoff
_Last updated: 2026-06-10_

## 이번 세션에서 완료한 것

- **미체결 조회 데드락 버그 수정** — `inquire-psbl-rvsecncl` 모의투자 미지원으로 028260 영구 BUY 차단. vps + "90000000" 에러 시 `set()` 반환으로 수정
- **텔레그램 알림 정상화** — DOT_ENV 시크릿 파싱 불안정 → `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` 별도 GitHub Secret 분리
- **텔레그램 알림 개선** — 종목명 추가(`_KR_NAMES`), 매수/매도 한글화, [KR] 제거, 포트폴리오 현황(`notify_portfolio`) 주문 발생 사이클 끝에 전송
- **BUY/SELL 수량 버그 수정** — 전략 qty=1 플레이스홀더가 그대로 주문되던 문제
  - BUY: RiskGuard가 금액·비중 한도로 직접 산출 (예: 삼성전자 12주, KB금융 18주)
  - SELL: runner에서 실제 보유 수량으로 교체

## 진행 중이거나 미완료

### 🔲 cron 자동 트리거 미설정
- 현재 workflow_dispatch(수동)만 있음
- 09:00 KST 자동 실행 원하면 cron 추가 필요
- GitHub Actions job 최대 6시간 → 09:00 정각 트리거 시 15:00에 잘릴 수 있음

## 핵심 결정 사항

- **TELEGRAM 시크릿 분리** — 민감한 토큰은 DOT_ENV 번들 말고 별도 시크릿으로 관리
- **BUY 수량**: RiskGuard가 `min(max_order_amount/price, portfolio*pct/price)` 로 결정 (전략 qty 무시)
- **SELL 수량**: runner가 `balance.positions`에서 실제 보유량 주입

## 알아두어야 할 맥락

- GitHub Secrets: `DOT_ENV`(설정값), `KIS_CONFIG_YAML`(KIS 인증), `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- 모의투자 `inquire-psbl-rvsecncl` 미지원 확정 — vps에서 항상 "90000000" 에러
- 텔레그램 테스트: `telegram-test.yml` workflow_dispatch 실행
- 1회 주문 한도: `MAX_ORDER_AMOUNT=1,000,000원`, 종목 비중: `MAX_POSITION_PCT=0.2`

## 다음 작업 제안

1. **[선택] cron 자동 트리거** — 매 거래일 09:00 KST 자동 실행
2. **[선택] 포트폴리오 알림에 당일 실현손익** — `daily_pnl` 추가
3. **[선택] EGW00201 스로틀링 개선** — 8종목 순차 조회 간 딜레이 늘리기

## 관련 파일

- [src/execution/order.py](src/execution/order.py) — 미체결 조회 vps 예외 처리
- [src/risk/guard.py](src/risk/guard.py) — BUY 수량 한도 기준 직접 산출
- [src/scheduler/runner.py](src/scheduler/runner.py) — SELL 실제 보유량 주입, notify_portfolio 호출
- [src/notify/telegram.py](src/notify/telegram.py) — 종목명, 한글화, notify_portfolio
- [.github/workflows/trade.yml](.github/workflows/trade.yml) — TELEGRAM 시크릿 env 추가
- [.github/workflows/telegram-test.yml](.github/workflows/telegram-test.yml) — 텔레그램 테스트
