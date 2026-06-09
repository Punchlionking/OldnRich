package com.oldbutrich.stockpick

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.oldbutrich.stockpick.ui.StockApp
import com.oldbutrich.stockpick.ui.theme.OldbutRichTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            OldbutRichTheme {
                StockApp()
            }
        }
    }
}
