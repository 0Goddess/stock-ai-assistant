```python
import os
import json
import requests
import pandas as pd
import yfinance as yf

from ta.trend import MACD
from datetime import datetime

# =========================
# LINE Messaging API
# =========================
LINE_TOKEN = os.getenv("LINE_TOKEN")

LINE_API = "https://api.line.me/v2/bot/message/broadcast"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {LINE_TOKEN}"
}

# =========================
# 股票名稱
# =========================
stock_names = {
    "2606": "裕民",
    "2027": "大成鋼",
    "2641": "正德",
    "2634": "漢翔",
    "3707": "漢磊",
    "6182": "合晶",
    "2605": "新興",
    "2408": "南亞科",
    "5347": "世界"
}

# =========================
# 讀取設定檔
# =========================
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

stocks = config["stocks"]

# =========================
# 發送 LINE 訊息
# =========================
def send_line(msg):

    payload = {
        "messages": [
            {
                "type": "text",
                "text": msg[:5000]
            }
        ]
    }

    response = requests.post(
        LINE_API,
        headers=headers,
        json=payload
    )

    print(response.status_code)
    print(response.text)

# =========================
# 技術分析
# =========================
def analyze_stock(stock_id):

    try:

        ticker = f"{stock_id}.TW"

        df = yf.download(
            ticker,
            period="6mo",
            progress=False,
            auto_adjust=False
        )

        if df.empty:
            return f"\n【{stock_id}】抓不到資料\n"

        if len(df) < 60:
            return f"\n【{stock_id}】資料不足\n"

        # =========================
        # 均線
        # =========================
        df["5MA"] = df["Close"].rolling(5).mean()
        df["20MA"] = df["Close"].rolling(20).mean()
        df["60MA"] = df["Close"].rolling(60).mean()

        # =========================
        # MACD
        # =========================
        macd = MACD(close=df["Close"])

        df["MACD_HIST"] = macd.macd_diff()

        latest = df.iloc[-1]

        close = float(latest["Close"])

        # =========================
        # 訊息
        # =========================
        msg = f"\n【{stock_id} {stock_names.get(stock_id,'')}】\n"

        # =========================
        # 買點條件1
        # =========================
        above_60 = (
            df["Close"].iloc[-3:] >
            df["60MA"].iloc[-3:]
        ).all()

        if above_60:
            msg += "✓ 連續3日站上60MA\n"
        else:
            msg += "✗ 尚未連3日站上60MA\n"

        # =========================
        # 買點條件2
        # =========================
        recent_high = float(
            df["High"].iloc[-20:-1].max()
        )

        if close >= recent_high:
            msg += "✓ 突破前波高點\n"
        else:
            diff = round(
                (recent_high - close) / close * 100,
                2
            )

            msg += f"✗ 距離前高差 {diff}%\n"

        # =========================
        # 買點條件3
        # =========================
        recent_low = float(
            df["Low"].iloc[-20:-1].min()
        )

        prev_low = float(
            df["Low"].iloc[-2]
        )

        if prev_low >= recent_low:
            msg += "✓ 前日未跌破前低\n"
        else:
            msg += "✗ 前日跌破前低\n"

        # =========================
        # 買點條件4
        # =========================
        if latest["MACD_HIST"] > 0:
            msg += "✓ MACD翻正\n"
        else:
            msg += "✗ MACD尚未翻正\n"

        # =========================
        # 賣點條件
        # =========================
        sell_signals = []

        bias20 = (
            close / float(latest["20MA"]) - 1
        ) * 100

        bias60 = (
            close / float(latest["60MA"]) - 1
        ) * 100

        if bias20 >= 30:
            sell_signals.append("⚠ 20MA乖離過大")

        if bias60 >= 35:
            sell_signals.append("⚠ 60MA乖離過大")

        # =========================
        # 五日漲幅
        # =========================
        five_day_change = (
            close / float(df["Close"].iloc[-6]) - 1
        ) * 100

        if (
            five_day_change > 30 and
            close < float(latest["5MA"])
        ):
            sell_signals.append("⚠ 急漲後跌破5MA")

        # =========================
        # 趨勢轉弱
        # =========================
        above20 = (
            df["Close"].iloc[-23:-3] >
            df["20MA"].iloc[-23:-3]
        ).all()

        below20 = (
            df["Close"].iloc[-3:] <
            df["20MA"].iloc[-3:]
        ).all()

        if above20 and below20:
            sell_signals.append("⚠ 連3日跌破20MA")

        # =========================
        # 顯示賣點
        # =========================
        if sell_signals:

            msg += "\n【賣點警示】\n"

            for s in sell_signals:
                msg += f"{s}\n"

        return msg

    except Exception as e:

        return f"\n【{stock_id}】分析失敗：{str(e)}\n"

# =========================
# 主程式
# =========================
all_msg = f"📊 台股監控 {datetime.now().strftime('%Y-%m-%d')}\n"

for stock in stocks:

    result = analyze_stock(stock)

    all_msg += result

# =========================
# 發送
# =========================
send_line(all_msg)
```
