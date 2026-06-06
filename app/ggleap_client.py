"""Client gọi endpoint ggleap public_booking_available_devices qua Playwright.

Cơ chế đã xác minh thực tế (spike):
  - reCAPTCHA Enterprise: grecaptcha.enterprise.execute(siteKey, {action:"submit"})
  - siteKey dùng chung 3 Quán; in-page fetch (chạy fetch trong trang) là phương án chính.
  - Header bắt buộc: g-recaptcha-token, x-gg-client. Origin/Referer do trình duyệt tự gắn.
  - start phải >= 15 phút và làm tròn mốc 15 phút (TimeSlotCalculator đã lo).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from urllib.parse import urlencode

from app.config import AppConfig, Venue
from app.time_slots import TimeSlot

logger = logging.getLogger("pc_tracker.ggleap")

GG_CLIENT_HEADER = "DynamicCenterPagesWeb 0.1"


class FetchError(Exception):
    pass


class GeoBlockError(Exception):
    pass


class ValidationError(Exception):
    """API trả 400 do tham số (vd start vi phạm luật 15 phút)."""


def iso8601_utc(dt: datetime) -> str:
    """Định dạng đúng như site dùng: 2026-06-05T19:30:00.000Z."""
    return dt.astimezone().strftime("%Y-%m-%dT%H:%M:%S.000Z") if dt.tzinfo is None \
        else dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def build_request(venue: Venue, slot: TimeSlot, token: str,
                  api_base_url: str) -> tuple[str, dict, dict]:
    """Dựng (url, params, headers) cho một request.

    Luôn gắn header bắt buộc g-recaptcha-token và x-gg-client.
    """
    url = f"{api_base_url}/public_booking_available_devices"
    params = {
        "centerUuid": venue.center_uuid,
        "start": iso8601_utc(slot.start_utc),
        "end": iso8601_utc(slot.end_utc),
    }
    headers = {
        "g-recaptcha-token": token,
        "x-gg-client": GG_CLIENT_HEADER,
        "accept": "application/json, text/plain, */*",
    }
    return url, params, headers


def token_needs_refresh(issued_at: float, now: float, ttl_seconds: int) -> bool:
    """True nếu token đã quá hạn TTL và cần sinh lại trước khi dùng."""
    return (now - issued_at) >= ttl_seconds


# --- JS chạy trong ngữ cảnh trang ---

JS_GET_TOKEN = r"""
async ({siteKey, action}) => {
  const gre = (window.grecaptcha && window.grecaptcha.enterprise)
    ? window.grecaptcha.enterprise : window.grecaptcha;
  if (!gre || !gre.execute) return {ok:false, error:'grecaptcha(.enterprise) không khả dụng'};
  if (gre.ready) await new Promise(r => gre.ready(r));
  try { return {ok:true, token: await gre.execute(siteKey, {action})}; }
  catch (e) { return {ok:false, error:String(e)}; }
}
"""

JS_FETCH = r"""
async ({url, headers}) => {
  try {
    const r = await fetch(url, {headers});
    const body = await r.text();
    return {status: r.status, body: body,
            country: r.headers.get('x-country-code')};
  } catch (e) {
    return {status: -1, body: String(e), country: null};
  }
}
"""


class GGLeapClient:
    def __init__(self, browser, config: AppConfig):
        self.browser = browser
        self.config = config

    async def _get_token(self, page) -> str:
        res = await page.evaluate(JS_GET_TOKEN, {
            "siteKey": self.config.site_key,
            "action": self.config.recaptcha_action,
        })
        if not res.get("ok"):
            raise FetchError(f"Không lấy được token: {res.get('error')}")
        return res["token"]

    async def fetch_availability(self, page, venue: Venue, slot: TimeSlot) -> dict:
        """In-page fetch cho một Khung_Giờ. Trả về JSON đã parse (dict).

        Xử lý: 200 -> trả JSON; 400 -> ValidationError; 403 -> refresh token +
        thử lại; 5xx/network -> backoff retry; geo-block -> GeoBlockError.
        """
        import asyncio
        last_status = None
        for attempt in range(self.config.max_api_retries):
            token = await self._get_token(page)
            url, params, headers = build_request(
                venue, slot, token, self.config.api_base_url)
            full_url = f"{url}?{urlencode(params)}"
            res = await page.evaluate(JS_FETCH, {"url": full_url, "headers": headers})
            status = res.get("status")
            last_status = status

            if status == 200:
                return json.loads(res["body"])
            if status == 400:
                raise ValidationError(
                    f"{venue.name} {slot.available_for}: HTTP 400 {res.get('body')[:200]}")
            if status == 403:
                logger.warning("%s %s: HTTP 403, làm mới token và thử lại",
                               venue.name, slot.available_for)
                await self.browser.refresh_page(page)
                continue
            if status is not None and 500 <= status < 600:
                await asyncio.sleep(2 ** attempt)
                continue
            logger.warning("%s %s: HTTP %s (thử lại)", venue.name,
                           slot.available_for, status)
            await asyncio.sleep(2 ** attempt)

        raise FetchError(
            f"{venue.name} {slot.available_for}: thất bại sau "
            f"{self.config.max_api_retries} lần (status cuối={last_status})")
