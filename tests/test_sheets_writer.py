"""Property test cho SheetsWriter (append không ghi đè, định tuyến tab)."""

from hypothesis import given, settings
from hypothesis import strategies as st

from app.config import AppConfig
from app.models import AvailabilityRecord, COLUMN_HEADERS
from app.sheets_writer import SheetsWriter


# ---- Fake gspread ----

class FakeWorksheet:
    def __init__(self, title, rows=None):
        self.title = title
        self.rows = rows if rows is not None else [COLUMN_HEADERS]

    def row_values(self, i):
        return self.rows[i - 1] if i - 1 < len(self.rows) else []

    def append_rows(self, rows, value_input_option=None):
        self.rows.extend(rows)

    def append_row(self, row, value_input_option=None):
        self.rows.append(row)

    def insert_row(self, row, index=1, value_input_option=None):
        self.rows.insert(index - 1, row)


class FakeSpreadsheet:
    def __init__(self):
        self.worksheets_map = {}

    def worksheet(self, tab):
        if tab not in self.worksheets_map:
            raise KeyError(tab)
        return self.worksheets_map[tab]

    def add_worksheet(self, title, rows, cols):
        ws = FakeWorksheet(title, rows=[])
        self.worksheets_map[title] = ws
        return ws


class FakeClient:
    def __init__(self, ss):
        self._ss = ss

    def open_by_key(self, key):
        return self._ss


def make_writer():
    cfg = AppConfig(venues=[], spreadsheet_id="x", service_account_path="p")
    ss = FakeSpreadsheet()
    return SheetsWriter(cfg, client=FakeClient(ss)), ss


records_list = st.lists(
    st.builds(
        AvailabilityRecord,
        venue=st.just("MVP"),
        collection_time=st.text(min_size=1, max_size=8),
        available_for=st.text(min_size=1, max_size=8),
        zone=st.text(min_size=1, max_size=8),
        pcs_available=st.integers(0, 50).map(str),
    ),
    max_size=10,
)


# Feature: pc-availability-tracker, Property 8: Append không ghi đè
@given(records_list, records_list)
@settings(max_examples=100)
def test_append_does_not_overwrite(first, second):
    writer, ss = make_writer()
    writer.append_records("MVP", first)
    # tab chỉ được tạo khi có bản ghi; nếu cả hai rỗng thì không có gì để kiểm
    if "MVP" not in ss.worksheets_map:
        writer.append_records("MVP", second)
        if "MVP" not in ss.worksheets_map:
            return
    after_first = list(ss.worksheets_map["MVP"].rows)
    writer.append_records("MVP", second)
    after_second = ss.worksheets_map["MVP"].rows

    # hàng cũ giữ nguyên vị trí/nội dung
    assert after_second[:len(after_first)] == after_first
    # bản ghi mới nằm ở cuối, đúng số lượng
    assert len(after_second) == len(after_first) + len(second)
    if second:
        assert after_second[-len(second):] == [r.to_row() for r in second]


# Feature: pc-availability-tracker, Property 9: Định tuyến bản ghi đúng tab theo Quán
@given(st.dictionaries(
    st.sampled_from(["MVP", "MVP Brno", "Cyber Empire"]),
    records_list, max_size=3))
@settings(max_examples=100)
def test_route_to_correct_tab(per_venue):
    writer, ss = make_writer()
    for venue, recs in per_venue.items():
        # gán đúng venue cho từng record
        recs = [AvailabilityRecord(venue, r.collection_time, r.available_for,
                                   r.zone, r.pcs_available) for r in recs]
        writer.append_records(venue, recs)

    for venue, recs in per_venue.items():
        if venue in ss.worksheets_map:
            data_rows = [row for row in ss.worksheets_map[venue].rows
                         if row != COLUMN_HEADERS]
            # số hàng dữ liệu của tab = số record của venue đó
            assert len(data_rows) == len(recs)


def test_header_created_for_new_tab():
    writer, ss = make_writer()
    writer.append_records("MVP", [
        AvailabilityRecord("MVP", "4:44PM", "5:00-6:00", "Plant A", "3")])
    rows = ss.worksheets_map["MVP"].rows
    assert rows[0] == COLUMN_HEADERS
    assert rows[1] == ["4:44PM", "5:00-6:00", "Plant A", "3"]
