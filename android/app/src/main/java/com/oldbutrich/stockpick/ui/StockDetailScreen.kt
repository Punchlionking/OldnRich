package com.oldbutrich.stockpick.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.oldbutrich.stockpick.data.CriterionResult
import com.oldbutrich.stockpick.data.Recommendation
import com.oldbutrich.stockpick.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StockDetailScreen(
    stock: Recommendation,
    loadCompany: suspend (String, String) -> String?,
    onBack: () -> Unit
) {
    // 기업 개요 온디맨드 로딩 (Wikipedia). null=로딩중, ""=없음, 그외=내용
    val overview by produceState<String?>(initialValue = null, stock.ticker) {
        value = loadCompany(stock.name, stock.market) ?: ""
    }
    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            text = stock.name,
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = stock.ticker,
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
                        )
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "뒤로가기")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface
                )
            )
        }
    ) { innerPadding ->
        LazyColumn(
            contentPadding = PaddingValues(
                start = 16.dp, end = 16.dp,
                top = innerPadding.calculateTopPadding() + 12.dp,
                bottom = 24.dp
            ),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            // ── 요약 헤더 카드
            item {
                SummaryCard(stock = stock)
            }

            // ── 기업 개요 (Wikipedia) — 로딩중이거나 내용 있을 때만
            if (overview == null || overview!!.isNotBlank()) {
                item { CompanyOverviewCard(overview) }
            }

            // ── 섹션 제목
            item {
                Text(
                    text = "📋 추천 이유 상세",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onBackground,
                    modifier = Modifier.padding(top = 4.dp, bottom = 2.dp)
                )
            }

            // ── 기준별 이유 카드 (펼침/접힘)
            itemsIndexed(stock.reasons) { index, criterion ->
                CriterionCard(
                    criterion = criterion,
                    isPrimary = index == 0
                )
            }

            // ── 면책 고지
            item {
                DisclaimerCard()
            }
        }
    }
}

@Composable
fun SummaryCard(stock: Recommendation) {
    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = Primary),
        elevation = CardDefaults.cardElevation(defaultElevation = 4.dp),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(modifier = Modifier.padding(20.dp)) {
            // 가격 + 시장
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = "현재가",
                        style = MaterialTheme.typography.labelSmall,
                        color = Color.White.copy(alpha = 0.7f)
                    )
                    Text(
                        text = formatPrice(stock.currentPrice, stock.currency),
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.Bold,
                        color = Color.White
                    )
                }
                Column(horizontalAlignment = Alignment.End) {
                    MarketBadge(market = stock.market)
                    Spacer(Modifier.height(6.dp))
                    HorizonBadgeWhite(horizon = stock.targetHorizon)
                }
            }

            Spacer(Modifier.height(16.dp))

            // 점수 + 대표기준
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = "종합 점수",
                        style = MaterialTheme.typography.labelSmall,
                        color = Color.White.copy(alpha = 0.7f)
                    )
                    Text(
                        text = "%.1f / 100".format(stock.overallScore),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = Color.White
                    )
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(
                        text = "대표 기준",
                        style = MaterialTheme.typography.labelSmall,
                        color = Color.White.copy(alpha = 0.7f)
                    )
                    Text(
                        text = stock.primaryLabel,
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.SemiBold,
                        color = Color.White
                    )
                }
            }

            Spacer(Modifier.height(12.dp))

            // 종합 점수 바
            LinearProgressIndicator(
                progress = { (stock.overallScore.toFloat() / 100f).coerceIn(0f, 1f) },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(8.dp)
                    .clip(RoundedCornerShape(4.dp)),
                color = Color.White,
                trackColor = Color.White.copy(alpha = 0.25f)
            )
        }
    }
}

