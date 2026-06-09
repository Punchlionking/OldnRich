package com.oldbutrich.stockpick.data

/**
 * 추천 JSON을 받아올 원격 주소 설정.
 *
 * GitHub Actions가 매일 생성해 저장소에 커밋한 recommendations.json을
 * raw.githubusercontent.com 경유로 받아옵니다.
 *
 * ⚠️ 아래 USER / REPO / BRANCH 를 본인 GitHub 정보로 바꾸세요.
 *   예) https://raw.githubusercontent.com/hong-gildong/OldbutRich/main/recommendations.json
 */
object RemoteConfig {
    private const val USER   = "Punchlionking"   // ← 본인 GitHub 아이디
    private const val REPO   = "OldnRich"         // ← 저장소 이름
    private const val BRANCH = "main"             // ← 브랜치명

    val recommendationsUrl: String
        get() = "https://raw.githubusercontent.com/$USER/$REPO/$BRANCH/recommendations.json"

    /** 아직 본인 정보로 안 바꿨으면 네트워크를 건너뛰고 번들 JSON만 사용. */
    val isConfigured: Boolean
        get() = USER != "YOUR_GITHUB_USERNAME"

    /** 네트워크 타임아웃 (밀리초) */
    const val CONNECT_TIMEOUT_MS = 7000
    const val READ_TIMEOUT_MS = 10000
}
