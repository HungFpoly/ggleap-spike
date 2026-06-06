"""Quản lý Chromium headless (Playwright async) — một trình duyệt, nhiều tab."""

from __future__ import annotations

import logging

from app.config import AppConfig

logger = logging.getLogger("pc_tracker.browser")

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

_GRECAPTCHA_READY = (
    "() => (window.grecaptcha && window.grecaptcha.execute) || "
    "(window.grecaptcha && window.grecaptcha.enterprise && "
    "window.grecaptcha.enterprise.execute)"
)


def build_launch_kwargs(config: AppConfig) -> dict:
    """Tham số launch Chromium; thêm proxy khi được bật. (hàm thuần, dễ test)"""
    kwargs: dict = {"headless": True, "args": ["--no-sandbox"]}
    if config.proxy.enabled and config.proxy.server:
        kwargs["proxy"] = {"server": config.proxy.server}
    return kwargs


class BrowserManager:
    def __init__(self, config: AppConfig):
        self.config = config
        self._pw = None
        self._browser = None
        self._context = None

    async def start(self) -> None:
        from playwright.async_api import async_playwright
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(**build_launch_kwargs(self.config))
        self._context = await self._browser.new_context(
            user_agent=USER_AGENT,
            locale="en-US",
            viewport={"width": 1366, "height": 768},
        )
        logger.info("Đã khởi tạo Chromium (proxy=%s)", self.config.proxy.enabled)

    async def open_booking_page(self, slug: str):
        page = await self._context.new_page()
        url = f"{self.config.booking_base_url}/{slug}/search-booking"
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        try:
            await page.wait_for_function(_GRECAPTCHA_READY, timeout=25000)
        except Exception:
            logger.warning("grecaptcha chưa sẵn sàng sau 25s cho %s (vẫn thử tiếp)", slug)
        return page

    async def refresh_page(self, page) -> None:
        await page.reload(wait_until="domcontentloaded", timeout=60000)
        try:
            await page.wait_for_function(_GRECAPTCHA_READY, timeout=25000)
        except Exception:
            pass

    async def close(self) -> None:
        try:
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._pw:
                await self._pw.stop()
        except Exception as e:
            logger.warning("Lỗi khi đóng trình duyệt: %s", e)
