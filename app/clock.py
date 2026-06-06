"""Nguồn thời gian DUY NHẤT cho mọi nhãn dữ liệu/trạng thái — luôn theo giờ Prague.

CẢNH BÁO: không bao giờ dùng datetime.now() trần hay datetime.utcnow() để sinh
nhãn hiển thị cho khách. Server chạy ở UTC (Render) hoặc giờ VN (dev) — phải quy
đổi về Europe/Prague.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

PRAGUE = ZoneInfo("Europe/Prague")
UTC = ZoneInfo("UTC")


def now_local() -> datetime:
    """Thời điểm hiện tại, tz-aware theo giờ Prague."""
    return datetime.now(PRAGUE)


def now_label(now: datetime | None = None) -> str:
    """Nhãn 'YYYY-MM-DD HH:MM' theo giờ Prague (dùng cho last_success)."""
    dt = now if now is not None else now_local()
    return dt.astimezone(PRAGUE).strftime("%Y-%m-%d %H:%M")


def date_label(now: datetime | None = None) -> str:
    """Nhãn ngày 'YYYY-MM-DD' theo giờ Prague (ngày thu thập)."""
    dt = now if now is not None else now_local()
    return dt.astimezone(PRAGUE).strftime("%Y-%m-%d")
