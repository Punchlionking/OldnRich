package com.oldbutrich.stockpick.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.oldbutrich.stockpick.ui.theme.HorizonLong
import com.oldbutrich.stockpick.ui.theme.HorizonMid
import com.oldbutrich.stockpick.ui.theme.HorizonShort
import com.oldbutrich.stockpick.ui.theme.Primary

private data class CriterionDoc(
    val key: String, val label: String, val group: String, val horizon: String, val desc: String
)

private val DOCS = listOf(
    CriterionDoc("mom_12_1", "중기 모멘텀(12-1)", "통계", "중기",
        "최근 1개월을 제외한 과거 12개월 수익률. 직전 1개월은 단기 반전 노이즈라 빼며, 수십 년간 거의 모든 시장에서 검증된 가장 강건한 모멘텀 팩터입니다."),
    CriterionDoc("quant", "퀀트·차트 신호", "통계", "단기",
        "RSI 과매도 반등 + MACD 골든크로스 + 볼린저밴드 하단 지지를 종합한 단기 기술적 매수 신호."),
    CriterionDoc("theme", "테마 급부상", "테마", "단기",
        "동일 테마군의 거래량이 평소 대비 급증하고 섹터 강도가 높은지를 봅니다. 갑자기 주목받는 테마를 포착."),
    CriterionDoc("beneficiary", "간접 수혜주(리드-래그)", "통계", "중기",
        "같은 테마 대장주가 급등했는데 아직 덜 오른 종목. 단순 상관이 아니라 '시차 추종(리드-래그)' 관계로 진짜 수혜주인지 검증."),
    CriterionDoc("est_revision", "추정치 상향·서프라이즈", "이벤트", "중기",
        "애널리스트 추정치의 상향 조정 방향과 실적이 컨센서스를 상회한 직후의 표류(PEAD). 목표가의 '수준'보다 예측력이 높은 '방향' 신호."),
    CriterionDoc("target_gap", "목표가 갭", "이벤트", "중기",
        "증권사 평균 목표가 대비 현재가의 상승여력. 커버하는 애널리스트 수로 신뢰도를 가중."),
    CriterionDoc("rumor", "호재 모멘텀", "이벤트", "단기",
        "⚠️ 비정상 거래량 + 단기 모멘텀 + 뉴스/감성 급등. 검증되지 않은 고위험 신호라 가중치를 낮추고 고위험 배지를 강제합니다."),
    CriterionDoc("insider", "내부자 군집매수", "이벤트", "중기",
        "임원·5% 대량보유자의 군집 매수. 내부자의 확신이 반영된 신호(국장: DART 대량보유, 미장: SEC Form4)."),
    CriterionDoc("fscore", "퀄리티(F-Score)", "품질", "장기",
        "Piotroski F-Score(0~9). 수익성·재무건전성·영업효율 9개 항목을 점수화해, 싸 보이지만 망가지는 '밸류 트랩'을 걸러냅니다."),
    CriterionDoc("fcf_yield", "FCF 수익률", "품질", "장기",
        "잉여현금흐름/기업가치. 회계 조정이 어려운 현금흐름 기반이라 PER보다 신뢰도 높은 밸류 신호."),
    CriterionDoc("roic", "자본효율(ROIC)", "품질", "장기",
        "투하자본이익률(ROIC)이 자본비용(WACC)을 초과하는지. 부채 레버리지로 부풀려지는 ROE와 달리 진짜 가치 창출을 봅니다."),
    CriterionDoc("accruals", "발생액 품질", "품질", "장기",
        "이익 중 현금이 아닌 발생액 비중. 높으면 이후 수익률이 낮은 경향(Sloan 이상현상). '이익은 좋은데 현금이 안 따라오는' 종목을 거릅니다."),
    CriterionDoc("undervalued", "저평가 우량주", "가치", "장기",
        "업종 평균 대비 PER/PBR 할인 + 수익성(ROE·영업이익률) - 부채 페널티."),
    CriterionDoc("earnings", "꾸준한 실적 성장", "가치", "장기",
        "연속으로 매출·영업이익이 동반 증가하는 분기 수 + YoY 성장률."),
    CriterionDoc("governance", "지배구조·주주환원", "정성", "중기",
        "총주주환원율(배당+자사주 소각)·밸류업. 같은 펀더멘털이라도 주주환원이 밸류에이션을 가르는 코리아 디스카운트 해소의 직접 트리거."),
    CriterionDoc("blog", "신뢰 소스 언급", "정성", "중기",
        "신뢰도 있는 투자 소스의 최근 언급 빈도·다양성·최신성."),
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HelpScreen(onBack: () -> Unit) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("추천 기준·논리", fontWeight = FontWeight.Bold) },
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
        Column(
            Modifier.padding(pad).fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(16.dp)
        ) {
            // 파이프라인 설명
            Card(
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(containerColor = Primary),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(Modifier.padding(18.dp)) {
                    Text("추천은 어떻게 만들어지나요?", fontSize = 16.sp,
                        fontWeight = FontWeight.Bold, color = Color.White)
                    Spacer(Modifier.height(10.dp))
                    listOf(
                        "① 배제 필터" to "부도위험(Altman Z)·재무 적신호 종목을 먼저 제외 — 큰 손실 회피",
                        "② 횡단면 정규화" to "각 팩터 점수를 시장 내 백분위로 변환 — 단위 다른 지표를 공정하게 결합",
                        "③ 가중 결합" to "16개 팩터의 가중 합으로 종합점수 산출",
                        "④ 리스크 조정" to "변동성이 낮은 종목에 가점(저변동성 이상현상)",
                        "⑤ 다양성 선정" to "한 기준에 쏠리지 않게 시장별 TOP 5 선정",
                    ).forEach { (t, d) ->
                        Row(Modifier.padding(vertical = 4.dp)) {
                            Text(t, fontSize = 13.sp, fontWeight = FontWeight.Bold,
                                color = Color.White, modifier = Modifier.width(96.dp))
                            Text(d, fontSize = 12.sp, color = Color.White.copy(alpha = 0.9f),
                                lineHeight = 17.sp)
                        }
                    }
                }
            }

            Spacer(Modifier.height(16.dp))
            Text("🎯 타겟 시점", fontSize = 15.sp, fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onBackground)
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                HorizonChip("⚡ 단기", "1~2주", HorizonShort)
                HorizonChip("📈 중기", "3개월 내", HorizonMid)
                HorizonChip("🏆 장기", "1년 이상", HorizonLong)
            }

            Spacer(Modifier.height(20.dp))
            Text("📚 16개 평가 기준", fontSize = 15.sp, fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onBackground)
            Spacer(Modifier.height(8.dp))

            var lastGroup = ""
            DOCS.forEach { doc ->
                if (doc.group != lastGroup) {
                    lastGroup = doc.group
                    Spacer(Modifier.height(8.dp))
                    Text("· ${doc.group}", fontSize = 13.sp, fontWeight = FontWeight.Bold,
                        color = Primary, modifier = Modifier.padding(vertical = 4.dp))
                }
                CriterionDocCard(doc)
                Spacer(Modifier.height(8.dp))
            }

            Spacer(Modifier.height(12.dp))
            Card(
                shape = RoundedCornerShape(12.dp),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.surfaceVariant)
            ) {
                Text(
                    "⚠ 이 추천은 정보 제공 목적이며 수익을 보장하지 않습니다. 모든 투자 판단과 책임은 투자자 본인에게 있습니다.",
                    fontSize = 11.sp, lineHeight = 17.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
                    modifier = Modifier.padding(14.dp)
                )
            }
            Spacer(Modifier.height(20.dp))
        }
    }
}

@Composable
private fun HorizonChip(label: String, sub: String, color: Color) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier.clip(RoundedCornerShape(12.dp))
            .background(color.copy(alpha = 0.12f)).padding(horizontal = 14.dp, vertical = 8.dp)
    ) {
        Text(label, fontSize = 13.sp, fontWeight = FontWeight.Bold, color = color)
        Text(sub, fontSize = 10.sp, color = color.copy(alpha = 0.85f))
    }
}

@Composable
private fun CriterionDocCard(doc: CriterionDoc) {
    Card(
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(Modifier.padding(14.dp)) {
            Box(
                contentAlignment = Alignment.Center,
                modifier = Modifier.size(38.dp).clip(RoundedCornerShape(10.dp))
                    .background(criterionColor(doc.key).copy(alpha = 0.15f))
            ) { Text(criterionEmoji(doc.key), fontSize = 18.sp) }
            Spacer(Modifier.width(12.dp))
            Column {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(doc.label, fontSize = 14.sp, fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface)
                    Spacer(Modifier.width(6.dp))
                    SmallHorizonChip(doc.horizon)
                }
                Spacer(Modifier.height(4.dp))
                Text(doc.desc, fontSize = 12.sp, lineHeight = 18.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.75f))
            }
        }
    }
}
