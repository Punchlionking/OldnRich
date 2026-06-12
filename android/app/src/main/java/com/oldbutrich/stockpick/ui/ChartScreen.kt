package com.oldbutrich.stockpick.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.oldbutrich.stockpick.data.ChartSeries
import com.oldbutrich.stockpick.data.HistoryItem
import com.oldbutrich.stockpick.ui.theme.Primary
import kotlin.math.roundToInt

private val UpColor = Color(0xFFDC2626)    // 한국식: 상승 빨강
private val DownColor = Color(0xFF2563EB)  // 하락 파랑

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChartScreen(
    item: HistoryItem,
    loader: suspend (HistoryItem) -> ChartSeries,
    onBack: () -> Unit
) {
    val series by produceState<ChartSeries?>(initialValue = null, item) {
        value = loader(item)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(item.name, fontWeight = FontWeight.Bold, fontSize = 17.sp)
                        Text("${item.ticker} · 최초 추천 ${item.firstDate.replace('-', '.')}",
                            fontSize = 11.sp,
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f))
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "뒤로")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface)
            )
        }
    ) { pad ->
        Box(Modifier.padding(pad).fillMaxSize().padding(16.dp)) {
            val s = series
            when {
                s == null -> Box(Modifier.fillMaxSize(), Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        CircularProgressIndicator(color = Primary)
                        Spacer(Modifier.height(10.dp))
                        Text("주가 추이 불러오는 중...",
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f))
                    }
                }
                s.points.size < 2 -> Box(Modifier.fillMaxSize(), Alignment.Center) {
                    Text(s.error ?: "표시할 데이터가 부족합니다",
                        color = MaterialTheme.colorScheme.error)
                }
                else -> ChartContent(item, s)
            }
        }
    }
}

