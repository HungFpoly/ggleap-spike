"""Ghi dữ liệu vào Google Sheets bằng Service Account (gspread).

- 3 tab dữ liệu (1/Quán) + 1 tab _state lưu trạng thái giám sát/known_zones.
- Append không ghi đè; đảm bảo hàng header tồn tại.
- Retry tối đa max_sheets_retries lần với backoff.
"""

from __future__ import annotations

import json
import logging

from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import AppConfig
from app.models import AvailabilityRecord, COLUMN_HEADERS

logger = logging.getLogger("pc_tracker.sheets")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
STATE_TAB = "_state"
STATE_CELL = "A1"


def records_to_rows(records: list[AvailabilityRecord]) -> list[list[str]]:
    """Chuyển danh sách bản ghi thành các hàng Sheet đúng thứ tự cột."""
    return [r.to_row() for r in records]


def make_client(sa_path: str):
    import gspread
    from google.oauth2.service_account import Credentials
    creds = Credentials.from_service_account_file(sa_path, scopes=SCOPES)
    return gspread.authorize(creds)


class SheetsWriter:
    def __init__(self, config: AppConfig, client=None):
        self.config = config
        self._client = client
        self._spreadsheet = None

    def _open(self):
        if self._spreadsheet is None:
            if self._client is None:
                self._client = make_client(self.config.service_account_path)
            self._spreadsheet = self._client.open_by_key(self.config.spreadsheet_id)
        return self._spreadsheet

    def _worksheet(self, tab: str, header: bool = True):
        ss = self._open()
        try:
            ws = ss.worksheet(tab)
        except Exception:
            ws = ss.add_worksheet(title=tab, rows=1000, cols=max(4, len(COLUMN_HEADERS)))
            if header:
                ws.append_row(COLUMN_HEADERS, value_input_option="USER_ENTERED")
            return ws
        if header:
            first = ws.row_values(1)
            if first != COLUMN_HEADERS:
                ws.insert_row(COLUMN_HEADERS, index=1, value_input_option="USER_ENTERED")
        return ws

    @retry(stop=stop_after_attempt(3),
           wait=wait_exponential(multiplier=1, min=2, max=20))
    def append_records(self, tab: str, records: list[AvailabilityRecord]) -> None:
        if not records:
            return
        ws = self._worksheet(tab)
        ws.append_rows(records_to_rows(records), value_input_option="USER_ENTERED")
        logger.info("Đã ghi %d hàng vào tab '%s'", len(records), tab)

    @retry(stop=stop_after_attempt(3),
           wait=wait_exponential(multiplier=1, min=2, max=20))
    def read_state(self) -> dict:
        ws = self._worksheet(STATE_TAB, header=False)
        raw = ws.acell(STATE_CELL).value
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("State trong tab _state không phải JSON hợp lệ, dùng rỗng")
            return {}

    @retry(stop=stop_after_attempt(3),
           wait=wait_exponential(multiplier=1, min=2, max=20))
    def write_state(self, state: dict) -> None:
        ws = self._worksheet(STATE_TAB, header=False)
        ws.update_acell(STATE_CELL, json.dumps(state, ensure_ascii=False))
