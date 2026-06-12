package com.oldbutrich.stockpick.ui

import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.background
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.DateRange
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Refresh
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
import com.oldbutrich.stockpick.data.DataSource
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.oldbutrich.stockpick.data.HistoryItem
import com.oldbutrich.stockpick.data.Recommendation
import com.oldbutrich.stockpick.ui.theme.Primary
import com.oldbutrich.stockpick.viewmodel.RecommendationViewModel
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
fun StockApp(vm: RecommendationViewModel = viewModel()) {
    val uiState by vm.uiState.collectAsState()
    val navController = rememberNavController()

    // 네비게이션에 넘길 임시 선택 항목
    var selectedStock by remember { mutableStateOf<Recommendation?>(null) }
    var selectedHistory by remember { mutableStateOf<HistoryItem?>(null) }

    NavHost(
        navController = navController,
        startDestination = "list",
        enterTransition  = { slideInHorizontally(initialOffsetX = { it }) },
        exitTransition   = { slideOutHorizontally(targetOffsetX = { -it / 3 }) },
        popEnterTransition  = { slideInHorizontally(initialOffsetX = { -it / 3 }) },
        popExitTransition   = { slideOutHorizontally(targetOffsetX = { it }) }
    ) {
        composable("list") {
            StockListRootScreen(
                uiState = uiState,
                onRefresh = { vm.refresh() },
                onOpenHistory = { navController.navigate("history") },
                onOpenHelp = { navController.navigate("help") },
                onStockClick = { stock ->
                    selectedStock = stock
                    navController.navigate("detail")
                }
            )
        }
        composable("detail") {
            selectedStock?.let { stock ->
                StockDetailScreen(stock = stock, onBack = { navController.popBackStack() })
            }
        }
        composable("history") {
            // 진입 시점에 이력 스냅샷
            val kr = remember { vm.history("KR") }
            val us = remember { vm.history("US") }
            HistoryScreen(
                krHistory = kr, usHistory = us,
                onItemClick = { item ->
                    selectedHistory = item
                    navController.navigate("chart")
                },
                onBack = { navController.popBackStack() }
            )
        }
        composable("chart") {
            selectedHistory?.let { item ->
                ChartScreen(
                    item = item,
                    loader = { vm.loadChart(it) },
                    onBack = { navController.popBackStack() }
                )
            }
        }
        composable("help") {
            HelpScreen(onBack = { navController.popBackStack() })
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
fun StockListRootScreen(
    uiState: com.oldbutrich.stockpick.viewmodel.RecommendationUiState,
    onRefresh: () -> Unit,
    onOpenHistory: () -> Unit,
    onOpenHelp: () -> Unit,
    onStockClick: (Recommendation) -> Unit
) {
    val tabs = listOf("🇰🇷  국장", "🇺🇸  미장")
    val pagerState = rememberPagerState(pageCount = { tabs.size })
    val scope = rememberCoroutineScope()

    Scaffold(
        topBar = {
            Column {
                // ── 앱 헤더
                Surface(
                    color = Primary,
                    shadowElevation = 4.dp
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier
                            .fillMaxWidth()
                            .statusBarsPadding()
                            .padding(start = 20.dp, end = 8.dp, top = 14.dp, bottom = 14.dp)
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = "오늘의 추천주",
                                fontSize = 22.sp,
                                fontWeight = FontWeight.ExtraBold,
                                color = Color.White
                            )
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                if (uiState.generatedAt.isNotEmpty()) {
                                    Text(
                                        text = uiState.generatedAt,
                                        fontSize = 12.sp,
                                        color = Color.White.copy(alpha = 0.75f)
                                    )
                                }
                                uiState.source?.let { src ->
                                    Spacer(Modifier.width(6.dp))
                                    DataSourceBadge(src)
                                }
                            }
                        }
                        // 새로고침
                        IconButton(onClick = onRefresh, enabled = !uiState.isRefreshing) {
                            if (uiState.isRefreshing) {
                                CircularProgressIndicator(
                                    color = Color.White, strokeWidth = 2.dp,
                                    modifier = Modifier.size(22.dp)
                                )
                            } else {
                                Icon(Icons.Default.Refresh, "새로고침", tint = Color.White)
                            }
                        }
                        // trace back (추천 이력)
                        IconButton(onClick = onOpenHistory) {
                            Icon(Icons.Default.DateRange, "추천 이력", tint = Color.White)
                        }
                        // 도움말 (추천 기준) — 젤 우측
                        IconButton(onClick = onOpenHelp) {
                            Icon(Icons.Default.Info, "추천 기준 도움말", tint = Color.White)
                        }
                    }
                }

                // ── 탭 바
                TabRow(
                    selectedTabIndex = pagerState.currentPage,
                    containerColor = MaterialTheme.colorScheme.surface,
                    contentColor = Primary,
                    indicator = { tabPositions ->
                        TabRowDefaults.PrimaryIndicator(
                            modifier = Modifier.tabIndicatorOffset(tabPositions[pagerState.currentPage]),
                            color = Primary
                        )
                    }
                ) {
                    tabs.forEachIndexed { index, label ->
                        Tab(
                            selected = pagerState.currentPage == index,
                            onClick = { scope.launch { pagerState.animateScrollToPage(index) } },
                            text = {
                                Text(
                                    text = label,
                                    fontWeight = if (pagerState.currentPage == index)
                                        FontWeight.Bold else FontWeight.Normal,
                                    fontSize = 15.sp
                                )
                            }
                        )
                    }
                }
            }
        }
    ) { innerPadding ->
        Box(modifier = Modifier.padding(innerPadding)) {
            when {
                uiState.isLoading -> {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            CircularProgressIndicator(color = Primary)
                            Spacer(Modifier.height(12.dp))
                            Text("추천 종목 분석 중...", color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f))
                        }
                    }
                }
                uiState.error != null -> {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text(
                            text = uiState.error,
                            color = MaterialTheme.colorScheme.error,
                            modifier = Modifier.padding(24.dp)
                        )
                    }
                }
                else -> {
                    HorizontalPager(
                        state = pagerState,
                        modifier = Modifier.fillMaxSize()
                    ) { page ->
                        val stocks = if (page == 0) uiState.krStocks else uiState.usStocks
                        StockListScreen(
                            stocks = stocks,
                            onStockClick = onStockClick
                        )
                    }
                }
            }
        }
    }
}

/** 데이터 출처 배지: 실시간(원격) / 캐시 / 기본(번들). */
@Composable
fun DataSourceBadge(source: DataSource) {
    val (label, dot) = when (source) {
        DataSource.REMOTE  -> "실시간" to Color(0xFF4ADE80)   // 초록
        DataSource.CACHE   -> "캐시"   to Color(0xFFFBBF24)   // 노랑
        DataSource.BUNDLED -> "기본"   to Color(0xFF94A3B8)   // 회색
    }
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier
            .clip(RoundedCornerShape(20.dp))
            .background(Color.White.copy(alpha = 0.18f))
            .padding(horizontal = 7.dp, vertical = 2.dp)
    ) {
        Box(
            modifier = Modifier
                .size(6.dp)
                .clip(RoundedCornerShape(50))
                .background(dot)
        )
        Spacer(Modifier.width(4.dp))
        Text(
            text = label,
            fontSize = 10.sp,
            fontWeight = FontWeight.SemiBold,
            color = Color.White
        )
    }
}