@Composable
private fun ChartContent(item: HistoryItem, s: ChartSeries) {
    val first = item.firstPrice.takeIf { it > 0 } ?: s.points.first().close
    val last = s.points.last().close
    val change = (last / first - 1.0) * 100.0
    val up = change >= 0
    val accent = if (up) UpColor else DownColor

    Column(Modifier.fillMaxSize()) {
        // 요약: 추천가 → 현재가, 수익률
        Card(
            shape = RoundedCornerShape(16.dp),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
            modifier = Modifier.fillMaxWidth()
        ) {
            Row(Modifier.padding(18.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("추천 시점 대비", fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f))
                    Text("${"%+.1f".format(change)}%", fontSize = 26.sp,
                        fontWeight = FontWeight.ExtraBold, color = accent)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text("${formatPrice(first, item.currency)}  →  ${formatPrice(last, item.currency)}",
                        fontSize = 13.sp, fontWeight = FontWeight.SemiBold,
                        color = MaterialTheme.colorScheme.onSurface)
                    Text("${s.points.first().date} ~ ${s.points.last().date}",
                        fontSize = 10.sp,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.45f))
                }
            }
        }

        Spacer(Modifier.height(16.dp))

        // 라인 차트
        val closes = s.points.map { it.close }
        val minV = closes.min()
        val maxV = closes.max()
        val range = (maxV - minV).takeIf { it > 0 } ?: 1.0

        Card(
            shape = RoundedCornerShape(16.dp),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
            modifier = Modifier.fillMaxWidth().weight(1f)
        ) {
            Column(Modifier.padding(16.dp).fillMaxSize()) {
                // 선택된 지점(터치) 또는 기본(최고/최저) 표시
                var selectedIdx by remember(s) { mutableStateOf<Int?>(null) }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("일봉 종가 추이", fontSize = 13.sp, fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface)
                    Spacer(Modifier.weight(1f))
                    val sel = selectedIdx?.let { s.points.getOrNull(it) }
                    if (sel != null) {
                        Text("📍 ${sel.date}  ", fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f))
                        Text(formatPrice(sel.close, item.currency), fontSize = 13.sp,
                            fontWeight = FontWeight.Bold, color = accent)
                    } else {
                        Text("터치해 날짜·가격 확인", fontSize = 11.sp,
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.4f))
                    }
                }
                Spacer(Modifier.height(4.dp))
                Text("최고 ${formatPrice(maxV, item.currency)} · 최저 ${formatPrice(minV, item.currency)}",
                    fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f))
                Spacer(Modifier.height(12.dp))

                val gridColor = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.08f)
                val markColor = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.45f)
                val crossColor = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
                // 추천일에 해당하는 인덱스(이상 첫 지점)
                val recDate = runCatching { java.time.LocalDate.parse(item.firstDate) }.getOrNull()
                val recIdx = if (recDate != null)
                    s.points.indexOfFirst { !it.date.isBefore(recDate) }.let { if (it < 0) s.points.size - 1 else it }
                else 0
                val n = closes.size
                Canvas(
                    Modifier.fillMaxSize()
                        .pointerInput(n) {
                            detectDragGestures(
                                onDragStart = { off ->
                                    selectedIdx = ((off.x / size.width) * (n - 1)).roundToInt().coerceIn(0, n - 1)
                                },
                                onDrag = { ch, _ ->
                                    selectedIdx = ((ch.position.x / size.width) * (n - 1)).roundToInt().coerceIn(0, n - 1)
                                }
                            )
                        }
                        .pointerInput(n) {
                            detectTapGestures { off ->
                                selectedIdx = ((off.x / size.width) * (n - 1)).roundToInt().coerceIn(0, n - 1)
                            }
                        }
                ) {
                    val w = size.width
                    val h = size.height
                    fun x(i: Int) = w * i / (n - 1)
                    fun y(v: Double) = (h * (1.0 - (v - minV) / range)).toFloat()

                    for (g in 0..4) {
                        val gy = h * g / 4f
                        drawLine(gridColor, Offset(0f, gy), Offset(w, gy), strokeWidth = 1f)
                    }

                    // 추천 시점 세로선
                    val recX = x(recIdx)
                    drawLine(markColor, Offset(recX, 0f), Offset(recX, h), strokeWidth = 2f,
                        pathEffect = PathEffect.dashPathEffect(floatArrayOf(10f, 8f)))

                    // 추천가 가로선
                    val baseY = y(first)
                    drawLine(accent.copy(alpha = 0.4f), Offset(0f, baseY), Offset(w, baseY),
                        strokeWidth = 2f,
                        pathEffect = PathEffect.dashPathEffect(floatArrayOf(12f, 8f)))

                    // 면적
                    val area = Path().apply {
                        moveTo(0f, h)
                        for (i in closes.indices) lineTo(x(i), y(closes[i]))
                        lineTo(w, h); close()
                    }
                    drawPath(area, Brush.verticalGradient(
                        listOf(accent.copy(alpha = 0.22f), accent.copy(alpha = 0.0f))))

                    // 종가 라인
                    val line = Path().apply {
                        moveTo(x(0), y(closes[0]))
                        for (i in 1 until n) lineTo(x(i), y(closes[i]))
                    }
                    drawPath(line, color = accent, style = Stroke(width = 3.5f))

                    drawCircle(accent, radius = 6f, center = Offset(x(0), y(closes.first())))
                    drawCircle(accent, radius = 7f, center = Offset(x(n - 1), y(closes.last())))

                    // 터치 크로스헤어
                    selectedIdx?.let { si ->
                        val cx = x(si); val cy = y(closes[si])
                        drawLine(crossColor, Offset(cx, 0f), Offset(cx, h), strokeWidth = 1.5f)
                        drawCircle(Color.White, radius = 9f, center = Offset(cx, cy))
                        drawCircle(accent, radius = 6f, center = Offset(cx, cy))
                    }
                }
            }
        }

        Spacer(Modifier.height(10.dp))
        Text("· 세로 점선 = 추천 시점, 가로 점선 = 추천가 · 차트를 드래그하면 날짜·가격 표시",
            fontSize = 10.sp, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.4f))
    }
}
