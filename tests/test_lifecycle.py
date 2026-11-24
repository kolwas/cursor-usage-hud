from usage_hud import lifecycle


def _log(tmp_path):
    return (tmp_path / "lifecycle.log").read_text(encoding="utf-8")


def test_clean_run_leaves_no_complaint_on_the_next_start(tmp_path):
    lifecycle.start(tmp_path)
    lifecycle.pulse(tmp_path)
    lifecycle.clean_exit(tmp_path)
    lifecycle.start(tmp_path)
    assert "vanished" not in _log(tmp_path)
    assert _log(tmp_path).count("start pid=") == 2
    assert "clean exit" in _log(tmp_path)


def test_a_run_killed_from_outside_is_noticed_on_the_next_start(tmp_path):
    lifecycle.start(tmp_path)
    lifecycle.pulse(tmp_path)
    # no clean_exit: the process was terminated
    lifecycle.start(tmp_path)
    text = _log(tmp_path)
    assert "previous run vanished without a clean exit" in text
    assert "last pulse: running" in text


def test_session_end_is_recorded(tmp_path):
    lifecycle.start(tmp_path)
    lifecycle.session_ending(tmp_path)
    assert "session is ending" in _log(tmp_path)


def test_unwritable_state_dir_never_raises(tmp_path):
    missing = tmp_path / "nope" / "deeper"
    lifecycle.start(missing)
    lifecycle.pulse(missing)
    lifecycle.clean_exit(missing)


def test_note_appends_a_line(tmp_path):
    lifecycle.note(tmp_path, "claude: live usage ok")
    assert "claude: live usage ok" in _log(tmp_path)


def _snap(provider_id, *, ok, error=""):
    from usage_hud.models import ProviderSnapshot, utc_now

    return ProviderSnapshot(
        provider_id=provider_id, title=provider_id, ok=ok, fetched_at=utc_now(), error=error
    )


def test_a_failing_provider_is_logged_once_and_again_when_it_recovers(tmp_path):
    seen: dict[str, str] = {}
    failing = [_snap("cursor", ok=False, error="Cursor API HTTP 401: unauthorized")]
    lifecycle.note_provider_failures(tmp_path, failing, seen)
    lifecycle.note_provider_failures(tmp_path, failing, seen)  # same error: no repeat
    assert _log(tmp_path).count("cursor: Cursor API HTTP 401") == 1

    lifecycle.note_provider_failures(tmp_path, [_snap("cursor", ok=True)], seen)
    assert "cursor: ok again" in _log(tmp_path)
    lifecycle.note_provider_failures(tmp_path, [_snap("cursor", ok=True)], seen)
    assert _log(tmp_path).count("ok again") == 1


def test_a_provider_that_was_never_broken_logs_nothing(tmp_path):
    lifecycle.note_provider_failures(tmp_path, [_snap("cursor", ok=True)], {})
    assert not (tmp_path / "lifecycle.log").exists()


def test_failure_lines_never_carry_a_token_or_a_runaway_body(tmp_path):
    token = "eyJhbGciOiJIUzI1NiJ9." + "A" * 120 + ".sig"
    lifecycle.note_provider_failures(
        tmp_path, [_snap("cursor", ok=False, error=f"bad reply {token} " + "x " * 400)], {}
    )
    line = _log(tmp_path)
    assert "eyJ" not in line and "AAAAAAAA" not in line
    assert len(line) < 300
