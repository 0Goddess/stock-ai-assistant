import os
import requests
import yfinance as yf
import pandas as pd

from ta.trend import MACD
from datetime import datetime, timedelta

# =========================================================
# 前高前低
# =========================================================
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

# =========================================================
# 籌碼面
# =========================================================
def get_chip_data(stock_id):

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

# =========================================================
# 股價資料
# =========================================================
def get_stock_price_data(stock_id):

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

        return None

    close_series = df["Close"]

    if isinstance(close_series, pd.DataFrame):

        close_series = close_series.iloc[:, 0]

    volume_series = df["Volume"]

    if isinstance(volume_series, pd.DataFrame):

        volume_series = volume_series.iloc[:, 0]

    # =========================================================
    # 均線
    # =========================================================
    df["5MA"] = close_series.rolling(5).mean()

    df["20MA"] = close_series.rolling(20).mean()

    df["60MA"] = close_series.rolling(60).mean()

    # =========================================================
    # MACD
    # =========================================================
    macd = MACD(close=close_series)

    df["MACD_HIST"] = macd.macd_diff()

    return df
