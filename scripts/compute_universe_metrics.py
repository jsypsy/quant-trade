"""후보 종목 스캘핑 적합도 지표 계산 (yfinance 기반).

출력: JSON {kr: [...]}
- scalping_score = 30일 일별 표준편차 × √(평균거래량)
"""
import json
import sys

import numpy as np
import yfinance as yf

KR_CANDIDATES = [
    # 대형주 (KOSPI)
    ("005930", "삼성전자",        "005930.KS"),
    ("000660", "SK하이닉스",      "000660.KS"),
    ("035420", "NAVER",           "035420.KS"),
    ("035720", "카카오",           "035720.KS"),
    ("005380", "현대차",           "005380.KS"),
    ("000270", "기아",             "000270.KS"),
    ("068270", "셀트리온",         "068270.KS"),
    ("051910", "LG화학",           "051910.KS"),
    ("207940", "삼성바이오로직스", "207940.KS"),
    ("003670", "포스코홀딩스",     "003670.KS"),
    ("105560", "KB금융",           "105560.KS"),
    ("055550", "신한지주",         "055550.KS"),
    ("012330", "현대모비스",       "012330.KS"),
    ("373220", "LG에너지솔루션",   "373220.KS"),
    ("006400", "삼성SDI",         "006400.KS"),
    ("247540", "에코프로비엠",     "247540.KQ"),
    ("028260", "삼성물산",         "028260.KS"),
    ("003550", "LG",              "003550.KS"),
    # KOSDAQ
    ("323410", "카카오뱅크",       "323410.KS"),
    ("259960", "크래프톤",         "259960.KS"),
]


def analyze(yahoo: str, kis: str, name: str) -> dict | None:
    try:
        h = yf.Ticker(yahoo).history(period="30d")
        if len(h) < 6:
            print(f"SKIP {yahoo}: 데이터 부족 ({len(h)}일)", file=sys.stderr)
            return None
        r = h["Close"].pct_change().dropna()
        vol = float(r.std())
        avg_vol = float(h["Volume"].mean())
        mom5 = float(h["Close"].iloc[-1] / h["Close"].iloc[-6] - 1)
        return {
            "ticker": kis,
            "name": name,
            "yahoo": yahoo,
            "volatility_30d": round(vol, 6),
            "avg_volume_30d": round(avg_vol),
            "scalping_score": round(vol * np.sqrt(avg_vol), 4),
            "momentum_5d": round(mom5, 6),
        }
    except Exception as e:
        print(f"SKIP {yahoo}: {e}", file=sys.stderr)
        return None


kr_results = []
for kis, name, yahoo in KR_CANDIDATES:
    r = analyze(yahoo, kis, name)
    if r:
        kr_results.append(r)

kr_results.sort(key=lambda x: x["scalping_score"], reverse=True)

print(json.dumps({"kr": kr_results}, ensure_ascii=False))
