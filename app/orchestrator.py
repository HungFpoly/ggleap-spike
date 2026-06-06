"""Điều phối một Chu_Kỳ thu thập cho cả 3 Quán (one-shot)."""

from __future__ import annotations

import logging
from datetime import datetime

from app.clock import now_local, now_label
from app.config import AppConfig, Venue
from app.ggleap_client import GGLeapClient
from app.monitor import Monitor
from app.response_parser import ResponseParser
from app.time_slots import TimeSlotCalculator
from app.zone_tracker import ZoneStateTracker

logger = logging.getLogger("pc_tracker.orchestrator")


def collect_venue(
    client: GGLeapClient,
    tracker: ZoneStateTracker,
    venue: Venue,
    now: datetime,
    config: AppConfig,
):
    """Thu thập tất cả Khung_Giờ cho một Quán. Trả về list AvailabilityRecord."""
    calc = TimeSlotCalculator(min_lead_minutes=config.min_lead_minutes)
    slots = calc.next_hour_slots(now, config.look_ahead_hours)
    collection_time = calc.collection_time_label(now)

    page = client.browser.open_booking_page(venue.slug)
    records = []
    try:
        for slot in slots:
            payload = client.fetch_availability(page, venue, slot)
            parsed = ResponseParser.parse_rooms(
                payload, venue.name, slot.available_for, config.excluded_zones)
            records.extend(
                tracker.build_records(
                    venue.name, slot.available_for, collection_time, parsed))
    finally:
        page.close()
    return records


def run_cycle(config: AppConfig, browser, sheets) -> dict:
    """Chạy một Chu_Kỳ: thu thập 3 Quán, ghi Sheets, cập nhật state. Trả về state mới."""
    monitor = Monitor()
    prev_state = sheets.read_state()
    tracker = ZoneStateTracker(
        {v: prev_state.get(v, {}).get("known_zones", {}) for v in
         [vn.name for vn in config.venues]})

    client = GGLeapClient(browser, config)
    now = now_local()

    for venue in config.venues:
        try:
            records = collect_venue(client, tracker, venue, now, config)
            sheets.append_records(venue.sheet_tab, records)
            monitor.record_venue_result(venue.name, ok=True)
        except Exception as e:  # cô lập lỗi theo Quán
            logger.exception("Quán %s lỗi: %s", venue.name, e)
            monitor.record_venue_result(venue.name, ok=False, error=str(e))

    new_state = monitor.build_new_state(
        prev_state, tracker.export_state(), now_label_value=now_label(now))
    sheets.write_state(new_state)
    return new_state
