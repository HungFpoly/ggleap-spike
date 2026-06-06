"""Property test cho ResponseParser."""

import json

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.response_parser import ResponseParser, ParseError

room_names = st.text(min_size=1, max_size=20)
uuids = st.uuids().map(str)
avails = st.integers(min_value=0, max_value=200)


@st.composite
def rooms_payload(draw):
    n = draw(st.integers(min_value=0, max_value=8))
    rooms = []
    expected = []
    for _ in range(n):
        uuid = draw(uuids)
        name = draw(room_names)
        avail = draw(avails)
        rooms.append({"RoomUuid": uuid, "RoomName": name,
                      "PcGroups": {}, "MachinesAvailable": avail})
        expected.append((uuid, name, avail))
    return {"Rooms": rooms, "MaxMachinesToBookAtOnce": 6}, expected


# Feature: pc-availability-tracker, Property 2: Parse mọi Zone từ response hợp lệ
# Với mọi response hợp lệ, parse trả đúng đủ (RoomUuid, RoomName, MachinesAvailable),
# loại các Zone thuộc excluded_zones.
@given(rooms_payload(), st.sets(room_names, max_size=3))
@settings(max_examples=100)
def test_parse_all_zones(payload_and_expected, excluded):
    payload, expected = payload_and_expected
    result = ResponseParser.parse_rooms(payload, "MVP", "5:00-6:00", excluded)
    expected_kept = [e for e in expected if e[1] not in excluded]
    assert result == expected_kept
    # không zone nào bị loại còn sót lại
    assert all(name not in excluded for _, name, _ in result)


# Feature: pc-availability-tracker, Property 3: Lỗi parse nêu rõ ngữ cảnh
# Với mọi đầu vào không hợp lệ (không phải dict, hoặc thiếu Rooms), raise
# ParseError với message chứa tên Quán và nhãn Khung_Giờ.
bad_inputs = st.one_of(
    st.text(max_size=10),
    st.integers(),
    st.lists(st.integers()),
    st.dictionaries(st.text(max_size=5).filter(lambda k: k != "Rooms"),
                    st.integers(), max_size=3),
)


@given(bad_inputs)
@settings(max_examples=100)
def test_parse_error_context(bad):
    with pytest.raises(ParseError) as exc:
        ResponseParser.parse_rooms(bad, "Cyber Empire", "7:00-8:00")
    msg = str(exc.value)
    assert "Cyber Empire" in msg
    assert "7:00-8:00" in msg
