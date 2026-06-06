"""Entrypoint one-shot cho Render Cron Job (async, thu thập 3 Quán song song).

Chế độ:
  (mặc định)   chạy một Chu_Kỳ đầy đủ, ghi Google Sheets.
  --once       như mặc định (demo một Chu_Kỳ).
  --validate   chỉ kiểm tra vượt reCAPTCHA (HTTP 200) cho mỗi Quán, KHÔNG ghi Sheets.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from app.clock import now_local
from app.config import AppConfig
from app.ggleap_client import GGLeapClient
from app.time_slots import TimeSlotCalculator


def _setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)sZ | %(levelname)s | %(name)s | %(message)s",
    )


async def run_validate(config: AppConfig, browser) -> bool:
    """Fetch thử Khung_Giờ kế tiếp cho mỗi Quán (song song). Không ghi Sheets."""
    log = logging.getLogger("pc_tracker.validate")
    client = GGLeapClient(browser, config)
    calc = TimeSlotCalculator(min_lead_minutes=config.min_lead_minutes)
    slots = calc.next_hour_slots(now_local(), 0)
    if not slots:
        log.error("Không có Khung_Giờ hợp lệ để kiểm tra")
        return False
    slot = slots[0]

    async def check(venue):
        page = await browser.open_booking_page(venue.slug)
        try:
            await client.fetch_availability(page, venue, slot)
            log.info("VALIDATE %s: PASS (HTTP 200) cho %s",
                     venue.name, slot.available_for)
            return True
        except Exception as e:
            log.error("VALIDATE %s: FAIL - %s", venue.name, e)
            return False
        finally:
            await page.close()

    results = await asyncio.gather(*(check(v) for v in config.venues))
    return all(results)


async def _main_async(argv) -> int:
    mode_validate = "--validate" in argv
    config = AppConfig.from_env()
    from app.browser_manager import BrowserManager
    browser = BrowserManager(config)
    try:
        await browser.start()
        if mode_validate:
            ok = await run_validate(config, browser)
            return 0 if ok else 1
        from app.sheets_writer import SheetsWriter
        from app.orchestrator import run_cycle
        sheets = SheetsWriter(config)
        await run_cycle(config, browser, sheets)
        return 0
    except Exception:
        logging.getLogger("pc_tracker.main").exception("Lỗi nghiêm trọng")
        return 1
    finally:
        await browser.close()


def main(argv=None) -> int:
    _setup_logging()
    argv = argv if argv is not None else sys.argv[1:]
    return asyncio.run(_main_async(argv))


if __name__ == "__main__":
    sys.exit(main())
