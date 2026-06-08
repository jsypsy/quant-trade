# KIS 퀀트 자동매매

한국투자증권(KIS) Open API를 이용한 퀀트 자동매매 시스템.  
전략 신호 생성 → 백테스트 검증 → 모의투자 자동 주문 실행까지 연결.

---

## 환경

| `KIS_ENV` | 대상 |
|-----------|------|
| `vps` (기본값) | 모의투자 |
| `prod` | 실전 — 충분한 검증 후에만 전환 |

---

## 처음 셋업 (공통)

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

## 주의

- 자동매매는 실제 금전 손실 위험이 있습니다.
- 모의투자(`vps`)에서 충분히 검증되지 않은 코드를 실전(`prod`)에 절대 투입하지 마세요.
- `.env`, `kis_devlp.yaml`, 토큰 캐시(`.kis_token_cache.json`)는 **절대 커밋하지 마세요**.
