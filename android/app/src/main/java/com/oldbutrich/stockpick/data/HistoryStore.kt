package com.oldbutrich.stockpick.data

import android.content.Context
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import java.io.File
import java.time.LocalDate

/** 추천 이력 1건. firstDate = 최초 추천일(이후 갱신되지 않음). */
data class HistoryItem(
    val ticker: String,
    val name: String,
    val market: String,        // "KR" | "US"
    val currency: String,
    val firstDate: String,     // ISO yyyy-MM-dd (최초 추천일)
    val firstPrice: Double,    // 최초 추천 시점 가격(차트 진입선)
    val firstLabel: String     // 최초 추천 사유(대표 기준)
)

/**
 * 추천 이력 영속 저장소 (filesDir/history.json).
 *  - 중복: (market+ticker) 기준, 최초 1건만 유지(firstDate 보존)
 *  - 한도: 국장/미장 각 100개. 초과 시 firstDate가 가장 오래된 것부터 삭제
 */
class HistoryStore(context: Context) {

    private val gson = Gson()
    private val file = File(context.filesDir, "history.json")
    private val capacityPerMarket = 100

    private fun loadAll(): MutableList<HistoryItem> {
        if (!file.exists()) return mutableListOf()
        return runCatching {
            val type = object : TypeToken<MutableList<HistoryItem>>() {}.type
            gson.fromJson<MutableList<HistoryItem>>(file.readText(), type) ?: mutableListOf()
        }.getOrDefault(mutableListOf())
    }

    private fun save(list: List<HistoryItem>) {
        runCatching { file.writeText(gson.toJson(list)) }
    }

    /** 오늘 추천된 종목들을 이력에 반영(중복은 최초만, 한도 초과분 정리). */
    fun record(recs: List<Recommendation>) {
        if (recs.isEmpty()) return
        val today = LocalDate.now().toString()
        val all = loadAll()
        val seen = all.map { it.market to it.ticker }.toHashSet()

        for (r in recs) {
            val key = r.market to r.ticker
            if (key in seen) continue          // 이미 있으면 최초것 유지(스킵)
            all.add(
                HistoryItem(
                    ticker = r.ticker, name = r.name, market = r.market,
                    currency = r.currency, firstDate = today,
                    firstPrice = r.currentPrice, firstLabel = r.primaryLabel
                )
            )
            seen.add(key)
        }

        // 시장별 한도 적용(오래된 firstDate부터 제거)
        val trimmed = mutableListOf<HistoryItem>()
        for (market in listOf("KR", "US")) {
            val ofMarket = all.filter { it.market == market }
                .sortedByDescending { it.firstDate }     // 최신 우선
                .take(capacityPerMarket)
            trimmed.addAll(ofMarket)
        }
        save(trimmed)
    }

    /** 시장별 이력(최신 추천일 순). */
    fun list(market: String): List<HistoryItem> =
        loadAll().filter { it.market == market }
            .sortedByDescending { it.firstDate }
}
