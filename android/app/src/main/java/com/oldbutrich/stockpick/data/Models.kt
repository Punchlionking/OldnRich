package com.oldbutrich.stockpick.data

import com.google.gson.annotations.SerializedName

data class RecommendationsResponse(
    @SerializedName("generated_at") val generatedAt: String,
    val version: Int,
    val markets: Markets
)

data class Markets(
    @SerializedName("KR") val kr: List<Recommendation>,
    @SerializedName("US") val us: List<Recommendation>
)

data class Recommendation(
    val ticker: String,
    val name: String,
    val market: String,
    val currency: String,
    @SerializedName("current_price") val currentPrice: Double,
    @SerializedName("overall_score") val overallScore: Double,
    @SerializedName("target_horizon") val targetHorizon: String,
    @SerializedName("primary_criterion") val primaryCriterion: String,
    @SerializedName("primary_label") val primaryLabel: String,
    @SerializedName("risk_level") val riskLevel: String,
    val reasons: List<CriterionResult>
)

data class CriterionResult(
    val key: String,
    val label: String,
    val score: Double,
    val horizon: String,
    val reason: String,
    val risk: String
)
