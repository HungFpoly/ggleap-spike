"""Mô hình dữ liệu cốt lõi cho PC Availability Tracker."""

from __future__ import annotations

from dataclasses import dataclass


# Thứ tự cột cố định trong Google Sheets (đã chốt với khách).
COLUMN_HEADERS = ["Date", "Collection Time", "Available For", "Zone", "PCs Available"]


@dataclass(frozen=True)
class AvailabilityRecord:
    """Một bản ghi số PC trống của một Zone tại một Khung_Giờ.

    Ánh xạ 1-1 với một hàng trong Google Sheets. Trường `venue` chỉ dùng để
    định tuyến tab, không phải là một cột.
    """

    venue: str            # tên Quán (xác định tab)
    date: str             # ngày thu thập theo giờ Prague, vd "2026-06-06"
    collection_time: str  # vd "4:44PM" (giờ địa phương Prague)
    available_for: str    # vd "5:00PM-6:00PM"
    zone: str             # tên hiển thị Zone (đã khử trùng)
    pcs_available: str    # "0".."N" hoặc "unavailable"

    def to_row(self) -> list[str]:
        """Chuyển thành một hàng Sheet theo đúng thứ tự cột."""
        return [self.date, self.collection_time, self.available_for,
                self.zone, self.pcs_available]

    @staticmethod
    def from_row(venue: str, row: list[str]) -> "AvailabilityRecord":
        """Dựng lại bản ghi từ một hàng Sheet (round-trip với to_row)."""
        return AvailabilityRecord(
            venue=venue,
            date=row[0],
            collection_time=row[1],
            available_for=row[2],
            zone=row[3],
            pcs_available=row[4],
        )
