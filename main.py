import os
import json
import requests
import pandas as pd
import yfinance as yf
import pandas_ta as ta
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
# 載入股票設定
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
                "text": msg
            }
        ]
    }

    requests.post(
        LINE_API,
        headers=headers,
        json=payload
    )

# =========================
# 技術分析
# =========================
def analyze_stock(stock_id):

    ticker = f"{stock_id}.TW"

    df = yf.download(
        ticker,
        period="6mo",
        progress=False
    )

    if len(df) < 60:
        return None

    df["5MA"] = df["Close"].rolling(5).mean()
    df["20MA"] = df["Close"].rolling(20).mean()
    df["60MA"] = df["Close"].rolling(60).mean()

    macd = ta.macd(df["Close"])

    df["MACD_HIST"] = macd["MACDh_12_26_9"]

    latest = df.iloc[-1]

    close = float(latest["Close"])
    volume = int(latest["Volume"])

    results = []

    # =========================
    # 條件1
    # =========================
    above_60 = (
        df["Close"].iloc[-3:] >
        df["60MA"].iloc[-3:]
    ).all()

    if above_60:
        results.append("✓ 連3日站上60MA")
    else:
        results.append("✗ 尚未連3日站上60MA")

    # =========================
    # 條件2
    # =========================
    recent_high = df["High"].iloc[-20:-1].max()

    if close >= recent_high:
        results.append("✓ 突破前波高點")
    else:
        diff = round((recent_high - close) / close * 100, 2)
        results.append(f"✗ 距離前高差 {diff}%")

    # =========================
    # 條件3
    # =========================
    recent_low = df["Low"].iloc[-20:-1].min()

    prev_low = float(df["Low"].iloc[-2])

    if prev_low >= recent_low:
        results.append("✓ 前日未跌破前低")
    else:
        results.append("✗ 前日跌破前低")

    # =========================
    # 條件4
    # =========================
    if latest["MACD_HIST"] > 0:
        results.append("✓ MACD翻正")
    else:
        results.append("✗ MACD尚未翻正")

    # =========================
    # 賣點
    # =========================
    sell_signals = []

    bias20 = (close / latest["20MA"] - 1) * 100
    bias60 = (close / latest["60MA"] - 1) * 100

    if bias20 >= 30:
        sell_signals.append("⚠ 20MA乖離過大")

    if bias60 >= 35:
        sell_signals.append("⚠ 60MA乖離過大")

    five_day_change = (
        close / float(df["Close"].iloc[-6]) - 1
    ) * 100

    if (
        five_day_change > 30 and
        close < latest["5MA"]
    ):
        sell_signals.append("⚠ 急漲後跌破5MA")

    above20 = (
        df["Close"].iloc[-23:-3] >
        df["20MA"].iloc[-23:-3]
    ).all()

    below20 = (
        df["Close"].iloc[-3:] <
        df["20MA"].iloc[-3:]
    ).all()

    if above20 and below20:
        sell_signals.append("⚠ 趨勢轉弱")

    # =========================
    # 組訊息
    # =========================
    msg = f"\n【{stock_id} {stock_names.get(stock_id,'')}】\n"

    for r in results:
        msg += f"{r}\n"

    if sell_signals:
        msg += "\n賣點警示：\n"

        for s in sell_signals:
            msg += f"{s}\n"

    return msg

# =========================
# 主程式
# =========================
all_msg = f"📊 台股監控 {datetime.now().strftime('%Y-%m-%d')}\n"

for stock in stocks:

    try:

        result = analyze_stock(stock)

        if result:
            all_msg += result

    except Exception as e:

        all_msg += f"\n【{stock}】分析失敗\n"

send_line(all_msg)
