"""Phân tích (parse) JSON response của endpoint ggleap public_booking_available_devices."""

from __future__ import annotations

from typing import Iterable


class ParseError(Exception):
    """Lỗi khi response không hợp lệ hoặc thiếu trường bắt buộc."""


# (RoomUuid, RoomName, MachinesAvailable)
ParsedZone = tuple[str, str, int]


class ResponseParser:
    @staticmethod
    def parse_rooms(
        payload: dict,
        venue: str,
        slot_label: str,
        excluded_zones: Iterable[str] = (),
    ) -> list[ParsedZone]:
        """Trích xuất (RoomUuid, RoomName, MachinesAvailable) cho mọi Zone.

        - Loại các Zone có RoomName nằm trong `excluded_zones`.
        - Raise ParseError (kèm venue + slot_label) nếu payload không hợp lệ
          hoặc thiếu trường "Rooms".
        """
        excluded = set(excluded_zones)

        if not isinstance(payload, dict):
            raise ParseError(
                f"Response không phải JSON object cho Quán '{venue}', "
                f"Khung_Giờ '{slot_label}'"
            )
        if "Rooms" not in payload:
            raise ParseError(
                f"Response thiếu trường 'Rooms' cho Quán '{venue}', "
                f"Khung_Giờ '{slot_label}'"
            )

        rooms = payload["Rooms"]
        if not isinstance(rooms, list):
            raise ParseError(
                f"Trường 'Rooms' không phải danh sách cho Quán '{venue}', "
                f"Khung_Giờ '{slot_label}'"
            )

        result: list[ParsedZone] = []
        for room in rooms:
            if not isinstance(room, dict):
                # Bỏ qua phần tử không hợp lệ thay vì làm hỏng cả Quán.
                continue
            name = room.get("RoomName")
            # Loại zone bị loại trừ TRƯỚC (vd "Room for unassigned machines" có RoomUuid=null).
            if name in excluded:
                continue
            uuid = room.get("RoomUuid")
            avail = room.get("MachinesAvailable")
            if name is None or uuid is None or avail is None:
                # Room thiếu field bắt buộc nhưng không thuộc excluded -> bỏ qua + log,
                # không raise để các zone khác vẫn thu thập được.
                import logging
                logging.getLogger("pc_tracker.parser").warning(
                    "Bỏ qua Room thiếu field (RoomName=%r, RoomUuid=%r) cho Quán "
                    "'%s', Khung_Giờ '%s'", name, uuid, venue, slot_label)
                continue
            result.append((str(uuid), str(name), int(avail)))
        return result
