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


def _claude_like_snap(*, now: datetime, cycle_end: datetime, used: float) -> ProviderSnapshot:
    """No real cycle_start anywhere (snap or metric) — mirrors Claude, which
    never reports one, forcing the percent-based backward inference."""
    return ProviderSnapshot(
        provider_id="anthropic",
        title="Claude",
        ok=True,
        fetched_at=now,
        metrics=[
            Metric(
                key="seven_day", label="7d", used=used, limit=100.0, unit="%",
                percent_used=used, cycle_end=cycle_end,
            )
        ],
    )


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


def _two_window_snap(
    *, now: datetime, five_hour_cycle_end: datetime, seven_day_cycle_end: datetime, seven_day_used: float
) -> ProviderSnapshot:
    """Mirrors anthropic.py's real shape: the snapshot-level cycle_end is
    always the FIRST metric's (five_hour's) — the same field a second,
    differently-scheduled metric's history got wrongly filtered by."""
    return ProviderSnapshot(
        provider_id="anthropic",
        title="Claude",
        ok=True,
        fetched_at=now,
        cycle_end=five_hour_cycle_end,
        metrics=[
            Metric(
                key="five_hour", label="5h", used=10.0, limit=100.0, unit="%",
                percent_used=10.0, cycle_end=five_hour_cycle_end,
            ),
            Metric(
                key="seven_day", label="7d", used=seven_day_used, limit=100.0, unit="%",
                percent_used=seven_day_used, cycle_end=seven_day_cycle_end,
            ),
        ],
    )


def test_a_second_windows_history_is_not_scoped_by_the_first_windows_resets(tmp_path):
    """Regression: the "same cycle" filter compared each stored sample's
    SNAPSHOT-level cycle_end against the current one — but for Claude that
    field is always five_hour's, not whichever metric is actually being
    projected. Every time the 5h window reset (~every 5h), seven_day's own
    week-long history got silently re-scoped down to "since the 5h window
    last reset" — a few hours standing in for as much as a week, because
    the two windows share no real relationship at all.
    """
    store = HistoryStore(tmp_path / "history.json")
    seven_day_end = NOW + timedelta(days=6)  # stable — the 7d window doesn't move

    # Two 5h resets happen across this stretch (the exact boundaries don't
    # matter — only that the snapshot-level cycle_end keeps changing while
    # seven_day's own stays put).
    store.record([_two_window_snap(
        now=NOW - timedelta(hours=20), five_hour_cycle_end=NOW - timedelta(hours=15),
        seven_day_cycle_end=seven_day_end, seven_day_used=1.0,
    )])
    store.record([_two_window_snap(
        now=NOW - timedelta(hours=15), five_hour_cycle_end=NOW - timedelta(hours=10),
        seven_day_cycle_end=seven_day_end, seven_day_used=1.2,
    )])
    store.record([_two_window_snap(
        now=NOW - timedelta(hours=10), five_hour_cycle_end=NOW - timedelta(hours=5),
        seven_day_cycle_end=seven_day_end, seven_day_used=1.4,
    )])
    # A 5h reset just happened — this and the next sample share the SAME
    # (current) five_hour cycle_end, which is exactly the case that used to
    # wrongly narrow seven_day's history down to just these two points.
    store.record([_two_window_snap(
        now=NOW - timedelta(hours=5), five_hour_cycle_end=NOW,
        seven_day_cycle_end=seven_day_end, seven_day_used=1.6,
    )])
    snap = _two_window_snap(
        now=NOW - timedelta(hours=1), five_hour_cycle_end=NOW,
        seven_day_cycle_end=seven_day_end, seven_day_used=8.0,
    )
    store.record([snap])

    proj = _proj(store, snap, key="seven_day")

    # Correct: the full ~19h span (1.0% -> 8.0%) -> roughly 8-9%/day.
    assert 5.0 < proj.avg_daily < 12.0
    # The bug's answer used only the last two (same 5h cycle_end) samples,
    # 1.6% -> 8.0% over 4h -> ~38%/day — well outside the correct range.
    assert proj.avg_daily < 30.0


