"""Giám sát qua nhật ký: trạng thái thành công/thất bại, thất bại liên tiếp."""

from __future__ import annotations

import logging

from app.clock import now_label

logger = logging.getLogger("pc_tracker.monitor")


class Monitor:
    """Theo dõi kết quả từng Quán trong một Chu_Kỳ và tính trạng thái bền vững.

    State có dạng (lưu ở tab _state của Google Sheet):
      {venue: {"last_success": str|None,
               "consecutive_failures": int,
               "known_zones": {room_uuid: display_name}}}
    """

    def __init__(self):
        self._results: dict[str, dict] = {}  # venue -> {ok, error, slot}

    def record_venue_result(self, venue: str, ok: bool,
                            slot_label: str | None = None,
                            error: str | None = None) -> None:
        self._results[venue] = {"ok": ok, "slot": slot_label, "error": error}
        if ok:
            logger.info("Quán %s: thu thập THÀNH CÔNG", venue)
        else:
            logger.error("Quán %s: thu thập THẤT BẠI (Khung_Giờ=%s): %s",
                         venue, slot_label, error)

    def build_new_state(
        self,
        prev_state: dict,
        known_zones: dict[str, dict[str, str]],
        now_label_value: str | None = None,
    ) -> dict:
        """Tính state mới từ prev_state + kết quả Chu_Kỳ hiện tại.

        - consecutive_failures tăng 1 khi fail, reset 0 khi ok.
        - last_success = giờ Prague hiện tại nếu ok, giữ giá trị cũ nếu fail.
        - Phát log WARNING khi một Quán fail >= 2 Chu_Kỳ liên tiếp.
        """
        label = now_label_value if now_label_value is not None else now_label()
        new_state: dict = {}
        for venue, res in self._results.items():
            prev = prev_state.get(venue, {})
            ok = res["ok"]
            fails = 0 if ok else int(prev.get("consecutive_failures", 0)) + 1
            if fails >= 2:
                logger.warning("Quán %s thất bại %d Chu_Kỳ liên tiếp", venue, fails)
            new_state[venue] = {
                "last_success": label if ok else prev.get("last_success"),
                "consecutive_failures": fails,
                "known_zones": known_zones.get(venue, prev.get("known_zones", {})),
            }
        return new_state

    def last_success(self, state: dict, venue: str) -> str | None:
        return state.get(venue, {}).get("last_success")
