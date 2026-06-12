package com.oldbutrich.stockpick.ui

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.KeyboardArrowRight
import androidx.compose.material3.*
import androidx.compose.material3.TabRowDefaults.tabIndicatorOffset
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.oldbutrich.stockpick.data.HistoryItem
import com.oldbutrich.stockpick.ui.theme.Primary
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
fun HistoryScreen(
    krHistory: List<HistoryItem>,
    usHistory: List<HistoryItem>,
    onItemClick: (HistoryItem) -> Unit,
    onBack: () -> Unit
) {
    val tabs = listOf("🇰🇷  국장 (${krHistory.size})", "🇺🇸  미장 (${usHistory.size})")
    val pager = rememberPagerState(pageCount = { tabs.size })
    val scope = rememberCoroutineScope()

    Scaffold(
        topBar = {
            Column {
                Surface(color = Primary, shadowElevation = 4.dp) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.fillMaxWidth().statusBarsPadding()
                            .padding(start = 4.dp, end = 20.dp, top = 8.dp, bottom = 8.dp)
                    ) {
                        IconButton(onClick = onBack) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, "뒤로", tint = Color.White)
                        }
                        Column {
                            Text("추천 이력", fontSize = 20.sp,
                                fontWeight = FontWeight.ExtraBold, color = Color.White)
                            Text("과거 추천 종목 · 최초 추천일 기준 주가 추이",
                                fontSize = 11.sp, color = Color.White.copy(alpha = 0.75f))
                        }
                    }
                }
                TabRow(
                    selectedTabIndex = pager.currentPage,
                    containerColor = MaterialTheme.colorScheme.surface,
                    contentColor = Primary,
                    indicator = { tp ->
                        TabRowDefaults.PrimaryIndicator(
                            Modifier.tabIndicatorOffset(tp[pager.currentPage]), color = Primary)
                    }
                ) {
                    tabs.forEachIndexed { i, label ->
                        Tab(selected = pager.currentPage == i,
                            onClick = { scope.launch { pager.animateScrollToPage(i) } },
                            text = { Text(label, fontSize = 14.sp,
                                fontWeight = if (pager.currentPage == i) FontWeight.Bold else FontWeight.Normal) })
                    }
                }
            }
        }
    ) { pad ->
        HorizontalPager(state = pager, modifier = Modifier.padding(pad).fillMaxSize()) { page ->
            val list = if (page == 0) krHistory else usHistory
            if (list.isEmpty()) {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("아직 추천 이력이 없습니다.\n앱을 실행할 때마다 추천 종목이 기록됩니다.",
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f),
                        fontSize = 14.sp)
                }
            } else {
                LazyColumn(
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    items(list, key = { it.market + it.ticker }) { item ->
                        HistoryCard(item, onClick = { onItemClick(item) })
                    }
                }
            }
        }
    }
}

@Composable
private fun HistoryCard(item: HistoryItem, onClick: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(16.dp)
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(item.name, fontWeight = FontWeight.Bold, fontSize = 16.sp,
                    color = MaterialTheme.colorScheme.onSurface)
                Text(item.ticker, fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f))
                Spacer(Modifier.height(6.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(20.dp))
                            .background(Primary.copy(alpha = 0.1f))
                            .padding(horizontal = 8.dp, vertical = 3.dp)
                    ) {
                        Text("최초 추천 ${item.firstDate.replace('-', '.')}",
                            fontSize = 11.sp, color = Primary, fontWeight = FontWeight.Medium)
                    }
                    Spacer(Modifier.width(6.dp))
                    Text(item.firstLabel, fontSize = 11.sp,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.55f))
                }
            }
            Column(horizontalAlignment = Alignment.End) {
                Text("추천가", fontSize = 10.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f))
                Text(formatPrice(item.firstPrice, item.currency),
                    fontSize = 13.sp, fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onSurface)
            }
            Icon(Icons.Default.KeyboardArrowRight, null,
                tint = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.3f))
        }
    }
}
