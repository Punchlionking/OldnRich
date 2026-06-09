package com.oldbutrich.stockpick.data

import android.content.Context
import android.util.Log
import com.google.gson.Gson
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/** 추천 데이터가 어디서 왔는지 표시용. */
enum class DataSource { REMOTE, CACHE, BUNDLED }

data class LoadResult(
    val response: RecommendationsResponse,
    val source: DataSource
)

/**
 * 추천 JSON 3단계 로딩 전략:
 *   1) 원격(raw.githubusercontent) 최신본 → 성공 시 로컬 캐시에 저장
 *   2) 실패 시 직전에 받아둔 로컬 캐시
 *   3) 그것도 없으면 앱에 번들된 assets/recommendations.json
 *
 * → 네트워크가 되면 항상 최신, 안 되면 마지막 성공본, 최초 실행이면 기본본.
 */
class RecommendationRepository(private val context: Context) {

    private val gson = Gson()
    private val cacheFile: File
        get() = File(context.filesDir, "recommendations_cache.json")

    suspend fun load(): LoadResult = withContext(Dispatchers.IO) {
        // 1) 원격 시도 (설정돼 있을 때만)
        if (RemoteConfig.isConfigured) {
            val remoteJson = fetchRemote()
            if (remoteJson != null) {
                val parsed = runCatching { gson.fromJson(remoteJson, RecommendationsResponse::class.java) }
                    .getOrNull()
                if (parsed != null && parsed.markets.kr.isNotEmpty()) {
                    runCatching { cacheFile.writeText(remoteJson) }   // 캐시 저장
                    return@withContext LoadResult(parsed, DataSource.REMOTE)
                }
            }
        }

        // 2) 로컬 캐시
        if (cacheFile.exists()) {
            runCatching {
                val cached = cacheFile.readText()
                gson.fromJson(cached, RecommendationsResponse::class.java)
            }.getOrNull()?.let {
                return@withContext LoadResult(it, DataSource.CACHE)
            }
        }

        // 3) 번들 asset (항상 존재)
        val bundled = context.assets.open("recommendations.json")
            .bufferedReader().use { it.readText() }
        val parsed = gson.fromJson(bundled, RecommendationsResponse::class.java)
        LoadResult(parsed, DataSource.BUNDLED)
    }

    private fun fetchRemote(): String? {
        return try {
            val conn = (URL(RemoteConfig.recommendationsUrl).openConnection() as HttpURLConnection).apply {
                connectTimeout = RemoteConfig.CONNECT_TIMEOUT_MS
                readTimeout = RemoteConfig.READ_TIMEOUT_MS
                requestMethod = "GET"
                setRequestProperty("Accept", "application/json")
            }
            conn.use { c ->
                if (c.responseCode == HttpURLConnection.HTTP_OK) {
                    c.inputStream.bufferedReader().use { it.readText() }
                } else {
                    Log.w(TAG, "원격 응답 코드 ${c.responseCode}")
                    null
                }
            }
        } catch (e: Exception) {
            Log.w(TAG, "원격 로딩 실패: ${e.message}")
            null
        }
    }

    // HttpURLConnection 에 use 확장 (자동 disconnect)
    private inline fun <T> HttpURLConnection.use(block: (HttpURLConnection) -> T): T {
        try {
            return block(this)
        } finally {
            disconnect()
        }
    }

    companion object {
        private const val TAG = "RecoRepository"
    }
}
