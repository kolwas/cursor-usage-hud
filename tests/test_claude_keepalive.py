"""The sign-in keepalive: runs the official CLI, never touches a credential.

Every test uses a stand-in for the CLI — none of them may start the real one.
"""

import os
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from usage_hud import claude_keepalive as ka  # noqa: E402
from usage_hud.models import ProviderSnapshot, utc_now  # noqa: E402

NOW = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)


class FakeCli:
    def __init__(self, returncode=0, stdout=b"ok", stderr=b"", raises=None):
        self.calls = []
        self.returncode, self.stdout, self.stderr, self.raises = returncode, stdout, stderr, raises

    def __call__(self, args, **kwargs):
        self.calls.append((args, kwargs))
        if self.raises:
            raise self.raises
        return subprocess.CompletedProcess(args, self.returncode, self.stdout, self.stderr)


def _run(tmp_path, cli, *, expired=False, now=NOW, found="C:/npm/claude.cmd"):
    return ka.run_keepalive(tmp_path, expired=expired, now=now, runner=cli, find_cli=lambda: found)


def test_runs_the_cli_with_one_tiny_request_and_no_session_file(tmp_path):
    cli = FakeCli()
    result = _run(tmp_path, cli)
    assert result == ka.KeepaliveResult(True, True, "refreshed")
    args, kwargs = cli.calls[0]
    assert args == ["C:/npm/claude.cmd", "-p", "ok", "--model", "haiku", "--no-session-persistence"]
    assert kwargs["cwd"] == str(tmp_path / "keepalive")
    assert kwargs["stdin"] == subprocess.DEVNULL and kwargs["timeout"] > 0


def test_it_does_not_run_again_within_the_schedule(tmp_path):
    cli = FakeCli()
    _run(tmp_path, cli)
    again = _run(tmp_path, cli, now=NOW + timedelta(hours=2, minutes=59))
    assert again.ran is False and len(cli.calls) == 1
    later = _run(tmp_path, cli, now=NOW + timedelta(hours=3, minutes=1))
    assert later.ran is True and len(cli.calls) == 2


def test_after_expiry_it_retries_much_sooner_but_not_in_a_loop(tmp_path):
    cli = FakeCli(returncode=1)
    assert _run(tmp_path, cli, expired=True).text == "failed (exit 1)"
    assert _run(tmp_path, cli, expired=True, now=NOW + timedelta(minutes=5)).ran is False
    assert _run(tmp_path, cli, expired=True, now=NOW + timedelta(minutes=21)).ran is True


def test_failure_text_never_contains_the_cli_output(tmp_path):
    cli = FakeCli(returncode=1, stdout=b"Bearer sk-ant-DO-NOT-LEAK", stderr=b"token=sk-ant-DO-NOT-LEAK")
    result = _run(tmp_path, cli)
    assert "LEAK" not in result.text and result.ok is False
    assert "LEAK" not in (tmp_path / "keepalive.json").read_text(encoding="utf-8")


def test_a_signed_out_cli_is_reported_as_needing_a_login(tmp_path):
    """The real failure seen on 2026-11-13: the CLI's refresh token was rejected,
    so only an interactive /login helps — the log must say so, not "exit 1"."""
    cli = FakeCli(
        returncode=1,
        stdout=b"Failed to authenticate: OAuth session expired and could not be refreshed",
    )
    result = _run(tmp_path, cli)
    assert result.ok is False and "signed out" in result.text and "/login" in result.text
    assert "OAuth" not in result.text  # fixed wording only, never the CLI's own text


def test_missing_cli_is_skipped_quietly(tmp_path):
    cli = FakeCli()
    result = _run(tmp_path, cli, found=None)
    assert result == ka.KeepaliveResult(False, False, "skipped (claude CLI not found)")
    assert cli.calls == []


def test_timeout_and_os_errors_become_fixed_messages(tmp_path):
    timed_out = _run(tmp_path, FakeCli(raises=subprocess.TimeoutExpired("claude", 90)))
    assert timed_out.text == "failed (timed out)"
    broken = _run(tmp_path, FakeCli(raises=FileNotFoundError("C:/secret/path")), now=NOW + timedelta(hours=4))
    assert broken.text == "failed (FileNotFoundError)" and "secret" not in broken.text


def test_only_an_expired_sign_in_asks_for_an_immediate_refresh():
    def snap(raw):
        return ProviderSnapshot(provider_id="anthropic", title="Claude", ok=True, fetched_at=utc_now(), raw=raw)

    expired = {"live_error": "live usage unavailable (Claude Code sign-in expired - use Claude Code once to renew it)"}
    assert ka.needs_refresh_now([snap(expired)]) is True
    assert ka.needs_refresh_now([snap({"live_error": "live usage unavailable (Anthropic not reachable)"})]) is False
    assert ka.needs_refresh_now([snap({"source": "live"}), snap({})]) is False


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_runner_works_off_the_ui_thread_and_reports_back_on_it(app, tmp_path, monkeypatch):
    ran_in = []

    def fake_run(state_dir, *, expired=False):
        ran_in.append(threading.get_ident())
        return ka.KeepaliveResult(True, True, "refreshed")

    monkeypatch.setattr(ka, "run_keepalive", fake_run)
    got = []
    runner = ka.KeepaliveRunner(lambda reason, result: got.append((threading.get_ident(), reason, result)))
    runner.start(tmp_path, reason="scheduled")
    assert runner.busy
    deadline = time.time() + 3
    while time.time() < deadline and not got:
        app.processEvents()
        time.sleep(0.005)
    assert got and got[0][1:] == ("scheduled", ka.KeepaliveResult(True, True, "refreshed"))
    assert ran_in[0] != threading.get_ident() and got[0][0] == threading.get_ident()
    assert not runner.busy


def test_runner_survives_an_unexpected_error(app, tmp_path, monkeypatch):
    def boom(state_dir, *, expired=False):
        raise RuntimeError("secret detail")

    monkeypatch.setattr(ka, "run_keepalive", boom)
    got = []
    runner = ka.KeepaliveRunner(lambda reason, result: got.append(result))
    runner.start(tmp_path, reason="expired")
    deadline = time.time() + 3
    while time.time() < deadline and not got:
        app.processEvents()
        time.sleep(0.005)
    assert got[0].text == "failed (unexpected error)" and "secret" not in got[0].text
