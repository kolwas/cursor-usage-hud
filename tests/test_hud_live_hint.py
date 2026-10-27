"""When live Claude usage fails and the Desktop log is dead, the chip says why."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from usage_hud.models import Metric, ProviderSnapshot, utc_now  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


def _claude(raw):
    unknown = Metric(key="five_hour", label="5h", used=0.0, limit=None, unit="%", stale=True)
    return ProviderSnapshot(
        provider_id="anthropic", title="Claude", ok=True, fetched_at=utc_now(),
        metrics=[unknown], raw=raw,
    )


def _chip(snap):
    from usage_hud.ui.hud import WeatherPanel

    panel = WeatherPanel()
    panel._snapshots = [snap]
    panel._projections = []
    try:
        return panel._chip_html()
    finally:
        panel.deleteLater()


def test_expired_sign_in_shows_login_instead_of_a_silent_dash():
    html = _chip(_claude({"live_error": "live usage unavailable (Claude Code sign-in expired - use Claude Code once to renew it)"}))
    assert ">login<" in html and "—" not in html


def test_other_live_failures_show_a_generic_hint():
    assert ">live?<" in _chip(_claude({"live_error": "live usage unavailable (Anthropic not reachable)"}))


def test_without_a_live_error_the_unknown_gauge_is_still_a_plain_dash():
    html = _chip(_claude({}))
    assert "—" in html and ">login<" not in html and ">live?<" not in html
