"""Quản lý vòng đời Chromium headless (Playwright) và trang booking."""

from __future__ import annotations

import logging

from app.config import AppConfig

logger = logging.getLogger("pc_tracker.browser")

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def build_launch_kwargs(config: AppConfig) -> dict:
    """Tham số launch Chromium; thêm proxy khi được bật."""
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

    def start(self) -> None:
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(**build_launch_kwargs(self.config))
        self._context = self._browser.new_context(
            user_agent=USER_AGENT,
            locale="en-US",
            viewport={"width": 1366, "height": 768},
        )
        logger.info("Đã khởi tạo Chromium (proxy=%s)", self.config.proxy.enabled)

    def open_booking_page(self, slug: str):
        """Mở trang booking của một Quán, chờ grecaptcha sẵn sàng."""
        page = self._context.new_page()
        url = f"{self.config.booking_base_url}/{slug}/search-booking"
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_function(
                "() => (window.grecaptcha && window.grecaptcha.execute) || "
                "(window.grecaptcha && window.grecaptcha.enterprise && "
                "window.grecaptcha.enterprise.execute)",
                timeout=25000,
            )
        except Exception:
            logger.warning("grecaptcha chưa sẵn sàng sau 25s cho %s (vẫn thử tiếp)", slug)
        return page

    def refresh_page(self, page) -> None:
        page.reload(wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_function(
                "() => (window.grecaptcha && window.grecaptcha.execute) || "
                "(window.grecaptcha && window.grecaptcha.enterprise && "
                "window.grecaptcha.enterprise.execute)",
                timeout=25000,
            )
        except Exception:
            pass

    def close(self) -> None:
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception as e:
            logger.warning("Lỗi khi đóng trình duyệt: %s", e)
