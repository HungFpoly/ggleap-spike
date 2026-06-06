"""Theo dõi trạng thái Zone và sinh AvailabilityRecord.

- Khóa định danh Zone = RoomUuid (duy nhất), KHÔNG dùng RoomName (có thể trùng).
- Khử trùng tên hiển thị: nhiều RoomUuid cùng RoomName -> thêm hậu tố "#1", "#2"...
  ổn định theo thứ tự RoomUuid đã sắp xếp.
- Zone đã biết (từ Chu_Kỳ trước) nhưng vắng mặt -> "unavailable".
"""

from __future__ import annotations

from app.models import AvailabilityRecord
from app.response_parser import ParsedZone


def build_display_names(parsed: list[ParsedZone]) -> dict[str, str]:
    """Map RoomUuid -> tên hiển thị đã khử trùng cho một response.

    Tên trùng nhau giữa nhiều RoomUuid sẽ được thêm hậu tố "#k" theo thứ tự
    RoomUuid sắp xếp (ổn định). Tên duy nhất giữ nguyên.
    """
    by_name: dict[str, list[str]] = {}
    for uuid, name, _ in parsed:
        by_name.setdefault(name, []).append(uuid)

    display: dict[str, str] = {}
    for name, uuids in by_name.items():
        if len(uuids) == 1:
            display[uuids[0]] = name
        else:
            for idx, uuid in enumerate(sorted(uuids), start=1):
                display[uuid] = f"{name} #{idx}"
    return display


class ZoneStateTracker:
    def __init__(self, known_zones: dict[str, dict[str, str]] | None = None):
        # {venue_name: {room_uuid: display_name}}
        self._known: dict[str, dict[str, str]] = known_zones or {}

    def known_zones(self, venue: str) -> dict[str, str]:
        return dict(self._known.get(venue, {}))

    def export_state(self) -> dict[str, dict[str, str]]:
        return {v: dict(m) for v, m in self._known.items()}

    def build_records(
        self,
        venue: str,
        date: str,
        available_for: str,
        collection_time: str,
        parsed: list[ParsedZone],
    ) -> list[AvailabilityRecord]:
        """Sinh một bản ghi cho mỗi RoomUuid trong hợp (đã biết ∪ trong response)."""
        display = build_display_names(parsed)
        present = {uuid: avail for uuid, _, avail in parsed}

        known = self._known.get(venue, {})
        # Hợp các RoomUuid đã biết và xuất hiện lần này.
        all_uuids = set(known) | set(present)

        records: list[AvailabilityRecord] = []
        for uuid in sorted(all_uuids):
            if uuid in present:
                name = display[uuid]
                pcs = str(present[uuid])
            else:
                # Vắng mặt lần này -> dùng tên hiển thị đã lưu, đánh dấu unavailable.
                name = known[uuid]
                pcs = "unavailable"
            records.append(
                AvailabilityRecord(
                    venue=venue,
                    date=date,
                    collection_time=collection_time,
                    available_for=available_for,
                    zone=name,
                    pcs_available=pcs,
                )
            )

        # Cập nhật known_zones với các Zone xuất hiện lần này (giữ tên đã khử trùng).
        merged = dict(known)
        merged.update(display)
        self._known[venue] = merged

        return records
