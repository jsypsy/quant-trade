# KIS 퀀트 자동매매

한국투자증권(KIS) Open API를 이용한 퀀트 자동매매 시스템.  
전략 신호 생성 → 백테스트 검증 → 모의투자 자동 주문 실행까지 연결.

## 빠른 시작

```bash
# 1. 계정 설정 파일 생성
cp config/kis_devlp.yaml.example ~/KIS/config/kis_devlp.yaml
# ~/KIS/config/kis_devlp.yaml 에 실제 키 입력

# 2. 환경변수 설정
cp .env.example .env

# 3. 의존성 설치
uv sync

# 4. 연결 확인 (모의투자 토큰 + 삼성전자 현재가)
python scripts/check_auth.py
```

## 환경

| `KIS_ENV` | 대상 |
|-----------|------|
| `vps` (기본) | 모의투자 |
| `prod` | 실전 — 충분한 검증 후 전환 |

## 주의

자동매매는 실제 금전 손실 위험이 있습니다.  
모의투자(`vps`)에서 충분히 검증되지 않은 코드를 실전에 투입하지 마세요.
