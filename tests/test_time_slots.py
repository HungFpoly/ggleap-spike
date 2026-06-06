"""Property + unit test cho TimeSlotCalculator."""

import re
from datetime import datetime, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from app.clock import PRAGUE, UTC
from app.time_slots import TimeSlotCalculator

calc = TimeSlotCalculator()

# datetime tz-aware ở Prague (sinh qua UTC để không tạo giờ ảo lúc đổi DST).
prague_datetimes = st.datetimes(
    min_value=datetime(2025, 1, 1),
    max_value=datetime(2027, 12, 31),
    timezones=st.just(UTC),
).map(lambda d: d.astimezone(PRAGUE))


# Feature: pc-availability-tracker, Property 4: Cấu trúc dãy Khung_Giờ
# Các slot cách đều 1 giờ, slot đầu là đầu giờ tròn, mọi start >= now + 15'.
@given(prague_datetimes, st.integers(min_value=0, max_value=12))
@settings(max_examples=100)
def test_slot_structure(now_local, look_ahead):
    slots = calc.next_hour_slots(now_local, look_ahead)
    now_floor = now_local.replace(second=0, microsecond=0)
    min_start = now_floor + timedelta(minutes=15)
    for s in slots:
        # start cách now (đã làm tròn phút) >= 15 phút (lead-time)
        assert s.start_utc >= min_start
        # start là đầu giờ tròn theo giờ Prague
        assert s.start_utc.astimezone(PRAGUE).minute == 0
    # cách đều 1 giờ
    for a, b in zip(slots, slots[1:]):
        assert b.start_utc - a.start_utc == timedelta(hours=1)


# Feature: pc-availability-tracker, Property 5: Tính hợp lệ của mỗi Khung_Giờ (DST + luật 15')
# start < end, end-start = 1h, start làm tròn mốc 15' và >= now + 15'.
dst_datetimes = st.one_of(
    prague_datetimes,
    # sinh instant UTC quanh mốc DST rồi đổi sang Prague -> luôn ra giờ thật
    st.datetimes(min_value=datetime(2026, 3, 29), max_value=datetime(2026, 3, 30, 23, 59),
                 timezones=st.just(UTC)).map(lambda d: d.astimezone(PRAGUE)),
    st.datetimes(min_value=datetime(2026, 10, 24), max_value=datetime(2026, 10, 26, 23, 59),
                 timezones=st.just(UTC)).map(lambda d: d.astimezone(PRAGUE)),
)


@given(dst_datetimes, st.integers(min_value=0, max_value=6))
@settings(max_examples=100)
def test_slot_validity_dst(now_local, look_ahead):
    slots = calc.next_hour_slots(now_local, look_ahead)
    now_floor = now_local.replace(second=0, microsecond=0)
    min_start = now_floor + timedelta(minutes=15)
    for s in slots:
        assert s.start_utc < s.end_utc
        assert s.end_utc - s.start_utc == timedelta(hours=1)
        assert s.start_utc >= min_start
        # làm tròn mốc 15 phút theo giờ Prague
        assert s.start_utc.astimezone(PRAGUE).minute % 15 == 0


# Feature: pc-availability-tracker, Property 7: Định dạng Collection Time và Available For
collection_re = re.compile(r"^\d{1,2}:\d{2}(AM|PM)$")
available_re = re.compile(r"^\d{1,2}:00(AM|PM)-\d{1,2}:00(AM|PM)$")


@given(prague_datetimes, st.integers(min_value=0, max_value=6))
@settings(max_examples=100)
def test_label_formats(now_local, look_ahead):
    assert collection_re.match(calc.collection_time_label(now_local))
    for s in calc.next_hour_slots(now_local, look_ahead):
        assert available_re.match(s.available_for)


# --- Unit test edge case ---

def test_run_at_44_includes_next_hour():
    # 16:44 -> đầu giờ kế tiếp 17:00 cách 16' (hợp lệ), phải có trong slots
    now = datetime(2026, 6, 5, 16, 44, tzinfo=PRAGUE)
    slots = calc.next_hour_slots(now, 0)
    assert len(slots) == 1
    assert slots[0].available_for == "5:00PM-6:00PM"


def test_run_at_58_skips_next_hour():
    # 16:58 -> 17:00 chỉ cách 2' < 15' -> bị loại; slot đầu tiên hợp lệ là 18:00
    now = datetime(2026, 6, 5, 16, 58, tzinfo=PRAGUE)
    slots = calc.next_hour_slots(now, 3)
    assert all(s.available_for != "5:00PM-6:00PM" for s in slots)
    assert slots[0].available_for == "6:00PM-7:00PM"


def test_round_up_to_quarter():
    base = datetime(2026, 6, 5, 16, 0, tzinfo=PRAGUE)
    assert TimeSlotCalculator.round_up_to_quarter(base.replace(minute=1)).minute == 15
    assert TimeSlotCalculator.round_up_to_quarter(base.replace(minute=15)).minute == 15
    assert TimeSlotCalculator.round_up_to_quarter(base.replace(minute=46)).hour == 17
