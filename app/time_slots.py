"""Tính Khung_Giờ (start/end UTC) và nhãn hiển thị theo giờ Prague.

Hai luật của API ggleap đối với `start` (đã xác minh thực tế):
  (1) start phải cách thời điểm hiện tại tối thiểu 15 phút.
  (2) start phải được làm tròn về mốc 15 phút (00/15/30/45).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.clock import PRAGUE, UTC


@dataclass(frozen=True)
class TimeSlot:
    start_utc: datetime   # tz-aware UTC
    end_utc: datetime     # tz-aware UTC, = start_utc + 1h
    available_for: str    # nhãn "5:00-6:00" theo giờ Prague


def _fmt_12h(dt: datetime) -> str:
    """Định dạng giờ 12h kiểu '4:44PM' (không zero-pad giờ), không phụ thuộc OS."""
    hour24 = dt.hour
    minute = dt.minute
    suffix = "AM" if hour24 < 12 else "PM"
    hour12 = hour24 % 12
    if hour12 == 0:
        hour12 = 12
    return f"{hour12}:{minute:02d}{suffix}"


class TimeSlotCalculator:
    def __init__(self, tz=PRAGUE, min_lead_minutes: int = 15):
        self.tz = tz
        self.min_lead_minutes = min_lead_minutes

    def collection_time_label(self, now_local: datetime) -> str:
        """Nhãn Collection Time, vd '4:44PM' theo giờ Prague."""
        return _fmt_12h(now_local.astimezone(self.tz))

    @staticmethod
    def round_up_to_quarter(dt: datetime) -> datetime:
        """Làm tròn LÊN mốc 15 phút gần nhất (00/15/30/45)."""
        dt = dt.replace(second=0, microsecond=0)
        if dt.minute % 15 == 0:
            return dt
        minute = (dt.minute // 15 + 1) * 15
        if minute >= 60:
            return dt.replace(minute=0) + timedelta(hours=1)
        return dt.replace(minute=minute)

    def next_hour_slots(self, now_local: datetime, look_ahead_hours: int) -> list[TimeSlot]:
        """Sinh Khung_Giờ kế tiếp + look_ahead_hours slot tương lai.

        Mỗi slot bắt đầu tại một đầu giờ tròn (:00) theo giờ Prague, dài đúng 1
        giờ. Chỉ giữ các slot có start cách now tối thiểu min_lead_minutes.

        Bước nhảy theo giờ được tính trên UTC để khoảng cách luôn đúng 1 giờ kể
        cả khi qua mốc đổi giờ DST (cộng timedelta trên wall-clock Prague sẽ sai
        ở giờ spring-forward/fall-back).
        """
        now_local = now_local.astimezone(self.tz)
        # Chuẩn hoá về mốc phút để lead-time tính ổn định (bỏ giây/micro-giây).
        now_floor = now_local.replace(second=0, microsecond=0)
        # Đầu giờ kế tiếp (wall-clock Prague) rồi quy về UTC làm mốc bước nhảy.
        base_local = now_floor.replace(minute=0) + timedelta(hours=1)
        base_utc = base_local.astimezone(UTC)
        min_valid_start_utc = self.round_up_to_quarter(
            now_floor + timedelta(minutes=self.min_lead_minutes)
        ).astimezone(UTC)

        slots: list[TimeSlot] = []
        for i in range(look_ahead_hours + 1):
            start_utc = base_utc + timedelta(hours=i)
            if start_utc < min_valid_start_utc:
                continue  # vi phạm lead-time -> bỏ qua để tránh HTTP 400
            end_utc = start_utc + timedelta(hours=1)
            start_local = start_utc.astimezone(self.tz)
            end_local = end_utc.astimezone(self.tz)
            label = f"{_fmt_12h(start_local)}-{_fmt_12h(end_local)}"
            slots.append(
                TimeSlot(start_utc=start_utc, end_utc=end_utc, available_for=label)
            )
        return slots
