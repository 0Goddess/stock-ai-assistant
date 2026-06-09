import pandas as pd

from data_fetcher import (
    get_high_low,
    get_chip_data,
    get_stock_price_data
)

# =========================================================
# 技術分析
# =========================================================
def analyze_stock(row):

    try:

        stock_id = str(row["股票"]).strip()

        stock_name = str(row["名稱"]).strip()

        high_date = str(row["前高起算日"]).strip()

        low_date = str(row["前低起算日"]).strip()

        # =========================================================
        # 抓股價資料
        # =========================================================
        df = get_stock_price_data(stock_id)

        if df is None:

            return (
                f"\n====================\n"
                f"【{stock_id} {stock_name}】\n"
                f"====================\n"
                f"抓不到資料\n"
            )

        # =========================================================
        # 修正格式
        # =========================================================
        close_series = df["Close"]

        if isinstance(close_series, pd.DataFrame):

            close_series = close_series.iloc[:, 0]

        volume_series = df["Volume"]

        if isinstance(volume_series, pd.DataFrame):

            volume_series = volume_series.iloc[:, 0]

        # =========================================================
        # 最新數據
        # =========================================================
        close = float(close_series.iloc[-1])

        ma5 = float(df["5MA"].iloc[-1])

        ma20 = float(df["20MA"].iloc[-1])

        ma60 = float(df["60MA"].iloc[-1])

        macd_today = float(df["MACD_HIST"].iloc[-1])

        macd_yesterday = float(df["MACD_HIST"].iloc[-2])

        volume_today = float(volume_series.iloc[-1])

        # =========================================================
        # 前高前低
        # =========================================================
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

        # =========================================================
        # 區間最大量
        # =========================================================
        if high_date and high_date != "nan":

            volume_range = df[df.index >= high_date]

        else:

            volume_range = df.tail(250)

        volume_data = volume_range["Volume"]

        if isinstance(volume_data, pd.DataFrame):

            volume_data = volume_data.iloc[:, 0]

        max_volume = float(volume_data.max())

        # =========================================================
        # 開始訊息
        # =========================================================
        msg = f"\n====================\n"

        msg += f"【{stock_id} {stock_name}】\n"

        msg += "====================\n"

        # =========================================================
        # 買點分析
        # =========================================================
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

        # =========================================================
        # 賣點分析
        # =========================================================
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
        # 籌碼面分析
        # =========================================================
        foreign_text = ""
        foreign_ratio_text = ""

        try:
            foreign_value = int(
                foreign_buy
                .replace(" 張", "")
                .replace(",", "")
                .replace("+", "")
            )

            volume_today_lot = int(volume_today) // 1000

            if volume_today_lot > 0:
                foreign_ratio = abs(foreign_value) / volume_today_lot * 100
            else:
                foreign_ratio = 0

            if foreign_value >= 1000:
                foreign_text = f"✓ 外資明顯買超：{foreign_buy}"
            elif foreign_value > 0:
                foreign_text = f"△ 外資小幅買超：{foreign_buy}"
            elif foreign_value <= -1000:
                foreign_text = f"⚠ 外資明顯賣超：{foreign_buy}"
            elif foreign_value < 0:
                foreign_text = f"△ 外資小幅賣超：{foreign_buy}"
            else:
                foreign_text = f"△ 外資無明顯方向：{foreign_buy}"

            if foreign_ratio >= 10:
                foreign_ratio_text = f"✓ 外資影響力強（占成交量 {foreign_ratio:.1f}%）"
            elif foreign_ratio >= 3:
                if foreign_value >= 0:
                    foreign_ratio_text = f"△ 外資偏多（占成交量 {foreign_ratio:.1f}%）"
                else:
                    foreign_ratio_text = f"△ 外資偏空（占成交量 {foreign_ratio:.1f}%）"
            else:
                foreign_ratio_text = f"△ 外資影響有限（占成交量 {foreign_ratio:.1f}%）"

        except Exception:
            foreign_text = f"外資買賣超：{foreign_buy}"
            foreign_ratio_text = "外資影響力：無法計算"

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

            prev_borrow_balance = borrow_balance_num - borrow_change_num

            if prev_borrow_balance > 0:
                borrow_ratio = borrow_change_num / prev_borrow_balance * 100
            else:
                borrow_ratio = 0

            if borrow_ratio >= 10:
                borrow_text = f"⚠ 借券賣出大增（{borrow_ratio:.1f}%）"
            elif borrow_ratio >= 3:
                borrow_text = f"△ 借券賣出增加（{borrow_ratio:.1f}%）"
            elif borrow_ratio <= -3:
                borrow_text = f"✓ 借券賣出減少（{borrow_ratio:.1f}%）"
            else:
                borrow_text = f"△ 借券賣出變化正常（{borrow_ratio:.1f}%）"

        except Exception:
            borrow_text = "借券資料不足"

        msg += (
            f"\n【籌碼面】\n"
            f"{foreign_text}\n"
            f"{foreign_ratio_text}\n\n"
            f"借券賣出餘額：{borrow_balance}\n"
            f"借券賣出增減：{borrow_change}\n"
            f"{borrow_text}\n"
        )

        # =========================================================
        # AI總結
        # =========================================================
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