def test_real_history_overrides_the_tautological_cycle_pace_for_an_inferred_start(tmp_path):
    """Regression: when no provider reports a real cycle_start (Claude never
    does), the backward-inferred one is built FROM percent_used and
    time-to-reset assuming a constant rate — so a "cycle pace" average
    computed from that same inferred start just reconstructs the assumption
    that produced it. renewal_offset comes out at ~0 ("exhaust right at
    reset") for EVERY snapshot, regardless of the real trend, because it is
    algebraically forced there, not because that's actually true.

    A real, slow, steadily-observed history (well past the 6h floor) must
    override that tautology once available, even though the tautological
    figure is numerically much larger.
    """
    store = HistoryStore(tmp_path / "history.json")
    cycle_end = NOW + timedelta(hours=148)  # ~6.9 days left in a 7-day window

    # A slow, real climb recorded over the last 20 hours: ~0.2%/hour.
    store.record([_claude_like_snap(now=NOW - timedelta(hours=20), cycle_end=cycle_end + timedelta(hours=20), used=1.0)])
    store.record([_claude_like_snap(now=NOW - timedelta(hours=10), cycle_end=cycle_end + timedelta(hours=10), used=3.0)])
    snap = _claude_like_snap(now=NOW, cycle_end=cycle_end, used=5.0)
    store.record([snap])

    proj = _proj(store, snap)

    # The tautological cycle-pace for these numbers would be ~15%/day and
    # force renewal_offset to ~0 — the real observed pace is close to 5%/day.
    assert proj.avg_daily < 10.0
    assert proj.renewal_offset_days is not None
    assert abs(proj.renewal_offset_days) > 1.0  # not the ~0 tautology artifact


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


def _cursor_snap(now: datetime, used: float) -> ProviderSnapshot:
    # cycle_start/cycle_end anchor to the module-level NOW, not to this
    # sample's own `now` — a real billing cycle does not shift between
    # polls, and several tests record a handful of samples spread across
    # minutes/days that are all meant to be the SAME ongoing cycle (so the
    # same-cycle history-scoping in projections() actually groups them).
    # cycle_end is set on the Metric itself, not just the snapshot: the
    # same-cycle filter keys off each STORED sample's per-metric cycle_end
    # (_metric_cycle_end), which is only ever recorded when Metric.cycle_end
    # is set — leaving it off silently made every recorded sample look
    # cycle-less and the same-cycle grouping could never match anything.
    cycle_end = NOW + timedelta(days=20)
    return ProviderSnapshot(
        provider_id="cursor",
        title="Cursor",
        ok=True,
        fetched_at=now,
        cycle_start=NOW - timedelta(days=10),
        cycle_end=cycle_end,
        metrics=[
            Metric(
                key="included", label="Included", used=used, limit=100.0, unit="%",
                percent_used=used, cycle_end=cycle_end,
            )
        ],
    )


def test_series_returns_the_raw_recorded_points_oldest_first(tmp_path):
    store = HistoryStore(tmp_path / "history.json")
    store.record([_cursor_snap(NOW - timedelta(hours=2), 10.0)])
    store.record([_cursor_snap(NOW - timedelta(hours=1), 20.0)])
    store.record([_cursor_snap(NOW, 30.0)])

    points = store.series("cursor", "included")
    assert [v for _, v in points] == [10.0, 20.0, 30.0]
    assert points[0][0] < points[1][0] < points[2][0]


def test_series_max_points_keeps_the_first_and_last(tmp_path):
    store = HistoryStore(tmp_path / "history.json")
    for i in range(50):
        store.record([_cursor_snap(NOW - timedelta(minutes=50 - i), float(i))])

    points = store.series("cursor", "included", max_points=10)
    assert len(points) <= 10
    assert points[0][1] == 0.0
    assert points[-1][1] == 49.0