@Composable
fun CriterionCard(criterion: CriterionResult, isPrimary: Boolean) {
    var expanded by remember { mutableStateOf(isPrimary) }

    Card(
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (isPrimary)
                MaterialTheme.colorScheme.primaryContainer
            else
                MaterialTheme.colorScheme.surface
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = if (isPrimary) 3.dp else 1.dp),
        modifier = Modifier
            .fillMaxWidth()
            .clickable { expanded = !expanded }
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            // 헤더 행
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                // 기준 아이콘
                Box(
                    contentAlignment = Alignment.Center,
                    modifier = Modifier
                        .size(36.dp)
                        .clip(RoundedCornerShape(10.dp))
                        .background(criterionColor(criterion.key).copy(alpha = 0.15f))
                ) {
                    Text(text = criterionEmoji(criterion.key), fontSize = 17.sp)
                }

                Spacer(Modifier.width(10.dp))

                Column(modifier = Modifier.weight(1f)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            text = criterion.label,
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.Bold
                        )
                        if (isPrimary) {
                            Spacer(Modifier.width(6.dp))
                            Box(
                                modifier = Modifier
                                    .clip(RoundedCornerShape(20.dp))
                                    .background(Primary)
                                    .padding(horizontal = 7.dp, vertical = 2.dp)
                            ) {
                                Text(
                                    text = "대표",
                                    color = Color.White,
                                    fontSize = 10.sp,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                        }
                        if (criterion.risk == "높음") {
                            Spacer(Modifier.width(6.dp))
                            Box(
                                modifier = Modifier
                                    .clip(RoundedCornerShape(20.dp))
                                    .background(RiskHigh.copy(alpha = 0.1f))
                                    .padding(horizontal = 7.dp, vertical = 2.dp)
                            ) {
                                Text(
                                    text = "⚠ 고위험",
                                    color = RiskHigh,
                                    fontSize = 10.sp,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                        }
                    }
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        SmallHorizonChip(horizon = criterion.horizon)
                        Spacer(Modifier.width(8.dp))
                        Text(
                            text = "점수 %.0f".format(criterion.score),
                            style = MaterialTheme.typography.labelSmall,
                            color = criterionColor(criterion.key),
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                }

                Icon(
                    imageVector = if (expanded) Icons.Default.KeyboardArrowUp
                                  else Icons.Default.KeyboardArrowDown,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.4f)
                )
            }

            // 점수 바
            Spacer(Modifier.height(10.dp))
            LinearProgressIndicator(
                progress = { (criterion.score.toFloat() / 100f).coerceIn(0f, 1f) },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(5.dp)
                    .clip(RoundedCornerShape(3.dp)),
                color = criterionColor(criterion.key),
                trackColor = criterionColor(criterion.key).copy(alpha = 0.12f)
            )

            // 펼쳐진 이유 텍스트
            AnimatedVisibility(
                visible = expanded,
                enter = fadeIn() + expandVertically(),
                exit = fadeOut() + shrinkVertically()
            ) {
                Column {
                    Spacer(Modifier.height(12.dp))
                    Divider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.3f))
                    Spacer(Modifier.height(10.dp))
                    Text(
                        text = criterion.reason,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.85f),
                        lineHeight = 22.sp
                    )
                }
            }
        }
    }
}

@Composable
fun SmallHorizonChip(horizon: String) {
    val color = when (horizon) {
        "단기" -> HorizonShort
        "중기" -> HorizonMid
        "장기" -> HorizonLong
        else   -> Color.Gray
    }
    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(20.dp))
            .background(color.copy(alpha = 0.1f))
            .padding(horizontal = 7.dp, vertical = 2.dp)
    ) {
        Text(
            text = horizon,
            fontSize = 10.sp,
            fontWeight = FontWeight.SemiBold,
            color = color
        )
    }
}

@Composable
fun HorizonBadgeWhite(horizon: String) {
    val emoji = when (horizon) {
        "단기" -> "⚡"
        "중기" -> "📈"
        "장기" -> "🏆"
        else   -> "•"
    }
    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(20.dp))
            .background(Color.White.copy(alpha = 0.2f))
            .padding(horizontal = 10.dp, vertical = 4.dp)
    ) {
        Text(
            text = "$emoji $horizon",
            fontSize = 13.sp,
            fontWeight = FontWeight.Bold,
            color = Color.White
        )
    }
}

