# KIS 퀀트 자동매매

한국투자증권(KIS) Open API를 이용한 퀀트 자동매매 시스템.  
전략 신호 생성 → 백테스트 검증 → 모의투자 자동 주문 실행까지 연결.

---

## 매매 전략 (현재 설정)

분봉 기반 **모멘텀 추종 단타** 전략. 두 단계로 동작합니다.

### 1단계 — 종목 선정 (5분마다 갱신)

거래대금 상위 풀에서 "오늘 자금이 몰리며 오르는 종목"만 추립니다.

| 단계 | 기준 (현재값) |
|------|---------------|
| 풀 구성 | 거래대금 순위 상위 **30** (KOSPI) |
| 가격 필터 | 현재가 ≥ **1,000원** (동전주 제외) |
| 모멘텀 필터 | 등락률 ≥ **+2%** (상승 종목만) |
| 랭킹 | 등락률 내림차순 → 상위 **10** 선정 |

> 보유 중인 종목은 매도 관리를 위해 항상 포함됩니다.

### 2단계 — 매수/매도 타이밍 (30초마다, 분봉)

선정된 종목에 **이동평균 골든크로스/데드크로스**를 적용합니다.

- **매수(BUY)**: 단기 MA(**3**)가 장기 MA(**10**)를 아래→위 돌파 (골든크로스)
- **매도(SELL)**: 단기 MA(3)가 장기 MA(10)를 위→아래 돌파 (데드크로스)
- **밴드(`cross_band_pct`)**: 크로스 최소 격차. 휩쏘(잦은 교차) 억제용. 현재 **0.01%**

### 리스크·청산 규칙

| 항목 | 현재값 | 설명 |
|------|--------|------|
| 운용자본 | 1,000만 | 매입원금 기준 상한 (수익 재투입 안 함) |
| 1회 주문 한도 | 600만 | `MAX_ORDER_AMOUNT` |
| 손절 | **-2%** | 종목별, 시장가 청산 |
| 익절 | **+4%** | 종목별, 시장가 청산 |
| 장마감 청산(EOD) | KRX 15:10 / NXT 19:50 | 전량 시장가 (오버나이트 갭 차단) |
| 재진입 쿨다운 | 60초 | 매도 후 같은 종목 재매수 금지 |
| 일손실 킬스위치 | 100만 | 초과 시 신규 매수 중단 |

청산 우선순위: **장마감 > 손절 > 익절** (전략 신호보다 우선).

### 거래소

- **KRX**(기본): 정규장 09:00~15:30, 시세 `J`
- **NXT/SOR**: 넥스트레이드 통합거래, 애프터마켓 ~20:00, 시세 `UN`(통합). 실전(prod) 전용. `KR_EXCHANGE=SOR`로 활성화.

### ⚠️ 한계 (반드시 인지)

- **순수 기술적 분석** — 기업 재무·실적·뉴스·공시·세계 시황·테마는 보지 않습니다.
- **백테스트/OOS 검증 미완료** — 실전 성적은 아직 검증되지 않았습니다.
- 애프터마켓엔 거래대금 순위가 정규장 마감값으로 고정되어, 동적 유니버스의 종목 선정이 부정확합니다.
- 실전 투입 전 반드시 모의에서 수익성을 검증하세요.

---

## 환경

| `KIS_ENV` | 대상 |
|-----------|------|
| `vps` (기본값) | 모의투자 |
| `prod` | 실전 — 충분한 검증 후에만 전환 |

---

## 처음 셋업 (로컬 실행용)

