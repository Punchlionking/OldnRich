package com.oldbutrich.stockpick.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// 앱 브랜드 색상
val Primary        = Color(0xFF1A56DB)   // 딥 블루
val PrimaryVariant = Color(0xFF1E40AF)
val Secondary      = Color(0xFF0EA5E9)

// 시점 배지 색상
val HorizonShort  = Color(0xFFEF4444)   // 단기 - 빨강
val HorizonMid    = Color(0xFFF97316)   // 중기 - 주황
val HorizonLong   = Color(0xFF3B82F6)   // 장기 - 파랑

// 위험도
val RiskHigh      = Color(0xFFDC2626)
val RiskNormal    = Color(0xFF16A34A)

// 점수 바
val ScoreColor    = Color(0xFF6366F1)

// 롱테일(신흥 강자) 강조색 — 보라/마젠타 계열로 코어와 구분
val LongtailAccent = Color(0xFF9333EA)

val LightColors = lightColorScheme(
    primary          = Primary,
    onPrimary        = Color.White,
    primaryContainer = Color(0xFFDBEAFE),
    secondary        = Secondary,
    onSecondary      = Color.White,
    background       = Color(0xFFF8FAFC),
    surface          = Color.White,
    onBackground     = Color(0xFF0F172A),
    onSurface        = Color(0xFF1E293B),
    surfaceVariant   = Color(0xFFF1F5F9),
    outline          = Color(0xFFCBD5E1),
)

@Composable
fun OldbutRichTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = LightColors,
        content = content
    )
}
