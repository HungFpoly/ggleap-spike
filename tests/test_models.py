"""Property test cho AvailabilityRecord."""

from hypothesis import given, settings
from hypothesis import strategies as st

from app.models import AvailabilityRecord


# pcs_available có thể là số (dạng chuỗi) hoặc "unavailable".
pcs_values = st.one_of(
    st.integers(min_value=0, max_value=999).map(str),
    st.just("unavailable"),
)

text = st.text(min_size=0, max_size=40)

records = st.builds(
    AvailabilityRecord,
    venue=text,
    collection_time=text,
    available_for=text,
    zone=text,
    pcs_available=pcs_values,
)


# Feature: pc-availability-tracker, Property 1: Round-trip bản ghi <-> hàng Sheet
# Với mọi AvailabilityRecord hợp lệ, to_row rồi from_row phải trả về bản ghi
# tương đương; hàng luôn có đúng 4 phần tử theo thứ tự cột.
@given(records)
@settings(max_examples=100)
def test_record_row_roundtrip(record):
    row = record.to_row()
    assert len(row) == 4
    assert row == [
        record.collection_time,
        record.available_for,
        record.zone,
        record.pcs_available,
    ]
    restored = AvailabilityRecord.from_row(record.venue, row)
    assert restored == record