> 이 섹션은 **자기 컴퓨터에서 직접 봇을 실행·테스트할 때만** 필요합니다.
> **GitHub Actions(클라우드)로만 돌린다면 건너뛰세요** — 아래 비밀 파일들은
> 워크플로우가 [GitHub Actions 시크릿](#github-actions-시크릿-클라우드-실행)에서
> 런타임에 자동 생성합니다 (로컬 파일 불필요).

> **비밀 파일 두 개는 저장소에 올라가지 않습니다.**  
> 머신마다 아래 순서로 직접 만들어야 합니다.

### 1. KIS 계정 파일 생성 (저장소 밖 — 절대 커밋 금지)

**macOS / Linux**
```bash
mkdir -p ~/KIS/config
cp config/kis_devlp.yaml.example ~/KIS/config/kis_devlp.yaml
```

**Windows**
```powershell
New-Item -ItemType Directory -Path "$HOME\KIS\config" -Force
Copy-Item config\kis_devlp.yaml.example "$HOME\KIS\config\kis_devlp.yaml"
```

그 다음 `~/KIS/config/kis_devlp.yaml` 을 열어 실제 값을 채워넣습니다:

```yaml
paper_app: "모의 앱키"         # KIS Developers 포털에서 확인
paper_sec: "모의 앱시크릿"
my_htsid:  "HTS_ID"
my_paper_stock: "모의계좌 앞 8자리"
my_prod:   "01"                 # 계좌 뒤 2자리 (종합계좌 = 01)
# 실전 키는 모의 검증 완료 후 입력
my_app:  ""
my_sec:  ""
my_acct_stock: ""
my_agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
```

KIS Developers 포털: https://apiportal.koreainvestment.com/  
→ 앱 관리에서 앱키 / 앱시크릿 확인

### 2. 환경변수 파일 생성

```bash
cp .env.example .env
# 기본값(KIS_ENV=vps)으로 모의투자 사용 가능
```

### 3. 의존성 설치

```bash
uv sync
```

### 4. 연결 확인

```bash
python scripts/check_auth.py
```

성공 시 출력:
```
토큰 발급 OK (앞 20자: ...)
삼성전자(005930) 현재가: XX,XXX원 (전일 대비 X.XX%)
연결 검증 완료 ✓
```

---

## 멀티 머신 개발 (Windows ↔ macOS 등)

코드는 `git pull` 하나로 동기화됩니다.  
**비밀 파일은 머신마다 따로 만들어야 합니다** (저장소에 없음):

| 파일 | 위치 | 내용 |
|------|------|------|
| KIS 계정 설정 | `~/KIS/config/kis_devlp.yaml` | 앱키 / 앱시크릿 / 계좌번호 |
| 환경변수 | 프로젝트 루트 `.env` | `KIS_ENV`, 리스크 한도 등 |

```bash
# 다른 머신에서 이어받을 때
git clone https://github.com/jsypsy/quant-trade.git
cd quant-trade
# → 위 "처음 셋업" 1~4번 반복
```

---

## GitHub Actions 시크릿 (클라우드 실행)

봇은 GitHub Actions(`.github/workflows/`)에서 실행됩니다. 비밀값은 저장소
**Settings → Secrets and variables → Actions** 에 등록하며, 코드·`.env`·커밋에 직접 넣지 않습니다.

| 시크릿 | 용도 | 형식 |
|--------|------|------|
| `DOT_ENV` | 실행 설정 (`.env` 내용) | 아래 예시 |
| `KIS_CONFIG_YAML` | KIS 계정 (앱키·시크릿·계좌) | `kis_devlp.yaml` 전체 내용 |
| `TELEGRAM_CONFIG` | 텔레그램 알림 (토큰 + 챗ID) | 아래 예시 |

### `DOT_ENV` 예시
```
KIS_ENV=vps
DRY_RUN=false
KR_EXCHANGE=KRX
MAX_DAILY_LOSS=1000000
MAX_ORDER_AMOUNT=6000000
```
- `KIS_ENV`: `vps`(모의) / `prod`(실전)
- `KR_EXCHANGE`: `KRX`(정규장) / `SOR`·`NXT`(넥스트레이드 통합·애프터마켓, **prod 전용**)
- `DRY_RUN`: `true`(주문 안 보냄) / `false`(실제 주문)
- `MAX_*`: 리스크 한도 (미지정 시 코드 기본값 사용)

### `TELEGRAM_CONFIG` 예시
```
TELEGRAM_BOT_TOKEN=<BotFather 봇 토큰>
TELEGRAM_CHAT_ID=<챗 ID 숫자>
```
> 토큰·챗ID를 한 시크릿으로 관리. 워크플로우가 `.env`에 병합해 사용합니다.
> 미설정 시 텔레그램 알림만 비활성화되고 매매는 정상 동작합니다.

> ⚠️ 시크릿 값(토큰·앱키·계좌)은 README·코드·커밋·로그에 **절대 노출 금지**.

---

## 주의

- 자동매매는 실제 금전 손실 위험이 있습니다.
- 모의투자(`vps`)에서 충분히 검증되지 않은 코드를 실전(`prod`)에 절대 투입하지 마세요.
- `.env`, `kis_devlp.yaml`, 토큰 캐시(`.kis_token_cache.json`)는 **절대 커밋하지 마세요**.
