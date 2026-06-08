import os
import json
import requests
import yfinance as yf
import pandas as pd
import gspread

from ta.trend import MACD
from datetime import datetime, timedelta
from oauth2client.service_account import ServiceAccountCredentials

# =========================
# LINE
# =========================
LINE_TOKEN = os.getenv("LINE_TOKEN")

LINE_API = "https://api.line.me/v2/bot/message/broadcast"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {LINE_TOKEN}"
}

# =========================
# FinMind Token
# =========================
FINMIND_TOKEN = os.getenv("FINMIND_TOKEN")
print("FINMIND_TOKEN =", FINMIND_TOKEN)

# =========================
# Google Sheet
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

SHEET_ID = "1gshq5BLEC5dsB8wzvjGNbwvqkO6ETTcQEQJm3S1Q9tk"

sheet = client.open_by_key(SHEET_ID).worksheet("stocks")

data = sheet.get_all_records()

# =========================
# LINE 發送
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

        data = filtered["High"]

        if isinstance(data, pd.DataFrame):
            data = data.iloc[:, 0]

        return float(data.max())

    else:

        data = filtered["Low"]

        if isinstance(data, pd.DataFrame):
            data = data.iloc[:, 0]

        return float(data.min())

# =========================
# 籌碼面
# =========================
def get_chip_data(stock_id):

    try:
        token = os.getenv("FINMIND_TOKEN")

        if not token:
            print("❌ FINMIND_TOKEN 不存在")
            return "無資料", "無資料", "無資料"

        today = datetime.today()
        start_date = (today - timedelta(days=10)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")

        url = "https://api.finmindtrade.com/api/v4/data"

        # =========================================================
        # 外資（改用「穩定日統計法」避免爆炸）
        # =========================================================
        res = requests.get(url, params={
            "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
            "data_id": stock_id,
            "start_date": start_date,
            "end_date": end_date,
            "token": token
        })

        js = res.json()
        df = pd.DataFrame(js.get("data", []))

        foreign_buy = "無資料"

        if not df.empty:

            # ⚠️ 不做 name filter（關鍵）
            daily = df.groupby("date").apply(
                lambda x: x["buy"].sum() - x["sell"].sum()
            )

            foreign_buy = f"{int(daily.iloc[-1]):+,} 張"

        # =========================================================
        # 借券（改用「最穩 dataset fallback」）
        # =========================================================
        borrow_res = requests.get(url, params={
            "dataset": "TaiwanStockMarginPurchaseShortSale",
            "data_id": stock_id,
            "start_date": start_date,
            "end_date": end_date,
            "token": token
        })

        bjs = borrow_res.json()
        bdf = pd.DataFrame(bjs.get("data", []))

        borrow_balance = "無資料"
        borrow_change = "無資料"

        if not bdf.empty:

            bdf = bdf.sort_values("date")

            col = "short_sale_balance" if "short_sale_balance" in bdf.columns else None

            if col:

                latest = bdf.iloc[-1]

                balance = int(latest[col])

                if len(bdf) >= 2:
                    prev = bdf.iloc[-2]
                    change = balance - int(prev[col])
                else:
                    change = 0

                borrow_balance = f"{balance:,} 張"
                borrow_change = f"{change:+,} 張"

        return foreign_buy, borrow_balance, borrow_change

    except Exception as e:

        print("❌ 籌碼錯誤:", e)

        return "無資料", "無資料", "無資料"
# =========================
# 技術分析
# =========================
def analyze_stock(row):

    try:

        stock_id = str(row["股票"]).strip()
        stock_name = str(row["名稱"]).strip()

        high_date = str(row["前高起算日"]).strip()
        low_date = str(row["前低起算日"]).strip()

        # =========================
        # 自動判斷上市 / 上櫃
        # =========================
        ticker_tw = f"{stock_id}.TW"
        ticker_two = f"{stock_id}.TWO"

        df = yf.download(
            ticker_tw,
            period="2y",
            progress=False,
            auto_adjust=False
        )

        if df.empty:

            df = yf.download(
                ticker_two,
                period="2y",
                progress=False,
                auto_adjust=False
            )

        if df.empty:

            return (
                f"\n====================\n"
                f"【{stock_id} {stock_name}】\n"
                f"====================\n"
                f"抓不到資料\n"
            )

        # =========================
        # 修正格式
        # =========================
        close_series = df["Close"]

        if isinstance(close_series, pd.DataFrame):
            close_series = close_series.iloc[:, 0]

        volume_series = df["Volume"]

        if isinstance(volume_series, pd.DataFrame):
            volume_series = volume_series.iloc[:, 0]

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
        # 最新數據
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
        # 區間最大量
        # =========================
        if high_date and high_date != "nan":

            volume_range = df[df.index >= high_date]

        else:

            volume_range = df.tail(250)

        volume_data = volume_range["Volume"]

        if isinstance(volume_data, pd.DataFrame):
            volume_data = volume_data.iloc[:, 0]

        max_volume = float(volume_data.max())

        # =========================
        # 開始訊息
        # =========================
        msg = f"\n====================\n"
        msg += f"【{stock_id} {stock_name}】\n"
        msg += "====================\n"

        # =========================
        # 買點分析
        # =========================
        msg += "\n【買點分析】\n"

        prev_below_60 = (
            close_series.iloc[-4] <
            df["60MA"].iloc[-4]
        )

        recent_above_60 = (
            close_series.iloc[-3:] >
            df["60MA"].iloc[-3:]
        ).all()

        if prev_below_60 and recent_above_60:

            msg += "✓ 突破60MA（連3日站上）\n"

        else:

            msg += "✗ 尚未完成60MA突破\n"

        if (
            close >= recent_high and
            volume_today >= max_volume
        ):

            msg += "✓ 量價突破前高\n"

        else:

            high_gap = (
                (recent_high - close)
                / recent_high
            ) * 100

            msg += (
                f"✗ 未突破前高 "
                f"(差 {high_gap:.2f}%)\n"
            )

        prev_close = float(close_series.iloc[-2])

        if (
            prev_close <= recent_low * 1.02 and
            close > recent_low
        ):

            msg += "✓ 前低反彈\n"

        else:

            msg += "✗ 尚未接近前低\n"

        if (
            macd_yesterday < 0 and
            macd_today > 0
        ):

            msg += "✓ MACD翻正\n"

        else:

            msg += (
                f"✗ MACD未翻正 "
                f"({macd_today:.2f})\n"
            )

        # =========================
        # 賣點分析
        # =========================
        msg += "\n【賣點分析】\n"

        bias20 = (
            close / ma20 - 1
        ) * 100

        bias60 = (
            close / ma60 - 1
        ) * 100

        if bias20 >= 30:

            msg += (
                f"⚠ 20MA乖離過大 "
                f"({bias20:.2f}%)\n"
            )

        else:

            msg += (
                f"✓ 20MA乖離正常 "
                f"({bias20:.2f}%)\n"
            )

        if bias60 >= 35:

            msg += (
                f"⚠ 60MA乖離過大 "
                f"({bias60:.2f}%)\n"
            )

        else:

            msg += (
                f"✓ 60MA乖離正常 "
                f"({bias60:.2f}%)\n"
            )

        five_day_change = (
            close / float(close_series.iloc[-6]) - 1
        ) * 100

        if (
            five_day_change > 30 and
            close < ma5
        ):

            msg += "⚠ 急漲後跌破5MA\n"

        else:

            msg += (
                f"✓ 5日漲幅 "
                f"{five_day_change:.2f}%\n"
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

            msg += "⚠ 連3日跌破20MA\n"

        else:

            msg += "✓ 尚未跌破20MA\n"

        if (
            macd_yesterday > 0 and
            macd_today < 0
        ):

            msg += "⚠ MACD轉負\n"

        else:

            msg += (
                f"✓ MACD維持 "
                f"({macd_today:.2f})\n"
            )

        # =========================
        # 籌碼面
        # =========================
        msg += "\n【籌碼面】\n"

        foreign_buy, borrow_balance, borrow_change = get_chip_data(stock_id)

        msg += f"外資買賣超：{foreign_buy}\n"
        msg += f"借券餘額：{borrow_balance}\n"
        msg += f"借券增減：{borrow_change}\n"

        # =========================
        # AI總結
        # =========================
        msg += "\n【總結】\n"

        if (
            prev_below_60 and recent_above_60 and
            macd_yesterday < 0 and
            macd_today > 0
        ):

            msg += (
                "短線轉強，\n"
                "可觀察是否續攻前高。\n"
            )

        elif (
            close >= recent_high * 0.95
        ):

            msg += (
                "接近關鍵前高，\n"
                "若量能放大，\n"
                "有機會突破。\n"
            )

        elif (
            bias20 >= 30 or
            bias60 >= 35
        ):

            msg += (
                "短線乖離偏大，\n"
                "留意獲利了結賣壓。\n"
            )

        elif (
            (macd_yesterday > 0 and macd_today < 0)
            or
            (above20 and below20)
        ):

            msg += (
                "技術面轉弱，\n"
                "留意後續修正風險。\n"
            )

        else:

            msg += (
                "目前仍處整理階段，\n"
                "建議持續觀察。\n"
            )

        return msg

    except Exception as e:

        return (
            f"\n====================\n"
            f"【{stock_id} {stock_name}】\n"
            f"====================\n"
            f"分析失敗：{str(e)}\n"
        )

# =========================
# 主程式
# =========================
date_str = datetime.now().strftime("%Y-%m-%d")

all_msg = f"📊 台股監控 {date_str}\n"

for row in data:

    if str(row["啟用"]).upper() != "Y":
        continue

    result = analyze_stock(row)

    all_msg += result

# =========================
# 發送 LINE
# =========================
send_line(all_msg)
