package com.oldbutrich.stockpick.data

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL
import java.time.LocalDate
import java.time.format.DateTimeFormatter

/** 일봉 한 점. */
data class PricePoint(val date: LocalDate, val close: Double)

data class ChartSeries(
    val points: List<PricePoint>,
    val error: String? = null
)

/**
 * 최초 추천일~현재의 일봉 종가 시계열을 가져온다(키 불필요).
 *  - KR: 네이버 금융 siseJson
 *  - US: Stooq CSV
 */
class PriceHistoryRepository {

    suspend fun load(item: HistoryItem): ChartSeries = withContext(Dispatchers.IO) {
        val recDate = runCatching { LocalDate.parse(item.firstDate) }
            .getOrDefault(LocalDate.now().minusMonths(3))
        val end = LocalDate.now()
        // 추천 시점부터가 핵심이지만, 당일/최근 추천이면 차트가 비므로
        // 추천일 이전 ~35일 맥락도 함께 조회(추천 시점은 화면에 세로선으로 표시).
        val start = minOf(recDate, end.minusDays(35))
        try {
            val pts = if (item.market == "KR") fetchNaver(item.ticker, start, end)
            else fetchStooq(item.ticker, start, end)
            if (pts.isEmpty()) ChartSeries(emptyList(), "가격 데이터가 없습니다")
            else ChartSeries(pts)
        } catch (e: Exception) {
            Log.w(TAG, "차트 로딩 실패 ${item.ticker}: ${e.message}")
            ChartSeries(emptyList(), "네트워크 오류: ${e.message}")
        }
    }

    // --- KR: 네이버 ---------------------------------------------------------
    private fun fetchNaver(code: String, start: LocalDate, end: LocalDate): List<PricePoint> {
        val f = DateTimeFormatter.ofPattern("yyyyMMdd")
        val url = "https://api.finance.naver.com/siseJson.naver?symbol=$code" +
                "&requestType=1&startTime=${start.format(f)}&endTime=${end.format(f)}&timeframe=day"
        val body = httpGet(url, naver = true)
        // ["YYYYMMDD", open, high, low, close, volume, foreign]
        val rowRegex = Regex("""\["(\d{8})",\s*([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)""")
        val df = DateTimeFormatter.ofPattern("yyyyMMdd")
        return rowRegex.findAll(body).mapNotNull { m ->
            runCatching {
                PricePoint(LocalDate.parse(m.groupValues[1], df), m.groupValues[5].toDouble())
            }.getOrNull()
        }.toList()
    }

    // --- US: Yahoo Finance (Stooq 봇차단 대체) ------------------------------
    private fun fetchStooq(ticker: String, start: LocalDate, end: LocalDate): List<PricePoint> {
        val zone = java.time.ZoneOffset.UTC
        val p1 = start.atStartOfDay(zone).toEpochSecond()
        val p2 = end.plusDays(1).atStartOfDay(zone).toEpochSecond()
        val url = "https://query1.finance.yahoo.com/v8/finance/chart/$ticker" +
                "?period1=$p1&period2=$p2&interval=1d"
        val body = httpGet(url, naver = true)   // UA 필요
        // JSON: ...timestamp":[...]... "close":[...]
        val tsBlock = Regex(""""timestamp":\[(.*?)]""").find(body)?.groupValues?.get(1) ?: return emptyList()
        val closeBlock = Regex(""""close":\[(.*?)]""").find(body)?.groupValues?.get(1) ?: return emptyList()
        val ts = tsBlock.split(',').mapNotNull { it.trim().toLongOrNull() }
        val cl = closeBlock.split(',').map { it.trim().toDoubleOrNull() }
        val out = ArrayList<PricePoint>()
        for (i in ts.indices) {
            val c = cl.getOrNull(i) ?: continue
            if (c <= 0) continue
            val d = java.time.Instant.ofEpochSecond(ts[i]).atZone(zone).toLocalDate()
            out.add(PricePoint(d, c))
        }
        return out
    }

    private fun httpGet(urlStr: String, naver: Boolean): String {
        val conn = (URL(urlStr).openConnection() as HttpURLConnection).apply {
            connectTimeout = 8000
            readTimeout = 10000
            requestMethod = "GET"
            if (naver) setRequestProperty("User-Agent", "Mozilla/5.0")
        }
        try {
            if (conn.responseCode != HttpURLConnection.HTTP_OK)
                throw RuntimeException("HTTP ${conn.responseCode}")
            return conn.inputStream.bufferedReader().use { it.readText() }
        } finally {
            conn.disconnect()
        }
    }

    companion object { private const val TAG = "PriceHistoryRepo" }
}
