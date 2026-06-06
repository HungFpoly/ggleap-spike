"""Property test cho ZoneStateTracker."""

from hypothesis import given, settings
from hypothesis import strategies as st

from app.zone_tracker import ZoneStateTracker, build_display_names

uuids = st.uuids().map(str)
names = st.text(min_size=1, max_size=8)
avails = st.integers(min_value=0, max_value=99)


@st.composite
def parsed_zones(draw):
    n = draw(st.integers(min_value=0, max_value=6))
    out = []
    used = set()
    for _ in range(n):
        u = draw(uuids)
        if u in used:
            continue
        used.add(u)
        # tên = uuid để mỗi zone có tên duy nhất (Property 6 kiểm theo từng uuid;
        # việc khử trùng tên trùng nhau do Property 14 lo riêng)
        out.append((u, u, draw(avails)))
    return out


# Feature: pc-availability-tracker, Property 6: build_records sinh đúng tập bản ghi và đúng giá trị trạng thái
# Với mọi known_zones + response, sinh đúng một bản ghi cho mỗi uuid trong hợp;
# 0 -> "0", N>0 -> "N", uuid đã biết nhưng vắng mặt -> "unavailable".
@given(parsed_zones(), parsed_zones())
@settings(max_examples=100)
def test_build_records(prev_parsed, cur_parsed):
    # known từ Chu_Kỳ trước
    prev_display = build_display_names(prev_parsed)
    tracker = ZoneStateTracker({"MVP": dict(prev_display)})

    records = tracker.build_records("MVP", "2026-06-06", "5:00PM-6:00PM", "4:44PM", cur_parsed)

    present = {u: a for u, _, a in cur_parsed}
    known_uuids = set(prev_display)
    expected_uuids = known_uuids | set(present)

    assert len(records) == len(expected_uuids)
    by_zone_uuid = {}
    # map lại uuid theo tên hiển thị để kiểm giá trị
    cur_display = build_display_names(cur_parsed)
    for r in records:
        # mỗi bản ghi đúng venue/date/slot/collection
        assert r.venue == "MVP"
        assert r.date == "2026-06-06"
        assert r.available_for == "5:00PM-6:00PM"
        assert r.collection_time == "4:44PM"
        assert r.pcs_available != ""  # không bỏ trống

    # kiểm giá trị từng uuid
    for u in expected_uuids:
        if u in present:
            name = cur_display[u]
            expected_val = str(present[u])
        else:
            name = prev_display[u]
            expected_val = "unavailable"
        match = [r for r in records if r.zone == name]
        assert match, f"thiếu bản ghi cho zone {name}"
        assert match[0].pcs_available == expected_val


# Feature: pc-availability-tracker, Property 14: Khử trùng tên Zone theo RoomUuid
# Mỗi RoomUuid cho đúng 1 tên hiển thị duy nhất; khử trùng ổn định; tên duy nhất giữ nguyên.
@st.composite
def parsed_with_dups(draw):
    # tạo vài nhóm tên, mỗi nhóm có thể nhiều uuid
    out = []
    n_names = draw(st.integers(min_value=1, max_value=3))
    for _ in range(n_names):
        name = draw(names)
        k = draw(st.integers(min_value=1, max_value=3))
        for _ in range(k):
            out.append((draw(uuids), name, draw(avails)))
    # loại uuid trùng
    seen = set()
    uniq = []
    for u, nm, a in out:
        if u in seen:
            continue
        seen.add(u)
        uniq.append((u, nm, a))
    return uniq


@given(parsed_with_dups())
@settings(max_examples=100)
def test_dedup_zone_names(parsed):
    display = build_display_names(parsed)
    # mỗi uuid có đúng 1 tên
    assert set(display) == {u for u, _, _ in parsed}
    # tên hiển thị duy nhất (không 2 uuid cùng tên)
    assert len(set(display.values())) == len(display)
    # ổn định: gọi lại cho kết quả y hệt
    assert build_display_names(parsed) == display
    # tên duy nhất (chỉ 1 uuid) giữ nguyên, không thêm hậu tố "#"
    name_count = {}
    for _, nm, _ in parsed:
        name_count[nm] = name_count.get(nm, 0) + 1
    for u, nm, _ in parsed:
        if name_count[nm] == 1:
            assert display[u] == nm
