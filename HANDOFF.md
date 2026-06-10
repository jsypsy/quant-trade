# Session Handoff
_Last updated: 2026-06-10_

## 이번 세션에서 완료한 것
- **주문 알림 정확성 수정** (`6487485`, main에 머지됨): 포트폴리오 현황을 주문 전 stale 잔고가 아니라 **실제 체결 확인 시점에 최신 잔고로** 전송. `sync_fills()`가 체결된 종목 집합 반환, runner가 체결 시에만 잔고 재조회. 라벨 `주문체결`→`주문접수`로 구분, 체결 시 종목명 표시.
- **동적 유니버스 구현** (`54d76b4`, 피처 브랜치에만 있음): 대형주 8개 하드코딩 제거 → KIS 거래량순위 API로 5분마다 종목 자동 선정.

## 진행 중이거나 미완료
- **동적 유니버스는 아직 main 미머지** — 피처 브랜치(`claude/vigilant-einstein-uj2sxk`)에만 있음. 머지 여부 사용자 답변 대기 중.
- **단위 보정 필요 (실거래 전 필수)**: KIS `acml_tr_pbmn`(거래대금)·`vol_inrt`(거래증가율) 단위 미확인. `min_trade_value`(500억 하한)·`min_rvol` 기본 비활성(0). 모의 응답 1회 찍어 단위 확인 후 켜야 함. → 확인용 스크립트 미작성.
- **손절(stop-loss) 부재**: RiskGuard에 일일 손실 킬스위치만 있고 종목별 손절/익절 없음. 단타 핵심 보호장치라 별도 작업 필요.

## 핵심 결정 사항
- 체결 알림은 **실시간 체결통보 WebSocket(`ws.py` TODO)** 이 정석이나, 모의(vps)는 미체결 조회 미지원이라 폴링으로 충분. 실전 전환 시 WebSocket 구현 예정 — **지금은 보류**.
- 예수금 표시(`telegram.py:95` `cash = portfolio_value - stocks_value`)는 **의도된 설계**(주식평가+예수금=총평가 불변식). `balance.cash` 직접 사용 제안은 철회 — 변경 안 함.
- 유니버스 선정 기준: 전문 자료 연구 결과 **거래대금 상위 풀 → 가격/등락률/RVOL 필터 → 등락률(상승률) 1등 랭킹**. 테마·뉴스·차트타점·체결강도·호가는 자동화 불가로 한계 명시.
- 보유 종목은 유니버스에서 빠져도 **매도 관리 위해 항상 포함**.

## 알아두어야 할 맥락
- 환경 기본 `vps`(모의투자). `settings.is_paper` = `kis_env=="vps"`.
- 매매 루프: `scripts/run_paper.py` → `PaperTrader._cycle()` (기본 20초 간격, 유니버스 5분 갱신).
- runner.py에 **기존부터 있던 lint 경고**(I001 import 정렬, F401 `Strategy` 미사용) — 내 변경과 무관, 수술적 원칙으로 미수정.
- 전략은 분봉 골든크로스(`make_strategy`: short=5, long=18). 동적 종목엔 종목별 튜닝 불가라 공통 윈도우 사용.

## 다음 작업 제안 (우선순위)
1. **거래대금/RVOL 단위 확인 스크립트** → 임계값(`min_trade_value`, `min_rvol`) 활성화
2. **종목별 손절/익절** RiskGuard에 추가 (단타 필수)
3. 동적 유니버스 main 머지 (사용자 승인 후)
4. 시총 하한·역배열 필터, 체결강도/호가 진입검증 (한계 항목 보강)
5. 실전 전환 시 `ws.py` 실시간 체결통보 구현

## 관련 파일
- `src/data/universe.py` — UniverseProvider (신규, 선정 프로세스)
- `src/signal/engine.py` — 팩토리 기반 동적 전략, `set_universe()`
- `src/scheduler/runner.py` — `_refresh_universe()`, 체결 기준 알림
- `src/execution/order_manager.py` — `sync_fills()` 체결 종목 반환
- `src/notify/telegram.py` — 주문접수/체결 라벨, 포트폴리오 알림
- `scripts/run_paper.py` — 동적 유니버스 배선
- `tests/test_universe.py` — 신규 테스트
