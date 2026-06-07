import os
import json
import requests
import yfinance as yf
import pandas as pd
import gspread
from ta.trend import MACD
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
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
# Google Sheet 認證
# =========================
google_creds = json.loads(
    os.getenv("GOOGLE_CREDENTIALS")
)
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
creds = ServiceAccountCredentials.from_json_keyfile_dict(
    google_creds,
    scope
)
client = gspread.authorize(creds)
# =========================
# Google Sheet
# =========================
SHEET_ID = "1gshq5BLEC5dsB8wzvjGNbwvqkO6ETTcQEQJm3S1Q9tk"
sheet = client.open_by_key(SHEET_ID).worksheet("stocks")
data = sheet.get_all_records()
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
# 前高前低
# =========================
def get_high_low(df, start_date, mode="high"):
    if start_date and start_date != "nan":
        filtered = df[df.index >= start_date]
    else:
        filtered = df.tail(250)
    if filtered.empty:
        filtered = df.tail(250)
    if mode == "high":
        return float(
    pd.Series(filtered["High"]).max()
)
    else:
            close_series = pd.Series(df["Close"]).squeeze()
            high_series = pd.Series(df["High"]).squeeze()
            low_series = pd.Series(df["Low"]).squeeze()
            volume_series = pd.Series(df["Volume"]).squeeze()
# =========================
# 技術分析
# =========================
def analyze_stock(row):
    try:
        stock_id = str(row["股票"])
        stock_name = str(row["名稱"])
        high_date = str(row["前高起算日"]).strip()
        low_date = str(row["前低起算日"]).strip()
        # =========================
        # 上市 / 上櫃
        # =========================
        if stock_id.startswith(("2", "4", "5", "6", "7", "8", "9")):
            ticker = f"{stock_id}.TWO"
        else:
            ticker = f"{stock_id}.TW"
        # =========================
        # 抓資料
        # =========================
        df = yf.download(
            ticker,
            period="2y",
            progress=False,
            auto_adjust=False
        )
        if df.empty:
            return None
        close_series = pd.Series(df["Close"]).squeeze()
        high_series = pd.Series(df["High"]).squeeze()
        low_series = pd.Series(df["Low"]).squeeze()
        volume_series = pd.Series(df["Volume"]).squeeze()
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
        # 最新資料
        # =========================
        close = float(close_series.iloc[-1])
        ma5 = float(df["5MA"].iloc[-1])
        ma20 = float(df["20MA"].iloc[-1])
        ma60 = float(df["60MA"].iloc[-1])
        macd_today = float(df["MACD_HIST"].iloc[-1])
        macd_yesterday = float(df["MACD_HIST"].iloc[-2])
        volume_today = float(volume_series.iloc[-1])
        # =========================
        # 前高前低
        # =========================
        recent_high = get_high_low(
            df,
            high_date,
            "high"
        )
        recent_low = get_high_low(
            df,
            low_date,
            "low"
        )
        # =========================
        # 前高區間最大量
        # =========================
        if high_date and high_date != "nan":
            volume_range = df[df.index >= high_date]
        else:
            volume_range = df.tail(250)
            max_volume = float(
    pd.Series(volume_range["Volume"]).max()
)
        # =========================
        # 買點
        # =========================
        buy_reasons = []
        # 買點1
        prev_below_60 = (
            close_series.iloc[-4] <
            df["60MA"].iloc[-4]
        )
        recent_above_60 = (
            close_series.iloc[-3:] >
            df["60MA"].iloc[-3:]
        ).all()
        if prev_below_60 and recent_above_60:
            buy_reasons.append(
                "突破60MA（原低於60MA，連3日站上）"
            )
        # 買點2
        if (
            close >= recent_high and
            volume_today >= max_volume
        ):
            buy_reasons.append(
                "量價突破前高"
            )
        # 買點3
        prev_close = float(close_series.iloc[-2])
        if prev_close >= recent_low:
            buy_reasons.append(
                "前低防守成功"
            )
        # 買點4
        if (
            macd_yesterday < 0 and
            macd_today > 0
        ):
            buy_reasons.append(
                "MACD翻正"
            )
        # =========================
        # 賣點
        # =========================
        sell_reasons = []
        bias20 = (
            close / ma20 - 1
        ) * 100
        bias60 = (
            close / ma60 - 1
        ) * 100
        if bias20 >= 30:
            sell_reasons.append(
                "20MA乖離過大"
            )
        if bias60 >= 35:
            sell_reasons.append(
                "60MA乖離過大"
            )
        five_day_change = (
            close / float(close_series.iloc[-6]) - 1
        ) * 100
        if (
            five_day_change > 30 and
            close < ma5
        ):
            sell_reasons.append(
                "急漲後跌破5MA"
            )
        above20 = (
            close_series.iloc[-23:-3] >
            df["20MA"].iloc[-23:-3]
        ).all()
        below20 = (
            close_series.iloc[-3:] <
            df["20MA"].iloc[-3:]
        ).all()
        if above20 and below20:
            sell_reasons.append(
                "連3日跌破20MA"
            )
        return {
            "stock": f"{stock_id} {stock_name}",
            "buy": buy_reasons,
            "sell": sell_reasons
        }
    except Exception as e:
        return {
            "stock": stock_id,
            "buy": [],
            "sell": [f"分析失敗：{str(e)}"]
        }
# =========================
# 主程式
# =========================
buy_list = []
sell_list = []
for row in data:
    if str(row["啟用"]).upper() != "Y":
        continue
    result = analyze_stock(row)
    if result is None:
        continue
    # =========================
    # 買點
    # =========================
    if result["buy"]:
        msg = f"\n【{result['stock']}】\n"
        for reason in result["buy"]:
            msg += f"- {reason}\n"
        buy_list.append(msg)
    # =========================
    # 賣點
    # =========================
    if result["sell"]:
        msg = f"\n【{result['stock']}】\n"
        for reason in result["sell"]:
            msg += f"- {reason}\n"
        sell_list.append(msg)
# =========================
# 組合訊息
# =========================
date_str = datetime.now().strftime("%Y-%m-%d")
all_msg = f"📊 台股監控 {date_str}\n"
# =========================
# 買點觀察
# =========================
if buy_list:
    all_msg += "\n====================\n"
    all_msg += "【買點觀察】\n"
    all_msg += "====================\n"
    for msg in buy_list:
        all_msg += msg
# =========================
# 賣點警示
# =========================
if sell_list:
    all_msg += "\n====================\n"
    all_msg += "【賣點警示】\n"
    all_msg += "====================\n"
    for msg in sell_list:
        all_msg += msg
# =========================
# 發送
# =========================
send_line(all_msg)
