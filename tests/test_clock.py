"""Property test cho nhãn thời gian theo giờ Prague, độc lập múi giờ server."""

import re
from datetime import datetime, timezone, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from app.clock import PRAGUE, now_label
from app.time_slots import TimeSlotCalculator

calc = TimeSlotCalculator()

instants = st.datetimes(
    min_value=datetime(2025, 1, 1),
    max_value=datetime(2027, 12, 31),
    timezones=st.just(timezone.utc),
)

# Các offset môi trường giả lập (server có thể ở UTC, VN, US...).
env_offsets = st.sampled_from([0, 7, -8, 2, 5, -5])


# Feature: pc-availability-tracker, Property 13: Mọi nhãn thời gian theo giờ Prague, độc lập múi giờ server
# Với cùng một instant, nhãn giờ sinh ra phải luôn bằng giá trị quy đổi sang
# Europe/Prague, bất kể múi giờ môi trường được dùng để biểu diễn instant đó.
@given(instants, env_offsets, st.integers(min_value=0, max_value=4))
@settings(max_examples=100)
def test_labels_always_prague(instant_utc, offset_hours, look_ahead):
    # Cùng một instant, biểu diễn ở một múi giờ môi trường bất kỳ.
    env_tz = timezone(timedelta(hours=offset_hours))
    as_env = instant_utc.astimezone(env_tz)

    # Giá trị kỳ vọng: quy đổi instant sang Prague.
    expected_prague = instant_utc.astimezone(PRAGUE)

    # now_label phải khớp giờ Prague dù truyền vào biểu diễn ở môi trường nào.
    assert now_label(as_env) == expected_prague.strftime("%Y-%m-%d %H:%M")

    # collection_time_label cũng phải theo giờ Prague.
    label = calc.collection_time_label(as_env)
    hour12 = expected_prague.hour % 12 or 12
    suffix = "AM" if expected_prague.hour < 12 else "PM"
    assert label == f"{hour12}:{expected_prague.minute:02d}{suffix}"
