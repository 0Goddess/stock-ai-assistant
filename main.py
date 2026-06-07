import os
import json
import requests
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
# 上櫃股票
# =========================
two_stocks = [
    "2641",
    "3707",
    "6182",
    "5347"
]

# =========================
# 載入設定
# =========================
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

stocks = config["stocks"]

# =========================
# 發送 LINE
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

        # =========================
        # 上市 / 上櫃
        # =========================
        if stock_id in two_stocks:
            ticker = f"{stock_id}.TWO"
        else:
            ticker = f"{stock_id}.TW"

        # =========================
        # 抓資料
        # =========================
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
        # 轉 Series
        # =========================
        close_series = df["Close"].squeeze()
        high_series = df["High"].squeeze()
        low_series = df["Low"].squeeze()

        # =========================
        # 均線
        # =========================
        df["5MA"] = close_series.rolling(5).mean()
        df["20MA"] = close_series.rolling(20).mean()
        df["60MA"] = close_series.rolling(60).mean()

        # =========================
        # MACD
        # =========================
        macd = MACD(close=close_series)

        df["MACD_HIST"] = macd.macd_diff()

        # =========================
        # 最新數值
        # =========================
        close = float(close_series.iloc[-1])

        ma5 = float(df["5MA"].iloc[-1])
        ma20 = float(df["20MA"].iloc[-1])
        ma60 = float(df["60MA"].iloc[-1])

        macd_hist = float(df["MACD_HIST"].iloc[-1])

        # =========================
        # 訊息
        # =========================
        msg = f"\n【{stock_id} {stock_names.get(stock_id,'')}】\n"

        # =========================
        # 買點條件1
        # =========================
        above_60 = (
            close_series.iloc[-3:] >
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
            high_series.iloc[-20:-1].max()
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
            low_series.iloc[-20:-1].min()
        )

        prev_low = float(
            low_series.iloc[-2]
        )

        if prev_low >= recent_low:
            msg += "✓ 前日未跌破前低\n"
        else:
            msg += "✗ 前日跌破前低\n"

        # =========================
        # 買點條件4
        # =========================
        if macd_hist > 0:
            msg += "✓ MACD翻正\n"
        else:
            msg += "✗ MACD尚未翻正\n"

        # =========================
        # 賣點條件
        # =========================
        sell_signals = []

        bias20 = (
            close / ma20 - 1
        ) * 100

        bias60 = (
            close / ma60 - 1
        ) * 100

        if bias20 >= 30:
            sell_signals.append("⚠ 20MA乖離過大")

        if bias60 >= 35:
            sell_signals.append("⚠ 60MA乖離過大")

        # =========================
        # 五日漲幅
        # =========================
        five_day_change = (
            close / float(close_series.iloc[-6]) - 1
        ) * 100

        if (
            five_day_change > 30 and
            close < ma5
        ):
            sell_signals.append("⚠ 急漲後跌破5MA")

        # =========================
        # 趨勢轉弱
        # =========================
        above20 = (
            close_series.iloc[-23:-3] >
            df["20MA"].iloc[-23:-3]
        ).all()

        below20 = (
            close_series.iloc[-3:] <
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
date_str = datetime.now().strftime('%Y-%m-%d')

strong_buy = []
watch_buy = []
sell_warning = []
weak_list = []

for stock in stocks:

    result = analyze_stock(stock)

    if "分析失敗" in result:
        weak_list.append(result)
        continue

    lines = result.split("\n")

    stock_title = lines[1]

    has_60 = "✓ 連續3日站上60MA" in result
    has_macd = "✓ MACD翻正" in result

    near_high = False

    for line in lines:

        if "距離前高差" in line:

            try:

                diff = float(
                    line.split("差 ")[1]
                    .replace("%", "")
                )

                if diff <= 5:
                    near_high = True

            except:
                pass

    has_sell = "【賣點警示】" in result

    # =========================
    # 強勢買點
    # =========================
    if has_60 and has_macd and near_high:

        msg = f"{stock_title}\n"

        msg += "- 站上60MA\n"
        msg += "- MACD翻正\n"
        msg += "- 接近前高\n"

        strong_buy.append(msg)

    # =========================
    # 買點觀察
    # =========================
    elif has_60 or has_macd:

        msg = f"{stock_title}\n"

        if has_60:
            msg += "- 站上60MA\n"

        if has_macd:
            msg += "- MACD翻正\n"

        for line in lines:

            if "距離前高差" in line:
                msg += f"- {line.replace('✗ ','')}\n"

        watch_buy.append(msg)

    # =========================
    # 賣點警示
    # =========================
    if has_sell:

        msg = f"{stock_title}\n"

        capture = False

        for line in lines:

            if "【賣點警示】" in line:
                capture = True
                continue

            if capture and line.strip():
                msg += f"- {line}\n"

        sell_warning.append(msg)

    # =========================
    # 弱勢整理
    # =========================
    if not has_60 and not has_macd:

        msg = f"{stock_title}\n"

        for line in lines:

            if "✗" in line:
                msg += f"- {line.replace('✗ ','')}\n"

        weak_list.append(msg)

# =========================
# 組合訊息
# =========================
all_msg = f"📊 台股監控 {date_str}\n"

# =========================
# 強勢買點
# =========================
if strong_buy:

    all_msg += "\n====================\n"
    all_msg += "【強勢買點】\n"
    all_msg += "====================\n"

    for msg in strong_buy:
        all_msg += f"\n{msg}"

# =========================
# 買點觀察
# =========================
if watch_buy:

    all_msg += "\n====================\n"
    all_msg += "【買點觀察】\n"
    all_msg += "====================\n"

    for msg in watch_buy:
        all_msg += f"\n{msg}"

# =========================
# 賣點警示
# =========================
if sell_warning:

    all_msg += "\n====================\n"
    all_msg += "【賣點警示】\n"
    all_msg += "====================\n"

    for msg in sell_warning:
        all_msg += f"\n{msg}"

# =========================
# 弱勢整理
# =========================
if weak_list:

    all_msg += "\n====================\n"
    all_msg += "【弱勢整理】\n"
    all_msg += "====================\n"

    for msg in weak_list:
        all_msg += f"\n{msg}"

# =========================
# 發送
# =========================
send_line(all_msg)
