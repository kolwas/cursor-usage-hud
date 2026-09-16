import json
from datetime import datetime, timedelta, timezone

from usage_hud.providers import anthropic


def _utc(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _write_history(tmp_path, samples, monkeypatch):
    root = tmp_path / "Claude"
    root.mkdir(parents=True, exist_ok=True)
    (root / "plan-usage-history.json").write_text(
        json.dumps({"version": 2, "samples": samples}), encoding="utf-8"
    )
    monkeypatch.setenv("CLAUDE_DESKTOP_DIR", str(root))


def _write_account(tmp_path, account, monkeypatch):
    path = tmp_path / ".claude.json"
    path.write_text(json.dumps({"oauthAccount": account}), encoding="utf-8")
    monkeypatch.setenv("CLAUDE_JSON", str(path))


# --------------------------------------------------------------------------- #
# No credentials, no network
# --------------------------------------------------------------------------- #


def test_provider_does_not_reach_the_network():
    """Claude is local-only: no HTTP client imported, no endpoint, no auth helper."""
    assert not hasattr(anthropic, "urllib")
    assert not hasattr(anthropic, "USAGE_URL")
    assert not hasattr(anthropic, "load_opencode_auth")


# --------------------------------------------------------------------------- #
# Plan metadata
# --------------------------------------------------------------------------- #


def test_rate_limit_tier_becomes_a_plan_name():
    assert anthropic.plan_from_tier("default_claude_max_5x") == "Max 5x"
    assert anthropic.plan_from_tier("default_claude_max_20x") == "Max 20x"
    assert anthropic.plan_from_tier("default_claude_pro") == "Pro"


def test_internal_tier_codenames_are_not_shown():
    assert anthropic.plan_from_tier("default_raven") == ""
    assert anthropic.plan_from_tier("") == ""


def test_title_combines_plan_and_account():
    account = {"emailAddress": "me@example.com", "userRateLimitTier": "default_claude_max_5x"}
    assert anthropic.plan_title(account) == "Claude Max 5x · me@example.com"
    assert anthropic.plan_title({}) == "Claude"


def test_org_tier_is_a_fallback_for_the_user_tier():
    account = {"organizationRateLimitTier": "default_claude_pro"}
    assert anthropic.plan_title(account) == "Claude Pro"


# --------------------------------------------------------------------------- #
# Rolling window estimates
# --------------------------------------------------------------------------- #


def test_window_end_from_the_last_zero_sample():
    start = _utc(2026, 9, 15, 12)
    samples = [
        (start, {"fh": 0}),
        (start + timedelta(minutes=30), {"fh": 4}),
        (start + timedelta(minutes=60), {"fh": 9}),
    ]
    end = anthropic.infer_window_end(samples, "fh", timedelta(hours=5), start + timedelta(hours=1))
    assert end == start + timedelta(hours=5)


def test_window_end_after_a_drop():
    base = _utc(2026, 9, 15, 8)
    rolled = base + timedelta(hours=6)
    samples = [
        (base, {"fh": 40}),
        (base + timedelta(hours=3), {"fh": 80}),
        (rolled, {"fh": 5}),
    ]
    end = anthropic.infer_window_end(samples, "fh", timedelta(hours=5), rolled)
    assert end == rolled + timedelta(hours=5)


def test_all_zero_series_means_no_window_running():
    base = _utc(2026, 9, 15, 8)
    samples = [(base, {"sd": 0}), (base + timedelta(hours=1), {"sd": 0})]
    assert anthropic.infer_window_end(samples, "sd", timedelta(days=7), base) is None


def test_expired_window_is_unknown_not_guessed_forward():
    base = _utc(2026, 9, 15, 8)
    samples = [(base, {"fh": 0}), (base + timedelta(minutes=10), {"fh": 30})]
    assert anthropic.infer_window_end(samples, "fh", timedelta(hours=5), base + timedelta(hours=9)) is None


# --------------------------------------------------------------------------- #
# Desktop log snapshot
# --------------------------------------------------------------------------- #


def test_snapshot_reports_both_windows(tmp_path, monkeypatch):
    now = _utc(2026, 9, 15, 13)
    _write_history(
        tmp_path,
        [
            {"t": _ms(now - timedelta(minutes=40)), "u": {"fh": 0, "sd": 2}},
            {"t": _ms(now - timedelta(minutes=5)), "u": {"fh": 4, "sd": 2}},
        ],
        monkeypatch,
    )
    snap = anthropic.snapshot_from_desktop_history(now, title="Claude")
    assert snap is not None and snap.ok
    assert [(m.key, m.used) for m in snap.metrics] == [("five_hour", 4.0), ("seven_day", 2.0)]
    # 5 h window opened at the last zero sample, so it still has ~4 h 20 m to run.
    assert snap.metrics[0].cycle_end == now - timedelta(minutes=40) + timedelta(hours=5)
    assert "estimated locally" in snap.message


def test_stale_log_reports_no_window_end(tmp_path, monkeypatch):
    now = _utc(2026, 9, 15, 13)
    _write_history(
        tmp_path,
        [{"t": _ms(now - timedelta(hours=9)), "u": {"fh": 55, "sd": 20}}],
        monkeypatch,
    )
    snap = anthropic.snapshot_from_desktop_history(now, title="Claude")
    assert snap is not None
    assert snap.metrics[0].cycle_end is None
    assert "stale 9h" in snap.metrics[0].detail


def test_extra_usage_is_called_out(tmp_path, monkeypatch):
    now = _utc(2026, 9, 15, 13)
    _write_history(tmp_path, [{"t": _ms(now), "u": {"fh": 10}}], monkeypatch)
    snap = anthropic.snapshot_from_desktop_history(now, title="Claude", extra_usage=True)
    assert snap is not None
    assert "not a hard stop" in snap.message


# --------------------------------------------------------------------------- #
# Provider wiring
# --------------------------------------------------------------------------- #


def test_fetch_uses_local_files_only(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc)
    _write_history(tmp_path, [{"t": _ms(now - timedelta(minutes=2)), "u": {"fh": 6}}], monkeypatch)
    _write_account(
        tmp_path,
        {
            "emailAddress": "me@example.com",
            "userRateLimitTier": "default_claude_max_5x",
            "hasExtraUsageEnabled": True,
        },
        monkeypatch,
    )

    snap = anthropic.AnthropicProvider().fetch()
    assert snap.ok
    assert snap.title == "Claude Max 5x · me@example.com"
    assert snap.metrics[0].used == 6.0
    assert "extra usage on" in snap.message


def test_fetch_without_a_log_reports_why(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_DESKTOP_DIR", str(tmp_path / "missing"))
    monkeypatch.setattr(anthropic, "find_plan_usage_history", lambda: None)
    _write_account(tmp_path, {"emailAddress": "me@example.com"}, monkeypatch)

    snap = anthropic.AnthropicProvider().fetch()
    assert not snap.ok
    assert "Claude Desktop app runs" in snap.error


def test_provider_is_registered_from_local_signals_only(tmp_path, monkeypatch):
    monkeypatch.setattr(anthropic, "find_plan_usage_history", lambda: None)
    monkeypatch.setattr(anthropic, "claude_account_meta", lambda: {})
    assert anthropic.claude_present_locally() is False

    monkeypatch.setattr(anthropic, "claude_account_meta", lambda: {"emailAddress": "x@y.z"})
    assert anthropic.claude_present_locally() is True