def test_sudden_spike_today_is_flagged_hot(tmp_path):
    """A pace far above the historical average today must set hot=True —
    it drives both the CRITICAL alert and the sparkline's spike badge."""
    store = HistoryStore(tmp_path / "history.json")
    day_start = NOW.replace(hour=0, minute=0, second=0, microsecond=0)
    # A slow, steady history over the past several days...
    store.record([_cursor_snap(NOW - timedelta(days=3), 5.0)])
    # ...then a sudden jump earlier today...
    store.record([_cursor_snap(day_start + timedelta(minutes=1), 6.0)])
    # ...and a big spike just now.
    snap = _cursor_snap(NOW, 40.0)
    store.record([snap])

    proj = _proj(store, snap, key="included")
    assert proj.hot is True
    assert "burning hot" in proj.note


def test_steady_pace_is_not_flagged_hot(tmp_path):
    store = HistoryStore(tmp_path / "history.json")
    day_start = NOW.replace(hour=0, minute=0, second=0, microsecond=0)
    store.record([_cursor_snap(NOW - timedelta(days=3), 5.0)])
    store.record([_cursor_snap(day_start + timedelta(minutes=1), 10.0)])
    snap = _cursor_snap(NOW, 11.0)
    store.record([snap])

    proj = _proj(store, snap, key="included")
    assert proj.hot is False


def test_short_window_burst_is_flagged_rocketing(tmp_path):
    """A fast climb in the last ~45 minutes, independent of `hot`'s whole-day
    comparison — this must fire even early in the day when 'today' barely
    has any history behind it yet for `hot` to compare against."""
    store = HistoryStore(tmp_path / "history.json")
    store.record([_cursor_snap(NOW - timedelta(days=10), 2.0)])
    store.record([_cursor_snap(NOW - timedelta(minutes=40), 5.0)])
    snap = _cursor_snap(NOW, 25.0)
    store.record([snap])

    proj = _proj(store, snap, key="included")
    assert proj.rocketing is True


def test_slow_steady_climb_is_not_flagged_rocketing(tmp_path):
    store = HistoryStore(tmp_path / "history.json")
    store.record([_cursor_snap(NOW - timedelta(days=10), 2.0)])
    store.record([_cursor_snap(NOW - timedelta(minutes=40), 9.5)])
    snap = _cursor_snap(NOW, 10.0)
    store.record([snap])

    proj = _proj(store, snap, key="included")
    assert proj.rocketing is False


def test_rocketing_fires_on_a_short_rolling_window_despite_inflated_avg_daily(tmp_path):
    """Regression: on a short window (like Claude's 5h) barely into its own
    cycle, avg_daily is computed from a tiny elapsed slice and is already
    huge — comparing the recent burst to THAT baseline can mathematically
    never trip, which is exactly the bug this reproduces and fixes. The
    detector must compare against the metric's own OLDER history instead.
    """
    store = HistoryStore(tmp_path / "history.json")
    cycle_start = NOW - timedelta(hours=1, minutes=30)
    cycle_end = cycle_start + timedelta(hours=5)

    def five_hour_snap(ts: datetime, used: float) -> ProviderSnapshot:
        return ProviderSnapshot(
            provider_id="anthropic",
            title="Claude",
            ok=True,
            fetched_at=ts,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
            metrics=[
                Metric(
                    key="five_hour", label="5h", used=used, limit=100.0, unit="%",
                    percent_used=used, cycle_end=cycle_end,
                )
            ],
        )

    # Flat for the first hour of the window...
    store.record([five_hour_snap(NOW - timedelta(minutes=80), 5.0)])
    store.record([five_hour_snap(NOW - timedelta(minutes=60), 5.0)])
    # ...then a fast climb in the last 45 minutes.
    store.record([five_hour_snap(NOW - timedelta(minutes=38), 5.0)])
    snap = five_hour_snap(NOW, 24.0)
    store.record([snap])

    proj = _proj(store, snap, key="five_hour")
    assert proj.avg_daily > 100  # confirms the trap: already-inflated baseline
    assert proj.rocketing is True


