"""Property + unit test cho Monitor (máy trạng thái thất bại liên tiếp)."""

from hypothesis import given, settings
from hypothesis import strategies as st

from app.monitor import Monitor


# Feature: pc-availability-tracker, Property 11: Máy trạng thái thất bại liên tiếp và thành công gần nhất
# Với mọi chuỗi kết quả ok/fail của một Quán: consecutive_failures tăng 1 khi
# fail / reset 0 khi ok; last_success phản ánh lần thành công gần nhất.
@given(st.lists(st.booleans(), min_size=1, max_size=30))
@settings(max_examples=100)
def test_consecutive_failures_state_machine(results):
    venue = "MVP"
    state = {}
    expected_fails = 0
    expected_last = None
    for i, ok in enumerate(results):
        label = f"2026-06-05 {i:02d}:44"
        mon = Monitor()
        mon.record_venue_result(venue, ok=ok)
        state = mon.build_new_state(state, {venue: {}}, now_label_value=label)

        if ok:
            expected_fails = 0
            expected_last = label
        else:
            expected_fails += 1
        assert state[venue]["consecutive_failures"] == expected_fails
        assert state[venue]["last_success"] == expected_last


def test_warning_after_two_failures(caplog):
    import logging
    venue = "Cyber Empire"
    state = {}
    with caplog.at_level(logging.WARNING):
        # fail lần 1
        m1 = Monitor(); m1.record_venue_result(venue, ok=False, error="x")
        state = m1.build_new_state(state, {venue: {}}, now_label_value="t1")
        # fail lần 2 -> phải có WARNING
        m2 = Monitor(); m2.record_venue_result(venue, ok=False, error="x")
        state = m2.build_new_state(state, {venue: {}}, now_label_value="t2")
    assert state[venue]["consecutive_failures"] == 2
    assert any("liên tiếp" in r.message for r in caplog.records)