@Composable
fun MarketBadge(market: String) {
    val (label, bg) = if (market == "KR")
        "🇰🇷 국장" to Color(0xFF15803D)
    else
        "🇺🇸 미장" to Color(0xFFB45309)

    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(20.dp))
            .background(bg)
            .padding(horizontal = 10.dp, vertical = 4.dp)
    ) {
        Text(text = label, fontSize = 11.sp, fontWeight = FontWeight.Bold, color = Color.White)
    }
}

@Composable
fun CompanyOverviewCard(overview: String?) {
    Card(
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text("🏢 기업 개요", style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurface)
            Spacer(Modifier.height(8.dp))
            if (overview == null) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    CircularProgressIndicator(
                        strokeWidth = 2.dp, color = Primary,
                        modifier = Modifier.size(16.dp))
                    Spacer(Modifier.width(8.dp))
                    Text("개요 불러오는 중...", fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f))
                }
            } else {
                Text(overview, fontSize = 13.sp, lineHeight = 20.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.8f))
                Spacer(Modifier.height(6.dp))
                Text("출처: Wikipedia", fontSize = 10.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.4f))
            }
        }
    }
}

@Composable
fun DisclaimerCard() {
    Card(
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        ),
        modifier = Modifier.fillMaxWidth()
    ) {
        Text(
            text = "⚠ 면책 고지\n이 추천은 정보 제공 목적이며, 투자 수익을 보장하지 않습니다. " +
                   "모든 투자 결정의 책임은 투자자 본인에게 있습니다. " +
                   "주식 투자는 원금 손실의 위험이 있습니다.",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.55f),
            lineHeight = 18.sp,
            modifier = Modifier.padding(14.dp)
        )
    }
}

fun criterionColor(key: String): Color = when (key) {
    "undervalued"  -> Color(0xFF16A34A)   // 초록
    "theme"        -> Color(0xFFA855F7)   // 보라
    "rumor"        -> Color(0xFFEF4444)   // 빨강
    "quant"        -> Color(0xFF0EA5E9)   // 하늘
    "target_gap"   -> Color(0xFFF97316)   // 주황
    "beneficiary"  -> Color(0xFF6366F1)   // 인디고
    "earnings"     -> Color(0xFF10B981)   // 에메랄드
    "blog"         -> Color(0xFFF59E0B)   // 앰버
    // v2 확장 팩터
    "mom_12_1"     -> Color(0xFF2563EB)   // 블루 (모멘텀)
    "fscore"       -> Color(0xFF059669)   // 딥그린 (퀄리티)
    "fcf_yield"    -> Color(0xFF0D9488)   // 틸
    "roic"         -> Color(0xFF7C3AED)   // 바이올렛
    "accruals"     -> Color(0xFF65A30D)   // 라임
    "est_revision" -> Color(0xFFDB2777)   // 핑크 (이벤트)
    "governance"   -> Color(0xFF0891B2)   // 시안 (국장 특화)
    "insider"      -> Color(0xFFCA8A04)   // 골드
    else           -> Color(0xFF6B7280)
}

fun criterionEmoji(key: String): String = when (key) {
    "undervalued"  -> "💎"
    "theme"        -> "🔥"
    "rumor"        -> "📡"
    "quant"        -> "📊"
    "target_gap"   -> "🎯"
    "beneficiary"  -> "🔗"
    "earnings"     -> "📈"
    "blog"         -> "📰"
    // v2 확장 팩터
    "mom_12_1"     -> "🚀"
    "fscore"       -> "🏅"
    "fcf_yield"    -> "💵"
    "roic"         -> "⚙️"
    "accruals"     -> "🧾"
    "est_revision" -> "🔼"
    "governance"   -> "🏛️"
    "insider"      -> "🤝"
    else           -> "•"
}
