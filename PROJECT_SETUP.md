# KIS 퀀트 자동매매 프로젝트 — 초기 셋팅 가이드

> 이 문서는 VS Code의 Claude Code(또는 동급의 코드 에이전트)에게 그대로 넘겨 프로젝트를 초기 구성하기 위한 사양서입니다.
> Claude Code는 이 문서를 읽고 **2번(폴더 구조) → 3번(환경 설정) → 8번(초기 작업 체크리스트)** 순서로 스캐폴딩을 진행합니다.
> 파일을 저장소 루트에 두고 필요하면 `CLAUDE.md`로 이름을 바꿔 Claude Code가 매 세션 자동으로 참고하도록 할 수 있습니다.

---

## 0. 프로젝트 목표 (한 줄 요약)

한국투자증권(KIS) Open API를 이용해 **전략 신호 생성 → 백테스트 검증 → (모의투자) 자동 주문 실행**까지 연결되는 퀀트 자동매매 시스템을 구축한다.
**실전 투입 전 반드시 모의투자(`vps`) 환경에서 충분히 검증**한다.

---

## 1. 핵심 전제 / 의사결정

| 항목 | 결정 | 비고 |
|---|---|---|
| 언어/런타임 | Python 3.11+ | 공식 KIS 저장소 요구사항과 동일 |
| 패키지 매니저 | `uv` | 공식 권장. 빠르고 lock 관리 간편 |
| API 연동 방식 | 공식 저장소 `koreainvestment/open-trading-api` 참조 | 직접 REST 래퍼를 짜기보다 검증된 샘플 구조를 베이스로 |
| 거래 환경 | **모의투자(vps) 우선** → 검증 후 실전(prod) | 절대 처음부터 실전 금지 |
| 데이터 | REST(시세/잔고/주문) + WebSocket(실시간 체결/호가) | |
| 백테스트 | 자체 엔진 또는 `backtrader`/`vectorbt` 중 택1 | 공식 저장소는 QuantConnect Lean 기반 backtester 제공 |
| 알림 | 텔레그램 봇(또는 Slack) | 체결/오류/킬스위치 알림용 |

### 참고할 공식 리소스
- 공식 샘플 저장소: `https://github.com/koreainvestment/open-trading-api`
  - `examples_llm/` : 단일 API 기능별 폴더 (LLM이 탐색하기 좋음) — **함수 시그니처/파라미터의 1차 출처로 사용**
  - `examples_user/` : 상품 카테고리별 통합 함수/실행 예제
  - `kis_auth.py` : 인증·토큰 관리·공통 호출 함수
  - `strategy_builder/`, `backtester/`, `MCP/` : 전략·백테스트·MCP 도구
- API 포털: `https://apiportal.koreainvestment.com/`

> **지침(Claude Code용):** API 함수의 정확한 엔드포인트·TR_ID·파라미터는 추측하지 말고, 위 공식 저장소의 해당 카테고리 폴더 코드를 1차 근거로 삼는다. 불확실하면 코드 주석에 `# TODO: 공식 예제 확인 필요` 표시.

---

## 2. 폴더 구조 (생성 대상)

```
kis-quant-trading/
├── README.md
├── CLAUDE.md                 # (선택) 본 문서를 에이전트 가이드로 사용
├── pyproject.toml            # uv 의존성
├── uv.lock
├── .env.example              # 환경변수 템플릿 (실제 .env는 커밋 금지)
├── .gitignore
│
├── config/
│   ├── settings.py           # pydantic-settings 기반 설정 로더
│   └── kis_devlp.yaml.example# KIS 계정 설정 템플릿 (실제 파일은 ~/KIS/config/로 복사)
│
├── src/
│   ├── kis/
│   │   ├── auth.py           # 접근토큰/웹소켓 접속키 발급·캐싱·재발급
│   │   ├── client.py         # REST 공통 호출(헤더, TR_ID, 유량제어, 재시도)
│   │   ├── ws.py             # WebSocket 실시간 시세/체결 수신
│   │   └── models.py         # 응답 DTO (pydantic)
│   │
│   ├── data/
│   │   ├── market.py         # 시세/차트/기간별 데이터 조회
│   │   ├── universe.py       # 종목 유니버스 구성·필터
│   │   └── store.py          # 캐시/DB 저장 (SQLite or parquet)
│   │
│   ├── strategy/
│   │   ├── base.py           # Strategy 추상 클래스 (generate_signals)
│   │   ├── golden_cross.py   # 예: 이동평균 골든크로스
│   │   └── registry.py       # 전략 등록/조회
│   │
│   ├── signal/
│   │   └── engine.py         # 전략 → BUY/SELL/HOLD 신호 산출
│   │
│   ├── portfolio/
│   │   ├── account.py        # 잔고·보유종목·예수금 조회
│   │   └── position.py       # 포지션 추적
│   │
│   ├── execution/
│   │   ├── order.py          # 주문(매수/매도/정정/취소) 실행
│   │   └── order_manager.py  # 미체결 관리·중복 방지·체결 동기화
│   │
│   ├── risk/
│   │   └── guard.py          # 리스크 가드: 손절/익절, 일일 손실 한도, 종목당 비중, 킬스위치
│   │
│   ├── backtest/
│   │   └── engine.py         # 과거 데이터 백테스트·성과 리포트
│   │
│   ├── scheduler/
│   │   └── runner.py         # 장 시간(09:00~15:30) 스케줄, 메인 루프
│   │
│   ├── notify/
│   │   └── telegram.py       # 체결/오류/킬스위치 알림
│   │
│   └── utils/
│       ├── logging.py        # 구조적 로깅 설정
│       └── time.py           # 영업일/장 운영시간 판단
│
├── scripts/
│   ├── check_auth.py         # 토큰 발급 동작 확인 (가장 먼저 실행)
│   ├── run_paper.py          # 모의투자 자동매매 진입점
│   └── run_backtest.py       # 백테스트 진입점
│
├── tests/
│   ├── test_auth.py
│   ├── test_strategy.py
│   └── test_risk.py
│
└── logs/                     # 런타임 로그 (gitignore)
```

