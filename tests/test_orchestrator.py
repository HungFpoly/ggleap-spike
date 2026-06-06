"""Property + unit test cho Orchestrator (cô lập lỗi theo Quán)."""

from datetime import datetime, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from app.clock import UTC
from app.config import AppConfig, Venue
from app import orchestrator
from app.time_slots import TimeSlot


VENUES = [
    Venue("mvp", "MVP", "uuid-mvp", "MVP"),
    Venue("mvpbrn", "MVP Brno", "uuid-brn", "MVP Brno"),
    Venue("cyberempire", "Cyber Empire", "uuid-cyber", "Cyber Empire"),
]


class FakePage:
    def close(self):
        pass


class FakeBrowser:
    def __init__(self):
        self.opened = []

    def open_booking_page(self, slug):
        self.opened.append(slug)
        return FakePage()

    def refresh_page(self, page):
        pass


class FakeSheets:
    def __init__(self):
        self.appended = {}
        self.state = {}

    def read_state(self):
        return self.state

    def append_records(self, tab, records):
        self.appended.setdefault(tab, []).extend(records)

    def write_state(self, state):
        self.state = state


def make_config():
    return AppConfig(venues=VENUES, spreadsheet_id="x",
                     service_account_path="p", look_ahead_hours=0)


# Feature: pc-availability-tracker, Property 10: Cô lập lỗi theo Quán
# Với mọi tổ hợp ok/fail của 3 Quán, mọi Quán đều được attempt đúng 1 lần;
# lỗi 1 Quán không chặn các Quán còn lại.
@given(st.lists(st.booleans(), min_size=3, max_size=3))
@settings(max_examples=50)
def test_failure_isolation(flags):
    config = make_config()
    fail_map = {VENUES[i].name: not flags[i] for i in range(3)}
    attempted = []

    def fake_collect(client, tracker, venue, now, cfg):
        attempted.append(venue.name)
        if fail_map[venue.name]:
            raise RuntimeError("boom")
        return []  # không có record cũng được

    orig = orchestrator.collect_venue
    orchestrator.collect_venue = fake_collect
    try:
        browser = FakeBrowser()
        sheets = FakeSheets()
        new_state = orchestrator.run_cycle(config, browser, sheets)
    finally:
        orchestrator.collect_venue = orig

    # mọi Quán đều được attempt đúng 1 lần
    assert sorted(attempted) == sorted(v.name for v in VENUES)
    # state phản ánh ok/fail đúng
    for v in VENUES:
        fails = new_state[v.name]["consecutive_failures"]
        if fail_map[v.name]:
            assert fails >= 1
        else:
            assert fails == 0


def test_collect_venue_calls_correct_uuid():
    """Unit test: collect_venue gọi fetch với đúng venue."""
    config = make_config()
    start = datetime(2026, 6, 5, 17, 0, tzinfo=UTC)
    slot = TimeSlot(start, start + timedelta(hours=1), "17:00-18:00")

    calls = []

    class Client:
        def __init__(self):
            self.browser = FakeBrowser()

        def fetch_availability(self, page, venue, slot):
            calls.append(venue.center_uuid)
            return {"Rooms": []}

    from app.zone_tracker import ZoneStateTracker
    # now = 16:44 Prague để có slot hợp lệ
    now = datetime(2026, 6, 5, 16, 44, tzinfo=UTC)
    orchestrator.collect_venue(Client(), ZoneStateTracker(), VENUES[0], now, config)
    assert calls == ["uuid-mvp"]
