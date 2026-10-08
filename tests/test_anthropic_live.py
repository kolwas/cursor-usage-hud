"""Live Claude usage: everything except the credential/network function itself,
which ships unimplemented — so these tests use synthetic values only."""

import json
from datetime import datetime, timedelta, timezone

from usage_hud.config import Settings
from usage_hud.history import HistoryStore
from usage_hud.providers import anthropic, anthropic_live
from usage_hud.providers.anthropic_live import LiveUsageUnavailable, LiveWindow

NOW = datetime(2026, 9, 15, 13, tzinfo=timezone.utc)


def _isolate(tmp_path, monkeypatch, samples=None):
    monkeypatch.setenv("CLAUDE_JSON", str(tmp_path / "missing.json"))
    root = tmp_path / "Claude"
    root.mkdir()
    if samples is not None:
        (root / "plan-usage-history.json").write_text(
            json.dumps({"version": 2, "samples": samples}), encoding="utf-8"
        )
    monkeypatch.setenv("CLAUDE_DESKTOP_DIR", str(root))


def test_live_option_is_off_by_default_and_follows_the_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("USAGE_HUD_STATE_DIR", str(tmp_path))
    monkeypatch.delenv("USAGE_HUD_CLAUDE_LIVE", raising=False)
    assert Settings.load().claude_live_usage is False
    monkeypatch.setenv("USAGE_HUD_CLAUDE_LIVE", "1")
    assert Settings.load().claude_live_usage is True


def test_live_snapshot_carries_exact_percent_and_reset_times():
    end5 = NOW + timedelta(hours=2, minutes=7)
    end7 = NOW + timedelta(days=4)
    snap = anthropic_live.snapshot_from_live(
        NOW,
        {"five_hour": LiveWindow(37.0, end5), "seven_day": LiveWindow(140.0, end7)},
        title="Claude Max",
    )
    by_key = {m.key: m for m in snap.metrics}
    assert by_key["five_hour"].percent_used == 37.0
    assert by_key["five_hour"].cycle_end == end5
    assert by_key["seven_day"].percent_used == 100.0  # clamped
    assert not any(m.stale for m in snap.metrics)
    assert snap.raw["source"] == "live"


def test_live_snapshot_with_no_windows_is_none():
    assert anthropic_live.snapshot_from_live(NOW, {}, title="Claude") is None


def test_provider_uses_live_usage_when_it_is_available(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setattr(
        anthropic_live, "fetch_live_usage", lambda: {"five_hour": LiveWindow(12.0, NOW)}
    )
    snap = anthropic.AnthropicProvider(live=True).fetch()
    assert snap.ok and snap.raw["source"] == "live"
    assert [(m.key, m.percent_used) for m in snap.metrics] == [("five_hour", 12.0)]


def test_unimplemented_live_fetch_falls_back_to_the_desktop_log(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc)
    _isolate(
        tmp_path,
        monkeypatch,
        [{"t": int(now.timestamp() * 1000), "u": {"fh": 9, "sd": 30}}],
    )
    snap = anthropic.AnthropicProvider(live=True).fetch()
    assert snap.ok and snap.raw["source"] == "plan-usage-history"
    assert "live usage unavailable" in snap.message


def test_unexpected_failure_falls_back_without_leaking_its_message(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc)
    _isolate(
        tmp_path,
        monkeypatch,
        [{"t": int(now.timestamp() * 1000), "u": {"fh": 9, "sd": 30}}],
    )

    def boom():
        raise RuntimeError("Bearer sk-ant-DO-NOT-LEAK")

    monkeypatch.setattr(anthropic_live, "fetch_live_usage", boom)
    snap = anthropic.AnthropicProvider(live=True).fetch()
    assert snap.ok
    assert "RuntimeError" in snap.message
    assert "DO-NOT-LEAK" not in snap.message


def test_live_off_never_calls_the_live_function(tmp_path, monkeypatch):
    _isolate(
        tmp_path,
        monkeypatch,
        [{"t": int(datetime.now(timezone.utc).timestamp() * 1000), "u": {"fh": 1, "sd": 2}}],
    )

    def must_not_run():
        raise AssertionError("live fetch called while the option is off")

    monkeypatch.setattr(anthropic_live, "fetch_live_usage", must_not_run)
    assert anthropic.AnthropicProvider().fetch().ok


def test_live_readings_stay_in_history_when_the_log_is_merged_later(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    store = HistoryStore(tmp_path / "history.json")
    live = anthropic_live.snapshot_from_live(
        NOW, {"five_hour": LiveWindow(20.0, NOW + timedelta(hours=3))}, title="Claude"
    )
    store.record([live])
    samples = store._read()["samples"]
    assert samples[0]["src"] == "live"

    entry = {
        "ts": (NOW - timedelta(hours=1)).isoformat(), "provider_id": "anthropic",
        "cycle_start": None, "cycle_end": None, "src": "log",
        "metrics": [{"key": "five_hour", "used": 5.0, "limit": 100.0, "percent_used": 5.0,
                     "unit": "%", "cycle_end": None}],
    }
    logged = anthropic_live.snapshot_from_live(NOW, {"five_hour": LiveWindow(1.0)}, title="Claude")
    logged.raw["history_entries"] = [entry]
    store.record([logged])
    assert [s["src"] for s in store._read()["samples"]] == ["log", "live"]


def test_unavailable_error_message_is_what_the_user_sees():
    try:
        anthropic_live.fetch_live_usage()
    except LiveUsageUnavailable as exc:
        assert "not implemented" in str(exc)
    else:
        raise AssertionError("the unimplemented stub must raise")