---

## 3. 환경 설정 절차

### 3.1 사전 준비 (사람이 직접 — 코드 에이전트가 대신 못 함)
1. 한국투자증권 계좌 개설 및 ID 연결
2. KIS Open API 서비스 신청 → **앱키(App Key) / 앱시크릿(App Secret)** 발급
3. **모의투자용**과 **실전투자용** 앱키를 각각 발급
4. HTS ID, 계좌번호(앞 8자리 / 뒤 2자리) 확인

### 3.2 uv 설치 (macOS 기준 — 사용자 환경)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv --version
```

### 3.3 프로젝트 초기화 (Claude Code가 수행)
```bash
uv init
uv add httpx requests websockets pandas numpy pydantic pydantic-settings \
       pyyaml python-dotenv apscheduler loguru
uv add --dev pytest pytest-asyncio ruff mypy
```
> 백테스트 라이브러리는 전략 확정 후 별도 추가(`uv add backtrader` 등).

### 3.4 KIS 계정 설정 파일
- 공식 구조를 따라 `~/KIS/config/kis_devlp.yaml`에 계정 정보를 둔다(저장소에 커밋 금지).
- 저장소에는 `config/kis_devlp.yaml.example` 템플릿만 둔다.

```yaml
# ~/KIS/config/kis_devlp.yaml  (예시 — 실제 값은 본인 것 입력)
# 실전투자
my_app: "실전 앱키"
my_sec: "실전 앱시크릿"
# 모의투자
paper_app: "모의 앱키"
paper_sec: "모의 앱시크릿"
# HTS ID
my_htsid: "HTS_ID"
# 계좌번호 앞 8자리
my_acct_stock: "증권계좌 8자리"
my_paper_stock: "모의 증권계좌 8자리"
# 계좌번호 뒤 2자리 (종합계좌 = 01)
my_prod: "01"
my_agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
```

### 3.5 .env.example (저장소에 커밋, 실제 .env는 금지)
```dotenv
# 거래 환경: vps(모의) / prod(실전)
KIS_ENV=vps
KIS_CONFIG_PATH=~/KIS/config/kis_devlp.yaml

# 알림
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# 리스크 한도(원/비율) — 기본은 보수적으로
MAX_DAILY_LOSS=300000        # 일일 최대 손실(원) 도달 시 킬스위치
MAX_ORDER_AMOUNT=1000000     # 1회 주문 최대 금액(원)
MAX_POSITION_PCT=0.2         # 단일 종목 최대 비중
```

---

## 4. 인증 / API 핵심 규칙 (반드시 코드에 반영)

| 규칙 | 내용 | 처리 방식 |
|---|---|---|
| 도메인 분리 | 실전 `openapi.koreainvestment.com:9443`, 모의 `openapivts.koreainvestment.com:29443` | env에 따라 자동 분기 |
| 토큰 발급 | `POST /oauth2/tokenP` (`grant_type=client_credentials`, appkey, appsecret) | `auth.py`에서 처리 |
| 토큰 수명 | 유효 24시간, **재발급은 1분당 1회 제한** | 토큰을 로컬에 캐싱하고 만료 임박 시에만 갱신 |
| 유량 제한 | 초당 호출 수 제한, 초과 시 `EGW00201` | 호출 사이 throttle + 지수 백오프 재시도 |
| TR_ID | 실전/모의에 따라 TR_ID가 다른 API 존재 | env 분기에서 TR_ID 매핑 |
| 모의투자 한계 | 모의는 REST 호출 제한이 더 낮음 | 연속 호출 많은 작업은 실전 계좌 고려(단, 주문 제외) |

> **지침(Claude Code용):** 토큰은 절대 매 호출마다 재발급하지 않는다. 파일/메모리 캐시 + 만료 시간 비교로 재사용하고, 1분 1회 제한을 절대 위반하지 않는다.

---

## 5. 아키텍처 흐름

```
[scheduler] 장 시간 루프
   └─> [data] 시세/유니버스 수집
        └─> [strategy] → [signal] BUY/SELL/HOLD 생성
             └─> [risk.guard] 한도·킬스위치 검증 ── (거부) ──> 주문 차단
                  └─> [execution.order] 주문 전송
                       └─> [order_manager] 체결 동기화
                            └─> [portfolio] 잔고 갱신
                                 └─> [notify] 텔레그램 알림
