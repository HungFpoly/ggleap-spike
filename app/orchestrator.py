"""Điều phối một Chu_Kỳ thu thập cho cả 3 Quán SONG SONG (async, one-shot)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from app.clock import now_local, now_label
from app.config import AppConfig, Venue
from app.ggleap_client import GGLeapClient, ValidationError
from app.monitor import Monitor
from app.response_parser import ResponseParser
from app.time_slots import TimeSlotCalculator
from app.zone_tracker import ZoneStateTracker

logger = logging.getLogger("pc_tracker.orchestrator")


async def collect_venue(
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

    page = await client.browser.open_booking_page(venue.slug)
    records = []
    try:
        for slot in slots:
            try:
                payload = await client.fetch_availability(page, venue, slot)
            except ValidationError as e:
                logger.warning("Bỏ qua %s %s: %s", venue.name, slot.available_for, e)
                continue
            parsed = ResponseParser.parse_rooms(
                payload, venue.name, slot.available_for, config.excluded_zones)
            records.extend(
                tracker.build_records(
                    venue.name, slot.available_for, collection_time, parsed))
    finally:
        await page.close()
    return records


async def run_cycle(config: AppConfig, browser, sheets) -> dict:
    """Chạy một Chu_Kỳ: thu thập 3 Quán SONG SONG, ghi Sheets, cập nhật state."""
    monitor = Monitor()
    prev_state = await asyncio.to_thread(sheets.read_state)
    tracker = ZoneStateTracker(
        {v.name: prev_state.get(v.name, {}).get("known_zones", {})
         for v in config.venues})

    client = GGLeapClient(browser, config)
    now = now_local()

    # Thu thập cả 3 Quán đồng thời (mỗi Quán một tab Chromium).
    async def one(venue: Venue):
        try:
            records = await collect_venue(client, tracker, venue, now, config)
            return venue, records, None
        except Exception as e:  # cô lập lỗi theo Quán
            logger.exception("Quán %s lỗi: %s", venue.name, e)
            return venue, None, e

    results = await asyncio.gather(*(one(v) for v in config.venues))

    # Ghi Sheets tuần tự (gspread đồng bộ) sau khi đã thu thập xong.
    for venue, records, err in results:
        if err is None:
            await asyncio.to_thread(sheets.append_records, venue.sheet_tab, records)
            monitor.record_venue_result(venue.name, ok=True)
        else:
            monitor.record_venue_result(venue.name, ok=False, error=str(err))

    new_state = monitor.build_new_state(
        prev_state, tracker.export_state(), now_label_value=now_label(now))
    await asyncio.to_thread(sheets.write_state, new_state)
    return new_state
