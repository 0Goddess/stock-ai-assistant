import os
import json
import requests
import gspread

from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials

from config import (
    LINE_TOKEN,
    LINE_API,
    SHEET_ID
)

from analyzer import analyze_stock

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {LINE_TOKEN}"
}

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
# 主程式
# =========================
date_str = datetime.now().strftime("%Y-%m-%d")

all_msg = f"📊 台股監控 {date_str}\n"

processed_stocks = set()

for row in data:

    stock_id = str(row["股票"]).strip()

    # =========================
    # 避免重複股票
    # =========================
    if stock_id in processed_stocks:
        continue

    processed_stocks.add(stock_id)

    # =========================
    # 啟用判斷
    # =========================
    if str(row["啟用"]).upper() != "Y":
        continue

    # =========================
    # 分析股票
    # =========================
    try:

        result = analyze_stock(row)

        all_msg += result

    except Exception as e:
        all_msg += (
            f"\n【系統錯誤】\n"
            f"{stock_id} "
            f"{str(e)}\n"
        )

# =========================
# 發送 LINE
# =========================
try:

    send_line(all_msg)

except Exception as e:

    print("LINE發送失敗:", e)

