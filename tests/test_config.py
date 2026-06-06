"""Unit test cho AppConfig.from_env."""

import json

from app.config import AppConfig, DEFAULT_VENUES, DEFAULT_EXCLUDED_ZONES


def test_defaults_when_minimal_env():
    cfg = AppConfig.from_env({
        "GOOGLE_SPREADSHEET_ID": "sheet123",
        "GOOGLE_SA_PATH": "/etc/secrets/sa.json",
    })
    assert cfg.look_ahead_hours == 8
    assert len(cfg.venues) == 3
    assert {v.slug for v in cfg.venues} == {v.slug for v in DEFAULT_VENUES}
    assert cfg.excluded_zones == DEFAULT_EXCLUDED_ZONES
    assert cfg.proxy.enabled is False
    assert cfg.spreadsheet_id == "sheet123"


def test_proxy_enabled():
    cfg = AppConfig.from_env({
        "PROXY_ENABLED": "true",
        "PROXY_SERVER": "http://user:pass@host:8080",
    })
    assert cfg.proxy.enabled is True
    assert cfg.proxy.server == "http://user:pass@host:8080"


def test_look_ahead_override_and_excluded_csv():
    cfg = AppConfig.from_env({
        "LOOK_AHEAD_HOURS": "5",
        "EXCLUDED_ZONES": "Room for unassigned machines, Test zone",
    })
    assert cfg.look_ahead_hours == 5
    assert "Test zone" in cfg.excluded_zones
    assert "Room for unassigned machines" in cfg.excluded_zones


def test_venues_json_override():
    venues = [{"slug": "x", "name": "X", "center_uuid": "uuid-x"}]
    cfg = AppConfig.from_env({"VENUES_JSON": json.dumps(venues)})
    assert len(cfg.venues) == 1
    assert cfg.venues[0].slug == "x"
    assert cfg.venues[0].sheet_tab == "X"  # mặc định = name
