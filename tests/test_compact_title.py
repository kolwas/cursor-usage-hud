"""The window title / tray tooltip headline must not pass a stale reading off as live."""

from usage_hud.models import Metric, ProviderSnapshot, utc_now
from usage_hud.ui.formatters import compact_title


def _snap(provider_id, *metrics, ok=True):
    return ProviderSnapshot(
        provider_id=provider_id, title=provider_id, ok=ok, fetched_at=utc_now(), metrics=list(metrics)
    )


def _pct(percent, *, stale=False):
    return Metric(key="m", label="m", used=percent, limit=100.0, unit="%", percent_used=percent, stale=stale)


def test_a_live_reading_is_shown_plainly():
    assert compact_title([_snap("anthropic", _pct(12.0))], []) == "Cla:12%"


def test_a_stale_reading_is_marked_not_shown_as_a_real_zero():
    assert compact_title([_snap("anthropic", _pct(0.0, stale=True))], []) == "Cla:~0%"


def test_an_unknown_gauge_shows_no_number_and_a_failed_provider_shows_a_bang():
    unknown = Metric(key="m", label="m", used=0.0, limit=None, unit="%", stale=True)
    assert compact_title([_snap("anthropic", unknown), _snap("cursor", ok=False)], []) == "Cla · Cur:!"


def test_the_first_known_gauge_wins_over_an_unknown_one():
    unknown = Metric(key="a", label="a", used=0.0, limit=None, unit="%", stale=True)
    assert compact_title([_snap("anthropic", unknown, _pct(7.0, stale=True))], []) == "Cla:~7%"
