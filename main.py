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
    import os
    import requests
    import pandas as pd
    from datetime import datetime, timedelta
    token = os.getenv("FINMIND_TOKEN")
    url = "https://api.finmindtrade.com/api/v4/data"
    # =========================================================
    # 日期
    # =========================================================
    end_date = datetime.today().strftime("%Y-%m-%d")
    start_date = (
        datetime.today() - timedelta(days=7)
    ).strftime("%Y-%m-%d")
    # =========================================================
    # 外資
    # =========================================================
    foreign_buy = "無資料"
    try:
        res = requests.get(
            url,
            params={
                "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
                "data_id": str(stock_id),
                "start_date": start_date,
                "end_date": end_date,
                "token": token
            },
            timeout=20
        )
        js = res.json()
        df = pd.DataFrame(js.get("data", []))
        if not df.empty:
            keywords = [
                "外資及陸資",
                "外資",
                "Foreign"
            ]
            foreign_df = pd.DataFrame()
            for k in keywords:
                tmp = df[
                    df["name"].astype(str).str.contains(
                        k,
                        na=False
                    )
                ]
                if not tmp.empty:
                    foreign_df = tmp
                    break
            if not foreign_df.empty:
                foreign_df = foreign_df.sort_values(
                    "date"
                )
                latest_value = None
                for i in range(
                    len(foreign_df) - 1,
                    -1,
                    -1
                ):
                    row = foreign_df.iloc[i]
                    buy = int(
                        row.get("buy", 0)
                    )
                    sell = int(
                        row.get("sell", 0)
                    )
                    # =============================================
                    # FinMind 是股數
                    # 需轉張
                    # =============================================
                    diff = (
                        buy - sell
                    ) // 1000
                    if diff != 0:
                        latest_value = diff
                        break
                if latest_value is not None:
                    foreign_buy = (
                        f"{latest_value:+,} 張"
                    )
                else:
                    foreign_buy = "0 張"
    except Exception as e:
        print("外資錯誤:", e)
    # =========================================================
    # 借券
    # =========================================================
    borrow_balance = "無資料"
    borrow_change = "無資料"
    try:
        res = requests.get(
            url,
            params={
                "dataset": "TaiwanDailyShortSaleBalances",
                "data_id": str(stock_id),
                "start_date": start_date,
                "end_date": end_date,
                "token": token
            },
            timeout=20
        )
        js = res.json()
        df = pd.DataFrame(js.get("data", []))
        if not df.empty:
            df = df.sort_values("date")
            latest = df.iloc[-1]
            if len(df) >= 2:
                prev = df.iloc[-2]
            else:
                prev = latest
            # =============================================
            # 借券餘額
            # =============================================
            balance = int(
                latest[
                    "SBLShortSalesCurrentDayBalance"
                ]
            )
            prev_balance = int(
                prev[
                    "SBLShortSalesCurrentDayBalance"
                ]
            )
            # =============================================
            # 股 → 張
            # =============================================
            balance = balance // 1000
            prev_balance = prev_balance // 1000
            borrow_balance = (
                f"{balance:,} 張"
            )
            borrow_change = (
                f"{balance - prev_balance:+,} 張"
            )
    except Exception as e:
        print("借券錯誤:", e)
    return (
        foreign_buy,
        borrow_balance,
        borrow_change
    )
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

        # =========================================================
        # 籌碼面
        # =========================================================
        foreign_buy, borrow_balance, borrow_change = (
            get_chip_data(stock_id)
        )
        # =========================================================
        # 外資分析
        # =========================================================
        foreign_text = ""
        foreign_ratio_text = ""
        try:
            foreign_value = int(
                foreign_buy
                .replace(" 張", "")
                .replace(",", "")
            )
            volume_today = int(volume_today) // 1000
            if volume_today > 0:
                foreign_ratio = (
                    abs(foreign_value)
                    / volume_today
                ) * 100
            else:
                foreign_ratio = 0
            if foreign_value >= 1000:
                foreign_text = (
                    f"✓ 外資明顯買超："
                    f"{foreign_buy}"
                )
            elif foreign_value > 0:
                foreign_text = (
                    f"△ 外資小幅買超："
                    f"{foreign_buy}"
                )
            elif foreign_value <= -1000:
                foreign_text = (
                    f"⚠ 外資明顯賣超："
                    f"{foreign_buy}"
                )
            elif foreign_value < 0:
                foreign_text = (
                    f"△ 外資小幅賣超："
                    f"{foreign_buy}"
                )
            else:
                foreign_text = (
                    f"△ 外資無明顯方向："
                    f"{foreign_buy}"
                )
            if foreign_ratio >= 10:
                foreign_ratio_text = (
                    f"✓ 外資影響力強 "
                    f"({foreign_ratio:.1f}%)"
                )
            elif foreign_ratio >= 3:
                if foreign_value >= 0:
                    foreign_ratio_text = (
                        f"△ 外資偏多 "
                        f"({foreign_ratio:.1f}%)"
                    )
                else:
                    foreign_ratio_text = (
                        f"△ 外資偏空 "
                        f"({foreign_ratio:.1f}%)"
                    )
            else:
                foreign_ratio_text = (
                    f"△ 外資影響有限 "
                    f"({foreign_ratio:.1f}%)"
                )
        except:
            foreign_text = (
                f"外資買賣超：{foreign_buy}"
            )
        # =========================================================
        # 借券分析
        # =========================================================
        borrow_text = ""
        try:
            borrow_balance_num = int(
                borrow_balance
                .replace(" 張", "")
                .replace(",", "")
            )
            borrow_change_num = int(
                borrow_change
                .replace(" 張", "")
                .replace(",", "")
                .replace("+", "")
            )
            if borrow_balance_num > 0:
                borrow_ratio = (
                    borrow_change_num
                    / borrow_balance_num
                ) * 100
            else:
                borrow_ratio = 0
            if borrow_ratio >= 10:
                borrow_text = (
                    f"⚠ 借券賣出大增 "
                    f"({borrow_ratio:.1f}%)"
                )
            elif borrow_ratio >= 3:
                borrow_text = (
                    f"△ 借券賣出增加 "
                    f"({borrow_ratio:.1f}%)"
                )
            elif borrow_ratio <= -3:
                borrow_text = (
                    f"✓ 借券賣出減少 "
                    f"({borrow_ratio:.1f}%)"
                )
            else:
                borrow_text = (
                    f"△ 借券賣出變化正常 "
                    f"({borrow_ratio:.1f}%)"
                )
        except:
            borrow_text = "借券資料不足"
        msg += (
            f"\n【籌碼面】\n"
            f"{foreign_text}\n"
            f"{foreign_ratio_text}\n\n"
            f"借券賣出餘額：{borrow_balance}\n"
            f"借券賣出增減：{borrow_change}\n"
            f"{borrow_text}\n"
        )
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
