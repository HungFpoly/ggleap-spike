"""Unit test cho cấu hình launch của BrowserManager (proxy bật/tắt)."""

from app.config import AppConfig, ProxyConfig
from app.browser_manager import build_launch_kwargs


def _cfg(proxy):
    return AppConfig(
        venues=[], spreadsheet_id="s", service_account_path="p", proxy=proxy)


def test_proxy_disabled_no_proxy_kwarg():
    kwargs = build_launch_kwargs(_cfg(ProxyConfig(enabled=False)))
    assert "proxy" not in kwargs
    assert kwargs["headless"] is True


def test_proxy_enabled_adds_proxy():
    kwargs = build_launch_kwargs(
        _cfg(ProxyConfig(enabled=True, server="http://host:8080")))
    assert kwargs["proxy"] == {"server": "http://host:8080"}


def test_proxy_enabled_without_server_skips():
    kwargs = build_launch_kwargs(_cfg(ProxyConfig(enabled=True, server=None)))
    assert "proxy" not in kwargs
