# Session Handoff
_Last updated: 2026-06-08_

## 이번 세션에서 완료한 것

- T1: 전체 폴더 구조 + 모든 모듈 스텁 생성 (53개 파일)
- T2: uv 의존성 설치 (httpx, pydantic-settings, loguru, pandas, numpy 등)
- T3: `config/settings.py` — pydantic-settings 기반, KIS_ENV로 도메인/계정 분기
- T4: `src/kis/auth.py` — 토큰 발급·파일 캐시(`~/.kis_token_cache.json`)·1분 재발급 제한
- T5: `scripts/check_auth.py` — 모의투자 토큰 + 삼성전자(005930) 현재가 연결 검증 스크립트
- README.md: 멀티 머신 셋업 가이드 (Windows/Mac 공통) 작성
- GitHub 푸시: `https://github.com/jsypsy/quant-trade` master 브랜치

## 진행 중이거나 미완료

- **check_auth.py 실행 검증 미완료** — 사용자가 아직 실행 결과를 보여주지 않음
  - 성공 기준: 토큰 발급 OK + 삼성전자 현재가 숫자 출력
  - 실패 시 확인할 것: `~/KIS/config/kis_devlp.yaml` 값, TR_ID `FHKST01010100` 정확성
- T6~T12 미진행 (사용자 지시에 따라 T5 이후 대기 중)

## 핵심 결정 사항

- 프로젝트 루트: `d:\workspace\quant-trade\` (= `kis-quant-trading/`)
- 패키지 매니저: `uv 0.11.7` (Python 3.14.4 환경)
- KIS_ENV 기본값: `vps` (모의투자) — `.env`에서 관리
- 토큰 캐시: `~/.kis_token_cache.json` — gitignore, 환경(env)별 분리 처리
- TR_ID `FHKST01010100`: 공식 예제 기반이나 코드에 `# TODO` 주석 남김
- HTS ID: `$1963755` (KIS 포털 표시값 그대로 사용 — 실제 사용 시 확인 필요)
- `my_prod` (계좌 뒤 2자리): `01` 기본값 — 실제 계좌와 다를 수 있음

## 알아두어야 할 맥락

- 비밀 파일 위치:
  - `C:\Users\jeong\KIS\config\kis_devlp.yaml` (윈도우, 저장소 외부)
  - `d:\workspace\quant-trade\.env` (gitignore)
- 다른 머신에서 클론 시 두 파일을 수동으로 재생성해야 함 (README에 상세 가이드 있음)
- `settings.py`의 `_load_yaml()`은 매 속성 접근마다 파일을 읽음 — T6에서 캐시로 개선 가능

## 다음 작업 제안

1. **`python scripts/check_auth.py` 실행 결과 확인** (T5 최종 검증)
2. T6: `src/kis/client.py` — REST 공통 호출 (헤더/유량제어/재시도) + `data/market.py` 시세 조회
3. T7: 전략 베이스 + 골든크로스 예시 + 시그널 엔진
4. T8: `src/risk/guard.py` 안전장치 + 테스트

## 관련 파일

- [config/settings.py](config/settings.py) — KIS_ENV 분기, 계정 로더
- [src/kis/auth.py](src/kis/auth.py) — 토큰 관리 핵심
- [scripts/check_auth.py](scripts/check_auth.py) — 연결 검증
- [README.md](README.md) — 멀티 머신 셋업 가이드
- [CLAUDE.md](CLAUDE.md) — 코딩 행동 지침
- [PROJECT_SETUP.md](PROJECT_SETUP.md) — 프로젝트 전체 사양
