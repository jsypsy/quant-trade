# Session Handoff
_Last updated: 2026-06-10_

## 이번 세션에서 완료한 것

- **미커밋 코드 전체 커밋·푸시** — RiskGuard, BacktestEngine, AccountQuery, KISAuth 리팩터 등
- **trades/ gitignore 추가**
- **운영시간 수정** — 08:00~20:00(NXT) → 09:00~15:30(KRX 정규장만). KIS 모의투자 NXT 미지원 공식 확인
- **GitHub Actions 자동매매 구축** — IP 차단 없음 확인 후 세 워크플로우 생성:
  - `.github/workflows/trade.yml` — workflow_dispatch → 장마감(15:30)까지 자동 실행
  - `.github/workflows/portfolio.yml` — 수동 포트폴리오 현황 조회
  - `.github/workflows/kis-ip-test.yml` — IP 차단 여부 테스트용
- **미체결 조회 endpoint 수정** — `inquire-nccs`(해외주식용, 404) → `inquire-psbl-rvsecncl`
- **포트폴리오 리포트** — `scripts/portfolio_report.py` 생성. GITHUB_STEP_SUMMARY에 Markdown 테이블 출력
- **Position/Balance 필드 확장** — 현재가·매입금액·평가손익·수익률 추가
- **첫 완결 거래 성공** — KB금융(105560) BUY→SELL +480원

## 진행 중이거나 미완료

### 🔲 텔레그램 알림 미전송
- 원인 미확인. 다음 실행 로그 시작에 `텔레그램 알림: 활성화/비활성화` 메시지가 찍힘
- `비활성화`면 → GitHub Secret `DOT_ENV` 내 `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` 재확인
- `활성화`인데 안 오면 → Telegram API 응답 문제 (봇이 채팅방에 없거나 chat_id 오류)

### 🔲 포트폴리오 5개 종목 보유 중
- 현재 봇이 어떤 종목을 얼마나 보유하는지 확인 필요 (포트폴리오 워크플로우로 확인 가능)

## 핵심 결정 사항

- **GitHub Actions로 자동매매** — 맥 없이도 동작. `trade.yml` workflow_dispatch 트리거
- **KIS 모의투자 NXT 미지원** — `is_market_open()` 09:00~15:30 고정
- **미체결 조회 TR_ID**: `VTTC8036R`(vps) / `TTTC8036R`(prod), path: `inquire-psbl-rvsecncl`
- **GitHub Secrets**: `KIS_CONFIG_YAML`(KIS 설정 YAML), `DOT_ENV`(.env 전체 내용)

## 알아두어야 할 맥락

- KR 8종목 운용 중, 모의투자(vps), 장 중 20초 주기
- 초당 거래건수 초과(EGW00201) 재시도로 처리 중 — 큰 문제 없음
- `uv` 경로: `~/.local/bin/uv`

## 다음 작업 제안

1. **[즉시] 텔레그램 알림 진단** — `trade.yml` 실행 후 시작 로그에서 "텔레그램 알림: ..." 확인
2. **[선택] 포트폴리오 현황 확인** — `portfolio.yml` 실행 → Job Summary 탭에서 테이블 확인
3. **[선택] EGW00201 스로틀링 개선** — 8종목 순차 조회 간 딜레이 늘리기

## 관련 파일

- [.github/workflows/trade.yml](.github/workflows/trade.yml) — 자동매매 워크플로우
- [.github/workflows/portfolio.yml](.github/workflows/portfolio.yml) — 포트폴리오 조회
- [src/utils/time.py](src/utils/time.py) — 운영시간 09:00~15:30
- [src/execution/order.py](src/execution/order.py) — 미체결 조회 endpoint 수정
- [src/portfolio/account.py](src/portfolio/account.py) — Position/Balance 확장
- [scripts/portfolio_report.py](scripts/portfolio_report.py) — Markdown 리포트
- [src/notify/telegram.py](src/notify/telegram.py) — 알림 전송 + 응답 로깅
