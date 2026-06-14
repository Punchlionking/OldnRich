package com.oldbutrich.stockpick.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.oldbutrich.stockpick.data.ChartSeries
import com.oldbutrich.stockpick.data.CompanyInfoRepository
import com.oldbutrich.stockpick.data.DataSource
import com.oldbutrich.stockpick.data.HistoryItem
import com.oldbutrich.stockpick.data.HistoryStore
import com.oldbutrich.stockpick.data.PriceHistoryRepository
import com.oldbutrich.stockpick.data.Recommendation
import com.oldbutrich.stockpick.data.RecommendationRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

data class RecommendationUiState(
    val krStocks: List<Recommendation> = emptyList(),
    val usStocks: List<Recommendation> = emptyList(),
    val generatedAt: String = "",
    val source: DataSource? = null,
    val isLoading: Boolean = true,
    val isRefreshing: Boolean = false,
    val error: String? = null
)

class RecommendationViewModel(application: Application) : AndroidViewModel(application) {

    private val repository = RecommendationRepository(application)
    private val historyStore = HistoryStore(application)
    private val priceRepo = PriceHistoryRepository()
    private val companyRepo = CompanyInfoRepository()

    private val _uiState = MutableStateFlow(RecommendationUiState())
    val uiState: StateFlow<RecommendationUiState> = _uiState

    /** 시장별 추천 이력(최신순). */
    fun history(market: String): List<HistoryItem> = historyStore.list(market)

    /** 최초 추천일~현재 일봉 차트 로딩. */
    suspend fun loadChart(item: HistoryItem): ChartSeries = priceRepo.load(item)

    /** 기업 개요(Wikipedia) 로딩. */
    suspend fun loadCompanyInfo(name: String, market: String): String? =
        companyRepo.load(name, market)

    init {
        load(isRefresh = false)
    }

    /** 수동 새로고침 (헤더 새로고침 버튼). */
    fun refresh() = load(isRefresh = true)

    private fun load(isRefresh: Boolean) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(
                isLoading = !isRefresh,
                isRefreshing = isRefresh,
                error = null
            )
            try {
                val result = repository.load()
                // 추천 이력 기록(중복은 최초만, 시장별 100개 한도)
                runCatching {
                    historyStore.record(result.response.markets.kr)
                    historyStore.record(result.response.markets.us)
                }
                _uiState.value = RecommendationUiState(
                    krStocks = result.response.markets.kr,
                    usStocks = result.response.markets.us,
                    generatedAt = formatDate(result.response.generatedAt),
                    source = result.source,
                    isLoading = false,
                    isRefreshing = false
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    isRefreshing = false,
                    error = "데이터를 불러오지 못했습니다: ${e.message}"
                )
            }
        }
    }

    private fun formatDate(isoDate: String): String {
        return try {
            val instant = Instant.parse(isoDate)
            val formatter = DateTimeFormatter
                .ofPattern("yyyy.MM.dd HH:mm")
                .withZone(ZoneId.of("Asia/Seoul"))
            formatter.format(instant) + " 기준"
        } catch (e: Exception) {
            isoDate
        }
    }
}
