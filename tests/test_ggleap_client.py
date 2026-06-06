"""Property + unit test cho request builder và TTL token."""

from datetime import datetime, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from app.clock import UTC
from app.config import Venue
from app.ggleap_client import (
    build_request, token_needs_refresh, GG_CLIENT_HEADER, iso8601_utc,
)
from app.time_slots import TimeSlot


def make_slot():
    start = datetime(2026, 6, 5, 17, 0, tzinfo=UTC)
    return TimeSlot(start, start + timedelta(hours=1), "17:00-18:00")


venues = st.builds(
    Venue,
    slug=st.text(min_size=1, max_size=8),
    name=st.text(min_size=1, max_size=8),
    center_uuid=st.uuids().map(str),
    sheet_tab=st.text(min_size=1, max_size=8),
)
tokens = st.text(min_size=1, max_size=50)


# Feature: pc-availability-tracker, Property 12: Request builder luôn gắn header bắt buộc và tôn trọng TTL token
@given(venues, tokens)
@settings(max_examples=100)
def test_request_always_has_required_headers(venue, token):
    url, params, headers = build_request(
        venue, make_slot(), token, "https://api.ggleap.com/production")
    assert headers["g-recaptcha-token"] == token
    assert headers["x-gg-client"] == GG_CLIENT_HEADER
    assert params["centerUuid"] == venue.center_uuid
    assert "public_booking_available_devices" in url


@given(
    st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False),
    st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False),
    st.integers(min_value=1, max_value=600),
)
@settings(max_examples=100)
def test_token_ttl(issued, now, ttl):
    elapsed = now - issued
    assert token_needs_refresh(issued, now, ttl) == (elapsed >= ttl)


def test_iso8601_format():
    dt = datetime(2026, 6, 5, 19, 30, 0, tzinfo=UTC)
    assert iso8601_utc(dt) == "2026-06-05T19:30:00.000Z"