def test_rocketing_never_fires_from_a_previous_already_reset_cycles_pace(tmp_path):
    """"Is this fast" for a short window like Claude's 5h can only be judged
    against ITS OWN history — a previous 5h session's pace is a different,
    unrelated period and is not a valid baseline (reported: "5h nie jestes w
    stanie ocenic patrzac na poprzednie 5h"). Right after a reset, before
    this window has recorded at least 2 samples of its own, rocketing must
    stay False rather than reach back across the reset for a baseline."""
    store = HistoryStore(tmp_path / "history.json")

    def five_hour_snap(
        ts: datetime, used: float, *, cycle_start: datetime, cycle_end: datetime
    ) -> ProviderSnapshot:
        return ProviderSnapshot(
            provider_id="anthropic",
            title="Claude",
            ok=True,
            fetched_at=ts,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
            metrics=[
                Metric(
                    key="five_hour", label="5h", used=used, limit=100.0, unit="%",
                    percent_used=used, cycle_end=cycle_end,
                )
            ],
        )

    # A fast, unrelated climb well inside the PREVIOUS 5h session.
    prev_start = NOW - timedelta(hours=6)
    prev_end = prev_start + timedelta(hours=5)
    store.record(
        [five_hour_snap(prev_start + timedelta(hours=1), 10.0, cycle_start=prev_start, cycle_end=prev_end)]
    )
    store.record(
        [five_hour_snap(prev_start + timedelta(hours=2), 70.0, cycle_start=prev_start, cycle_end=prev_end)]
    )

    # New cycle just started — only one sample of its own recorded so far,
    # nowhere near enough to say anything about ITS pace yet.
    new_start = NOW - timedelta(minutes=20)
    new_end = new_start + timedelta(hours=5)
    snap = five_hour_snap(NOW, 18.0, cycle_start=new_start, cycle_end=new_end)
    store.record([snap])

    proj = _proj(store, snap, key="five_hour")
    assert proj.rocketing is False


def test_two_samples_a_minute_apart_are_not_enough_of_a_trend(tmp_path):
    """A tiny observed slice inside the 45-minute window must not trip the
    detector just because two samples a minute apart imply a huge %/hour
    rate — need to have actually watched a real chunk of the window."""
    store = HistoryStore(tmp_path / "history.json")
    store.record([_cursor_snap(NOW - timedelta(days=10), 2.0)])
    store.record([_cursor_snap(NOW - timedelta(minutes=1), 5.0)])
    snap = _cursor_snap(NOW, 10.0)
    store.record([snap])

    proj = _proj(store, snap, key="included")
    assert proj.rocketing is False


# --------------------------------------------------------------------------- #
# History-based avg_daily overriding the tautological cycle-pace estimate
# --------------------------------------------------------------------------- #


def _claude_five_hour_snap(*, now: datetime, cycle_end: datetime, used: float) -> ProviderSnapshot:
    """No real cycle_start anywhere — mirrors Claude, which never reports
    one for the 5h window either, forcing the percent-based backward
    inference (see cycle.infer_cycle_start)."""
    return ProviderSnapshot(
        provider_id="anthropic",
        title="Claude",
        ok=True,
        fetched_at=now,
        metrics=[
            Metric(
                key="five_hour", label="5h", used=used, limit=100.0, unit="%",
                percent_used=used, cycle_end=cycle_end,
            )
        ],
    )


def test_history_average_can_override_within_a_short_windows_own_lifetime(tmp_path):
    """Regression: "-0d 0h 00m" forever on the 5h gauge. The history-based
    average is supposed to override the tautological cycle-pace estimate
    (built from a back-inferred cycle_start, which algebraically can only
    ever agree with itself — see the comment in history.py) once there is
    real same-cycle data to measure a rate from. The threshold for "enough
    same-cycle data" used to be a flat 6 hours — longer than Claude's
    entire 5h window can ever run for, so for that gauge the override could
    never fire, not even once, and the ETA badge always read a fabricated
    exact zero. 40 minutes of real same-cycle samples must be enough now.
    """
    store = HistoryStore(tmp_path / "history.json")
    reset = NOW - timedelta(minutes=40)
    cycle_end = reset + timedelta(hours=5)
    store.record([_claude_five_hour_snap(now=reset, cycle_end=cycle_end, used=0.0)])
    snap = _claude_five_hour_snap(now=NOW, cycle_end=cycle_end, used=38.0)
    store.record([snap])

    proj = _proj(store, snap, key="five_hour")
    # A genuine climb this fast (0% to 38% in 40 minutes) is a real,
    # non-tautological rate — the point isn't that it happens to be tame,
    # it's that it isn't a suspiciously exact zero any more.
    assert abs(proj.renewal_offset_days) > 1e-6
    assert "history" in proj.note or proj.avg_daily > 50.0


