# Session Handoff
_Last updated: 2026-06-10_

## 이번 세션에서 완료한 것

- **포트폴리오 알림 포맷 개선**
  - 종목코드 제거, 평단가 추가 (`종목명 N주 @ 가격 수익률`)
  - 총 수익률 = 초기 자본(10M) 대비 실제 계좌 수익률로 수정 (`portfolio_value - initial_balance`)
  - 주식 매입 / 주식 평가 분리 (직접 비교 가능)
  - 보유 종목 없을 때 "보유 종목 없음" 명시
- **portfolio.yml 제거** — KIS 동일 앱키 토큰 충돌(403) 문제로 삭제
- **포트폴리오 알림 통합** — 자동매매 루프 안에서 주문 발생 사이클 끝에 전송
- **초기 자본 설정 추가** — `settings.initial_balance = 10_000_000`

## 진행 중이거나 미완료

### ⚠️ 포트폴리오 알림 정확도
- KIS 모의투자 API가 주문 직후 잔고를 즉시 반영하지 않음
- 현재: 주문 직전 상태의 balance 표시 (pre-order)
- 재조회 시도했으나 빈 데이터 반환 → 원복
- **미해결**: 포트폴리오를 주문 타이밍에 보내는 한 정확도 보장 불가
- 대안으로 N분마다 정기 전송 논의했으나 미구현

### 🔲 단타형 전략 + 동적 종목 선택 (미구현)
- 현재: 8종목 고정 + 골든크로스 전략
- 계획: KOSPI200 상위 30~40종목 풀, 매 사이클 모멘텀+거래량 기준 6~8개 동적 선택
- 1~2분 주기, 스탑로스 -1%, 종목당 15~20% 비중
- 구현 범위 큼 — 다음 세션에서 시작

### 🔲 cron 자동 트리거 미설정
- 현재 수동(workflow_dispatch)만 있음

## 핵심 결정 사항

- **KIS 토큰**: 앱키당 1개, 동시 발급 불가 → 별도 워크플로우에서 잔고 조회 불가
- **포트폴리오 알림**: 주문 발생 사이클 끝에 pre-order balance로 전송 (차선책)
- **총 수익률**: `(portfolio_value - initial_balance) / initial_balance` — 주식 미실현 손익률 아님
- **총 평가**: `tot_evlu_amt` = 주식 + 현금 합산 계좌 전체 가치

## 알아두어야 할 맥락

- GitHub Secrets: `DOT_ENV`, `KIS_CONFIG_YAML`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- 모의투자 잔고 API: 주문 직후 빈 데이터 반환 (레이턴시 문제)
- 코드 변경 후 반드시 Actions job 재시작 필요 (Cancel → workflow_dispatch 재실행)
- `settings.initial_balance = 10_000_000` (.env의 `INITIAL_BALANCE`로 재정의 가능)

## 다음 작업 제안

1. **[주요] 단타형 전략 구현** — 동적 종목 선택 + 모멘텀/거래량 기반 + 스탑로스
2. **[선택] 포트폴리오 정기 전송** — N분마다 전송해 주문 타이밍 의존성 제거
3. **[선택] cron 자동 트리거** — 매 거래일 09:00 KST

## 관련 파일

- [src/notify/telegram.py](src/notify/telegram.py) — 포트폴리오 알림 포맷
- [src/scheduler/runner.py](src/scheduler/runner.py) — 주문 후 notify_portfolio 호출
- [config/settings.py](config/settings.py) — initial_balance 추가
