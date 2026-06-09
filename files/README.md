# 오늘의 주식 추천 엔진 (백엔드 스캐너)

국장(KR)·미장(US) 각 5종목을 8개 기준으로 점수화해 선정하고,
타겟 시점 태그와 추천 이유까지 붙여 **안드로이드 앱이 그대로 받아쓸 JSON**으로 내보냅니다.

## 실행

```bash
python -m stock_recommender.main
# → recommendations.json 생성 + 콘솔 요약
```

API 키가 없으면 자동으로 **Mock 데이터**로 동작하므로 바로 돌려볼 수 있습니다.
실제 데이터로 돌리려면 아래 환경변수를 설정하세요 (있는 것만 채워도 됨):

```bash
export KIS_APP_KEY=...        # 한국투자증권 (국장 시세)
export KIS_APP_SECRET=...
export DART_API_KEY=...       # 공시/재무 (국장)
export ALPHA_VANTAGE_KEY=...  # 미장 펀더멘털/지표
export TWELVE_DATA_KEY=...    # 미장 기술지표
export FINNHUB_KEY=...        # 미장 목표가/뉴스
```

## 구조

| 파일 | 역할 |
|------|------|
| `models.py` | 데이터 모델 (입력 종목 + 출력 추천) |
| `config.py` | 기준별 가중치·시점, 임계값, API 키 |
| `criteria.py` | **8개 기준 점수화 로직 (엔진의 핵심)** |
| `engine.py` | 종합점수 산출 → 다양성 고려 선정 → 시점 태그 |
| `indicators.py` | RSI/MACD/볼린저 계산 (KIS 일봉용, 표준 라이브러리만) |
| `datasources.py` | **KIS·DART / Alpha Vantage·Twelve Data·Finnhub 실연동 + Mock** |
| `main.py` | 진입점, JSON 출력 |

## 데이터 연동 현황

`datasources.py`에 실제 API 호출이 구현되어 있습니다. 키가 있으면 실데이터,
없으면 자동으로 Mock으로 폴백합니다.

| 데이터 | 국장(KR) | 미장(US) |
|--------|----------|----------|
| 시세·거래량 | KIS inquire-price | Twelve Data /quote |
| RSI·MACD·볼린저 | 일봉 → `indicators.py`로 직접 계산 | Twelve Data /rsi·/macd·/bbands |
| PER·PBR·업종평균 | KIS + 유니버스 집계 | Alpha Vantage OVERVIEW + 집계 |
| ROE·영업이익률·실적 | KIS finance API | Alpha Vantage INCOME_STATEMENT |
| 목표가 | ⚠ 미연동(네이버/FnGuide 필요) | Alpha Vantage AnalystTargetPrice |
| 뉴스·감성 | ⚠ 미연동(네이버뉴스+감성분석) | Finnhub /company-news (건수만) |
| 테마·수혜·블로그 | ⚠ 미연동(매핑테이블/집계 필요) | 동일 |

⚠ 표시는 중립값으로 채워져 해당 기준 점수가 낮게 나옵니다. 즉 **지금은
저평가·퀀트·실적·목표가(미장) 기준이 실데이터로 작동**하고, 나머지 소스를
추가할수록 정밀해지는 구조입니다.

## 평가 기준 (v2 — 16개 팩터)

`tier`: 데이터 가용 단계 — **live**=현재 작동 / **data**=재무제표 연동 시 / **source**=신규 소스 필요

