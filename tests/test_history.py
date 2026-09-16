from datetime import datetime, timedelta, timezone

from usage_hud.history import HistoryStore
from usage_hud.models import Metric, ProviderSnapshot

# HistoryStore.projections() always measures against the real wall clock
# (datetime.now()), not snapshot.fetched_at — so every fixture anchors
# cycle_start/cycle_end that many hours *before/after real NOW*, not before
# a made-up "now" on the snapshot (which the math never reads).
NOW = datetime.now(timezone.utc)


def _seven_day_snap(*, elapsed_hours: float, used: float) -> ProviderSnapshot:
    cycle_start = NOW - timedelta(hours=elapsed_hours)
    cycle_end = cycle_start + timedelta(days=7)
    return ProviderSnapshot(
        provider_id="anthropic",
        title="Claude",
        ok=True,
        fetched_at=NOW,
        cycle_start=cycle_start,
        cycle_end=cycle_end,
        metrics=[
            Metric(
                key="seven_day",
                label="7d",
                used=used,
                limit=100.0,
                unit="%",
                percent_used=used,
                cycle_end=cycle_end,
            )
        ],
    )


def _proj(store: HistoryStore, snap: ProviderSnapshot, key: str = "seven_day"):
    projs = store.projections([snap], burn_multiplier=2.0)
    return next(p for p in projs if p.metric_key == key)


def test_fresh_window_is_still_predicted_but_marked_tentative(tmp_path):
    """2% used, 1h into a fresh 7-day window: the noisy extrapolated rate
    (the false 'projected overrun' seen with the real Claude Desktop log)
    is still returned — predictions are never withheld — but flagged
    unconfident so callers render it as a muted/early estimate, not a verdict.
    """
    store = HistoryStore(tmp_path / "history.json")
    snap = _seven_day_snap(elapsed_hours=1, used=2.0)

    proj = _proj(store, snap)
    assert proj.confident is False
    assert proj.renewal_offset_days is not None
    assert "(early estimate)" in proj.note
    assert proj.avg_daily > 0


def test_same_rate_is_trusted_once_the_window_has_run_a_while(tmp_path):
    """The same ~2%/hour pace, 18h into the same 7-day window, is real signal."""
    store = HistoryStore(tmp_path / "history.json")
    snap = _seven_day_snap(elapsed_hours=18, used=36.0)

    proj = _proj(store, snap)
    assert proj.will_exhaust is True
    assert proj.confident is True
    assert proj.renewal_offset_days is not None
    assert "(early estimate)" not in proj.note


def test_short_rolling_window_gets_a_proportionally_short_warmup(tmp_path):
    """A 5h window must not wait 6h (longer than the window itself) to be trusted:
    3h in (60% of the window) has to already be past its own warm-up."""
    store = HistoryStore(tmp_path / "history.json")
    cycle_start = NOW - timedelta(hours=3)
    cycle_end = cycle_start + timedelta(hours=5)
    snap = ProviderSnapshot(
        provider_id="anthropic",
        title="Claude",
        ok=True,
        fetched_at=NOW,
        cycle_start=cycle_start,
        cycle_end=cycle_end,
        metrics=[
            Metric(
                key="five_hour",
                label="5h",
                used=90.0,
                limit=100.0,
                unit="%",
                percent_used=90.0,
                cycle_end=cycle_end,
            )
        ],
    )
    proj = _proj(store, snap, key="five_hour")
    assert proj.confident is True


def test_very_fresh_short_window_still_gets_a_warmup(tmp_path):
    """5 minutes into a 5h window is still too early — same rule, smaller window."""
    store = HistoryStore(tmp_path / "history.json")
    cycle_start = NOW - timedelta(minutes=5)
    cycle_end = cycle_start + timedelta(hours=5)
    snap = ProviderSnapshot(
        provider_id="anthropic",
        title="Claude",
        ok=True,
        fetched_at=NOW,
        cycle_start=cycle_start,
        cycle_end=cycle_end,
        metrics=[
            Metric(
                key="five_hour",
                label="5h",
                used=15.0,
                limit=100.0,
                unit="%",
                percent_used=15.0,
                cycle_end=cycle_end,
            )
        ],
    )
    proj = _proj(store, snap, key="five_hour")
    assert proj.confident is False
    assert "(early estimate)" in proj.note


def test_no_cycle_length_known_is_left_unconstrained(tmp_path):
    """Without both an inferred start and a known end there is no window to be
    'too early' in, so the pre-existing behaviour (trust the rate) is kept."""
    store = HistoryStore(tmp_path / "history.json")
    snap = ProviderSnapshot(
        provider_id="cursor",
        title="Cursor",
        ok=True,
        fetched_at=NOW,
        metrics=[
            Metric(
                key="included", label="Included", used=99.0, limit=100.0, unit="%", percent_used=99.0
            )
        ],
    )
    proj = _proj(store, snap, key="included")
    assert proj.note == "collecting history…"