```

핵심 인터페이스 (`strategy/base.py`):
```python
class Strategy(ABC):
    @abstractmethod
    def generate_signals(self, market_data: pd.DataFrame) -> dict[str, Signal]:
        """종목코드 -> Signal(action=BUY/SELL/HOLD, qty, reason) 매핑 반환"""
```

---

## 6. 리스크 / 안전장치 (필수 구현 — 자동매매에서 가장 중요)

1. **모의투자 우선:** 기본 `KIS_ENV=vps`. `prod` 전환은 명시적 환경변수 변경으로만 가능.
2. **킬스위치:** 일일 누적 손실이 `MAX_DAILY_LOSS` 초과 시 즉시 모든 신규 주문 중단 + 알림.
3. **주문 상한:** 1회 주문 금액(`MAX_ORDER_AMOUNT`), 단일 종목 비중(`MAX_POSITION_PCT`) 한도 강제.
4. **중복 주문 방지:** 동일 종목 미체결 주문이 있으면 신규 진입 차단.
5. **시장가 주의:** 기본은 지정가. 시장가는 명시적 옵션으로만 허용.
6. **Dry-run 모드:** 실제 주문 대신 로그만 남기는 모드를 기본 제공.
7. **비밀정보 보호:** `.env`, `kis_devlp.yaml`, `logs/`, 토큰 캐시 파일은 반드시 `.gitignore`. API 키를 코드/로그에 절대 출력 금지.

---

## 7. 코딩 컨벤션

- 포매터/린터: `ruff` (format + lint), 타입체크 `mypy`.
- 모든 외부 I/O(REST/WS)는 예외를 잡아 구조적 로깅으로 남긴다(`loguru`).
- 금액·수량은 정수/`Decimal` 사용(부동소수점 오차 회피).
- 시크릿은 코드에 하드코딩 금지, 항상 설정 로더 경유.
- 함수 단위로 작게, 테스트 가능한 순수 함수 우선(특히 전략·리스크 로직).

---

## 8. Claude Code 초기 작업 체크리스트 (순서대로)

- [ ] **T1.** 위 2번 폴더 구조 및 빈 모듈 파일 생성, `pyproject.toml`/`.gitignore`/`.env.example`/`README.md` 작성
- [ ] **T2.** `uv` 의존성 설치 (3.3 참조)
- [ ] **T3.** `config/settings.py` — pydantic-settings로 `.env` + `kis_devlp.yaml` 로드, `KIS_ENV`에 따라 도메인/TR_ID 분기
- [ ] **T4.** `src/kis/auth.py` — 토큰 발급·캐싱·재발급(1분 제한 준수), 웹소켓 접속키 발급
- [ ] **T5.** `scripts/check_auth.py` — 모의투자 토큰 발급 + 삼성전자(005930) 현재가 1회 조회로 연결 검증
- [ ] **T6.** `src/kis/client.py` — REST 공통 호출(헤더/유량제어/재시도), `data/market.py` 시세 조회
- [ ] **T7.** `src/strategy/base.py` + 예시 전략 1개(`golden_cross.py`) + `signal/engine.py`
- [ ] **T8.** `src/risk/guard.py` — 6번 안전장치 구현 + `tests/test_risk.py`
- [ ] **T9.** `src/execution/order.py` + `order_manager.py` — **dry-run 기본**, 모의 주문 동작 확인
- [ ] **T10.** `src/scheduler/runner.py` + `scripts/run_paper.py` — 모의투자 엔드투엔드 루프
- [ ] **T11.** `src/notify/telegram.py` 알림 연결
- [ ] **T12.** `src/backtest/engine.py` + `scripts/run_backtest.py` (전략 확정 후)

> **시작점:** T1~T5까지 먼저 완료하고 `python scripts/check_auth.py`가 성공(토큰 발급 + 시세 조회)하는지 확인한 뒤 다음 단계로 진행할 것.

---

## 9. 면책 / 주의

- 자동매매는 **실제 금전 손실 위험**이 있다. 모의투자에서 충분히 검증되지 않은 코드를 실전(`prod`)에 절대 투입하지 않는다.
- KIS 공식 샘플 코드 및 API는 사전 공지 없이 변경될 수 있으므로, 함수 시그니처는 항상 최신 공식 저장소 기준으로 재확인한다.
- 본 시스템 사용으로 인한 손익에 대한 책임은 전적으로 사용자 본인에게 있다.