| 기준 | 신호 | 타겟 | tier |
|------|------|------|------|
| 중기 모멘텀(12-1) | 1개월 제외 12개월 수익률 (학술 검증 모멘텀) | 중기 | **live** |
| 퀀트·차트 신호 | RSI 반등 + MACD 골든크로스 + 볼린저 | 단기 | **live** |
| 테마 급부상 | 테마군 거래량 급증 + 섹터 강도 | 단기 | live(US/KR 매핑 필요) |
| 간접 수혜주(리드-래그) | 대장주 급등 갭 + 시차상관(그레인저 프록시) | 중기 | live |
| 추정치 상향·서프라이즈 | EPS 추정 상향 + 실적 상회 후 표류(PEAD) | 중기 | source |
| 목표가 갭 | 컨센서스 목표가 대비 상승여력 | 중기 | data |
| 호재 모멘텀 | 비정상 거래량 + 모멘텀 + 감성 (⚠️고위험) | 단기 | data |
| 내부자 군집매수 | 임원·주요주주 90일 순매수 | 중기 | source |
| 퀄리티(F-Score) | Piotroski 9항목 (수익성·건전성·효율) | 장기 | data |
| FCF 수익률 | 잉여현금흐름/기업가치 (조작 강건 밸류) | 장기 | data |
| 자본효율(ROIC) | ROIC−WACC 스프레드 (레버리지 무관 효율) | 장기 | data |
| 발생액 품질 | (순이익−CFO)/자산, Sloan 이상현상 필터 | 장기 | data |
| 저평가 우량주 | 업종 대비 PER/PBR 할인 + 수익성 | 장기 | live |
| 꾸준한 실적 성장 | 연속 증가 분기 + YoY | 장기 | live |
| 지배구조·주주환원 | 총주주환원율·자사주소각·밸류업 (코리아 디스카운트) | 중기 | source |
| 신뢰 소스 언급 | 화이트리스트 소스 언급 빈도 | 중기 | data |

### 결합 파이프라인 (engine.py)

개별 팩터를 단순 가중합하지 않고 **퀀트 표준 파이프라인**으로 결합:

1. **배제 필터** — Altman Z-Score < 1.8(부도위험)·적신호(감사의견 등) 종목을 *먼저* 제외
2. **횡단면 정규화** — 각 팩터를 *시장 내 백분위 순위(0~100)*로 변환 → 단위·스케일 차이 공정 결합, 이상치 강건
3. **가중 결합** — 정규화 점수의 가중합 = 종합점수
4. **리스크 조정** — 저변동성 이상현상 반영(λ=0.15, 저변동성에 가점)
5. **다양성 선정** — 같은 대표기준 편중 방지하며 시장별 TOP 5

설정은 `config.py`의 `Combination`·`Exclusion`·`CRITERIA`(weight/tier)에서 조정.

## 출력 JSON 스키마 (앱 연동 계약)

```json
{
  "generated_at": "ISO8601",
  "version": 1,
  "markets": {
    "KR": [ Recommendation, ... 최대 5개 ],
    "US": [ Recommendation, ... 최대 5개 ]
  }
}
```

`Recommendation`:
```json
{
  "ticker": "373220",
  "name": "LG에너지솔루션",
  "market": "KR",
  "currency": "KRW",
  "current_price": 83118,
  "overall_score": 62.5,
  "target_horizon": "중기",          // 장기 | 중기 | 단기  → 리스트 태그
  "primary_criterion": "target_gap",
  "primary_label": "목표가 갭",       // 카드 헤드라인
  "risk_level": "보통",              // 보통 | 높음  → 고위험 경고 배지
  "reasons": [                       // 상세화면용. [0]은 항상 대표기준
    { "key", "label", "score", "horizon", "reason", "risk" }, ...
  ]
}
```

앱은 리스트 화면에서 `name`/`current_price`/`overall_score`/`target_horizon`,
상세 화면에서 `reasons[].reason`을 그대로 표시하면 됩니다.

## 실제 API 연동

`datasources.py`의 `KoreaDataSource` / `USDataSource`에 TODO로 표시된
메서드를 채우면 됩니다. 어떤 API의 어떤 엔드포인트로 `models.py`의
각 필드를 채워야 하는지 파일 상단 주석에 매핑해두었습니다.

## 주의

- 추천 결과는 **정보 제공 목적**이며 수익을 보장하지 않습니다. 앱에 면책 고지 필수.
- '호재 모멘텀' 기준은 검증되지 않은 신호로, 가중치를 낮추고 고위험 배지를 강제합니다.
- 불특정 다수 대상 종목 추천 서비스는 국내에서 유사투자자문업/투자자문업
  신고·등록 대상일 수 있으니 배포 전 확인하세요.
- 가중치·임계값은 출발점입니다. 과거 데이터로 백테스트해 튜닝하세요.
