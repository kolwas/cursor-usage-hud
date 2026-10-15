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
