"""Cấu hình hệ thống, nạp từ biến môi trường (tách biệt mã lõi)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Venue:
    slug: str
    name: str
    center_uuid: str
    sheet_tab: str
    timezone: str = "Europe/Prague"


@dataclass(frozen=True)
class ProxyConfig:
    enabled: bool = False
    server: Optional[str] = None


# 3 Quán mặc định (đã xác minh qua spike).
DEFAULT_VENUES = [
    Venue("mvp", "MVP", "f71515f0-3c74-46d7-9a92-6bd582c9b966", "MVP"),
    Venue("mvpbrn", "MVP Brno", "222b2b2c-e92e-412b-9180-5702652c11a7", "MVP Brno"),
    Venue("cyberempire", "Cyber Empire", "8e75d6f4-4e81-427c-9b40-3161d2664798", "Cyber Empire"),
]

DEFAULT_EXCLUDED_ZONES = frozenset({"Room for unassigned machines"})

SITE_KEY = "6Lf-QoooAAAAAMemhOboOzrh8frERUxfXlgFUUOz"
RECAPTCHA_ACTION = "submit"


@dataclass(frozen=True)
class AppConfig:
    venues: list[Venue]
    spreadsheet_id: str
    service_account_path: str
    look_ahead_hours: int = 8
    excluded_zones: frozenset[str] = DEFAULT_EXCLUDED_ZONES
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    booking_base_url: str = "https://centers.ggcircuit.com"
    api_base_url: str = "https://api.ggleap.com/production"
    site_key: str = SITE_KEY
    recaptcha_action: str = RECAPTCHA_ACTION
    token_ttl_seconds: int = 120
    max_api_retries: int = 3
    max_sheets_retries: int = 3
    min_lead_minutes: int = 15

    @staticmethod
    def from_env(env: dict[str, str] | None = None) -> "AppConfig":
        env = env if env is not None else dict(os.environ)

        venues_json = env.get("VENUES_JSON")
        if venues_json:
            venues = [
                Venue(v["slug"], v["name"], v["center_uuid"],
                      v.get("sheet_tab", v["name"]),
                      v.get("timezone", "Europe/Prague"))
                for v in json.loads(venues_json)
            ]
        else:
            venues = list(DEFAULT_VENUES)

        excluded_raw = env.get("EXCLUDED_ZONES")
        if excluded_raw:
            excluded = frozenset(json.loads(excluded_raw)) \
                if excluded_raw.strip().startswith("[") \
                else frozenset(z.strip() for z in excluded_raw.split(",") if z.strip())
        else:
            excluded = DEFAULT_EXCLUDED_ZONES

        proxy = ProxyConfig(
            enabled=env.get("PROXY_ENABLED", "false").lower() == "true",
            server=env.get("PROXY_SERVER") or None,
        )

        return AppConfig(
            venues=venues,
            spreadsheet_id=env.get("GOOGLE_SPREADSHEET_ID", ""),
            service_account_path=env.get("GOOGLE_SA_PATH", ""),
            look_ahead_hours=int(env.get("LOOK_AHEAD_HOURS", "8")),
            excluded_zones=excluded,
            proxy=proxy,
        )