def test_a_big_delta_overrides_even_before_the_elapsed_floor_is_reached(tmp_path):
    """Regression, reported again after the previous fix: "Znow 5h to 0
    gdni na minisie". A window that resets and climbs FAST (0% to 18% in
    just 15 minutes — real live example) still lost to the elapsed-time
    floor (30 minutes for a 5h window), because 15 minutes had not yet
    passed, even though an 18-point jump is obviously not 2-samples-a-
    minute-apart noise. The override must trust an unambiguously large
    delta immediately, not make it wait out a timer first.
    """
    store = HistoryStore(tmp_path / "history.json")
    reset = NOW - timedelta(minutes=15)
    cycle_end = reset + timedelta(hours=5)
    store.record([_claude_five_hour_snap(now=reset, cycle_end=cycle_end, used=0.0)])
    snap = _claude_five_hour_snap(now=NOW, cycle_end=cycle_end, used=18.0)
    store.record([snap])

    proj = _proj(store, snap, key="five_hour")
    assert abs(proj.renewal_offset_days) > 1e-6


def test_a_tiny_delta_still_waits_for_the_elapsed_floor(tmp_path):
    """The other half of the same fix: a THIN delta (noise-scale, not a
    real signal) must not get to skip the elapsed-time floor just because
    it's early — only a delta big enough to not plausibly be noise gets
    the fast path."""
    store = HistoryStore(tmp_path / "history.json")
    reset = NOW - timedelta(minutes=2)
    cycle_end = reset + timedelta(hours=5)
    store.record([_claude_five_hour_snap(now=reset, cycle_end=cycle_end, used=0.0)])
    snap = _claude_five_hour_snap(now=NOW, cycle_end=cycle_end, used=1.0)
    store.record([snap])

    proj = _proj(store, snap, key="five_hour")
    # The history override must not have fired — a 1-point wobble 2
    # minutes into a fresh window is exactly the noise case the elapsed
    # floor exists to catch, and 1.0 point is well under _MIN_ELAPSED_DELTA.
    assert "history" not in proj.note
    assert proj.confident is False


def test_a_re_estimated_cycle_end_does_not_orphan_earlier_same_cycle_history(tmp_path):
    """Regression: infer_window_end's cycle_end estimate can legitimately
    shift by hours between refreshes as more of the window's own log comes
    into view (observed live: ~2h15m for a 7-day window) — comparing
    cycle_end for EXACT equality treated that refinement as a brand-new
    cycle, silently cutting the cycle's own earlier samples out of its own
    history-based average and leaving only a sliver too short to ever
    clear the elapsed-time threshold.
    """
    store = HistoryStore(tmp_path / "history.json")
    cycle_start = NOW - timedelta(hours=40)
    # An early, slightly-off estimate of when this 7-day cycle ends...
    stale_estimate = cycle_start + timedelta(days=7) - timedelta(hours=2)
    store.record(
        [_claude_like_snap(now=cycle_start + timedelta(hours=1), cycle_end=stale_estimate, used=2.0)]
    )
    store.record(
        [_claude_like_snap(now=cycle_start + timedelta(hours=20), cycle_end=stale_estimate, used=20.0)]
    )
    # ...refined closer to now, drifting by ~2 hours — still the SAME real
    # cycle, not a new one (a real new cycle would be a full 7 days away).
    refined_estimate = cycle_start + timedelta(days=7)
    snap = _claude_like_snap(now=NOW, cycle_end=refined_estimate, used=29.0)
    store.record([snap])

    proj = _proj(store, snap, key="seven_day")
    # With the 40-hour-old sample correctly still counted as same-cycle,
    # the real rate is close to (29-2)/39h =~ 16.6%/day, not the
    # tautological cycle-pace built from only the last few minutes.
    assert proj.avg_daily < 30.0
    assert abs(proj.renewal_offset_days) > 0.5
