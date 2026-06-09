# 백엔드 자동 갱신 설정 (GitHub Actions)

매일 자동으로 추천 엔진을 돌려 `recommendations.json`을 갱신하고,
앱은 그 결과를 받아오는 구조입니다. **앱 실행 시 엔진을 돌리지 않으므로
실행이 1초 이내로 빠르고, API 일일 한도도 하루 1~2회만 소모됩니다.**

```
GitHub Actions (매일 cron)
  → 엔진 실행 (키는 Secrets에서 주입)
  → recommendations.json 커밋
        ↓
앱 → raw.githubusercontent.com 에서 JSON 다운로드 (실패 시 캐시/번들 폴백)
```

---

## 1단계 — GitHub 저장소 만들기

```bash
cd C:\Users\LEE\OldbutRich
git init
git add .
git commit -m "init: 추천 엔진 + 안드로이드 앱"
```

GitHub에서 새 저장소(`OldnRich`) 생성 후:

```bash
git remote add origin https://github.com/Punchlionking/OldnRich.git
git branch -M main
git push -u origin main
```

> ✅ `.env` 는 `.gitignore` 에 등록돼 있어 **키가 커밋되지 않습니다.** 확인하세요.

---

## 2단계 — API 키를 GitHub Secrets에 등록

저장소 → **Settings → Secrets and variables → Actions → New repository secret**

아래 6개를 각각 등록 (이름 정확히 일치):

| Secret 이름 | 값 |
|---|---|
| `KIS_APP_KEY` | 한투 APP KEY |
| `KIS_APP_SECRET` | 한투 APP SECRET |
| `DART_API_KEY` | OpenDART 키 |
| `ALPHA_VANTAGE_KEY` | Alpha Vantage 키 |
| `TWELVE_DATA_KEY` | Twelve Data 키 |
| `FINNHUB_KEY` | Finnhub 키 |

> 로컬 `files/.env` 에 있는 값들을 그대로 복사하면 됩니다.

---

## 3단계 — 워크플로우 동작 확인

저장소 → **Actions 탭 → "추천 종목 갱신" → Run workflow** (수동 실행)

- 약 8분 후 완료되면 `recommendations.json` 이 자동 커밋됩니다.
- 이후로는 매일 자동 실행 (KST 16:10 국장 마감 후 / KST 06:10 미장 마감 후).
- 실행 주기는 `.github/workflows/update-recommendations.yml` 의 `cron` 으로 조정.

---

## 4단계 — 앱에 본인 저장소 주소 연결

`android/app/src/main/java/com/oldbutrich/stockpick/data/RemoteConfig.kt` 수정:

```kotlin
private const val USER   = "본인_GitHub_아이디"   // ← 변경
private const val REPO   = "OldnRich"
private const val BRANCH = "main"
```

저장 후 앱을 빌드하면:
- 실행 시 최신 JSON을 네트워크로 받아옴 → 헤더에 **🟢 실시간** 배지
- 오프라인이면 마지막 캐시 → **🟡 캐시**
- 최초 실행·캐시 없음 → 번들 기본본 → **⚪ 기본**

---

## 참고 — API 무료 한도 주의

| API | 무료 한도 | 비고 |
|---|---|---|
| Alpha Vantage | **25콜/일** | 1회 실행에 24콜 → 하루 1회가 안전 |
| Twelve Data | 800콜/일, 8콜/분 | US 수집이 ~8분 걸리는 원인 |
| KIS | 초당 제한 | 모의투자 서버 사용 중 (`KIS_VIRTUAL=1`) |

→ cron을 하루 1~2회로 유지하세요. 더 자주 돌리면 Alpha Vantage 한도 초과로
저평가/실적 점수가 빠진 채 생성됩니다.
