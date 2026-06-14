package com.oldbutrich.stockpick.data

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

/**
 * 기업 개요(간단 설명) 조회 — Wikipedia.
 *  - KR: ko.wikipedia (종목명으로 바로 조회, 한국어 산문)
 *  - US: en.wikipedia (opensearch로 정확한 문서 찾은 뒤 요약)
 * 없으면 null(앱에서 개요 카드 숨김).
 */
class CompanyInfoRepository {

    suspend fun load(name: String, market: String): String? = withContext(Dispatchers.IO) {
        try {
            if (market == "KR") summary("ko", name)
            else {
                val title = searchTitle("en", name) ?: name
                summary("en", title)
            }
        } catch (e: Exception) {
            Log.w(TAG, "기업개요 실패 $name: ${e.message}")
            null
        }
    }

    /** REST summary → extract(산문). 동음이의/없음이면 null. */
    private fun summary(lang: String, title: String): String? {
        val t = URLEncoder.encode(title.replace(' ', '_'), "UTF-8")
        val body = httpGet("https://$lang.wikipedia.org/api/rest_v1/page/summary/$t") ?: return null
        val j = JSONObject(body)
        if (j.optString("type") == "disambiguation") return null
        val extract = j.optString("extract").trim()
        if (extract.isBlank()) return null
        return trimSentences(extract)
    }

    /** opensearch로 가장 적합한 문서 제목 찾기(US 동음이의 회피). */
    private fun searchTitle(lang: String, name: String): String? {
        val q = URLEncoder.encode("$name company", "UTF-8")
        val body = httpGet("https://$lang.wikipedia.org/w/api.php" +
                "?action=opensearch&search=$q&limit=1&namespace=0&format=json") ?: return null
        val arr = JSONArray(body)
        val titles = arr.optJSONArray(1) ?: return null
        return if (titles.length() > 0) titles.getString(0) else null
    }

    /** 너무 길면 처음 2~3문장(~220자)로 자름. */
    private fun trimSentences(text: String): String {
        if (text.length <= 220) return text
        val cut = text.take(220)
        val lastDot = cut.lastIndexOfAny(charArrayOf('.', '。'))
        return (if (lastDot > 80) cut.substring(0, lastDot + 1) else cut.trimEnd()) + " …"
    }

    private fun httpGet(urlStr: String): String? {
        val conn = (URL(urlStr).openConnection() as HttpURLConnection).apply {
            connectTimeout = 7000
            readTimeout = 9000
            requestMethod = "GET"
            setRequestProperty("User-Agent", "OldnRich/1.0")
        }
        return try {
            if (conn.responseCode != HttpURLConnection.HTTP_OK) null
            else conn.inputStream.bufferedReader().use { it.readText() }
        } finally {
            conn.disconnect()
        }
    }

    companion object { private const val TAG = "CompanyInfoRepo" }
}
