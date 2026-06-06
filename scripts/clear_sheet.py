"""Xóa sạch dữ liệu mọi tab (gồm cả _state) trong spreadsheet.

Dùng để reset trước một đợt thu thập mới. Cần env:
  GOOGLE_SPREADSHEET_ID, GOOGLE_SA_PATH
"""

import os

import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def main():
    sheet_id = os.environ["GOOGLE_SPREADSHEET_ID"]
    sa_path = os.environ.get("GOOGLE_SA_PATH", "service_account.json")
    creds = Credentials.from_service_account_file(sa_path, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss = client.open_by_key(sheet_id)
    for ws in ss.worksheets():
        ws.clear()
        print("Cleared tab:", ws.title)
    print("Done.")


if __name__ == "__main__":
    main()
