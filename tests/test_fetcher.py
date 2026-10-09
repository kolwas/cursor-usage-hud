import os
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from usage_hud import fetcher  # noqa: E402
from usage_hud.config import Settings  # noqa: E402
from usage_hud.models import ProviderSnapshot, utc_now  # noqa: E402
from usage_hud.providers.base import Provider  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _Fake(Provider):
    def __init__(self, pid, *, delay=0.0, boom=False):
        self.id = pid
        self.title = pid
        self.delay = delay
        self.boom = boom
        self.thread = None

    def fetch(self):
        self.thread = threading.get_ident()
        time.sleep(self.delay)
        if self.boom:
            raise RuntimeError("secret detail")
        return ProviderSnapshot(provider_id=self.id, title=self.title, ok=True, fetched_at=utc_now())


def _wait(app, cond, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end and not cond():
        app.processEvents()
        time.sleep(0.005)
    return cond()


def test_fetch_runs_off_the_ui_thread_and_is_delivered_on_it(app, monkeypatch):
    provider = _Fake("a")
    monkeypatch.setattr(fetcher, "discover_providers", lambda _s: [provider])
    got = []
    f = fetcher.BackgroundFetcher(lambda p, s: got.append((threading.get_ident(), s)))
    f.start(Settings())
    assert _wait(app, lambda: got)
    assert provider.thread != threading.get_ident()
    assert got[0][0] == threading.get_ident()
    assert got[0][1][0].ok


def test_a_slow_provider_does_not_block_the_caller(app, monkeypatch):
    monkeypatch.setattr(fetcher, "discover_providers", lambda _s: [_Fake("slow", delay=0.6)])
    got = []
    f = fetcher.BackgroundFetcher(lambda p, s: got.append(s))
    t0 = time.time()
    f.start(Settings())
    assert time.time() - t0 < 0.2
    assert f.busy
    assert _wait(app, lambda: got)


def test_a_failing_provider_becomes_an_error_snapshot_without_its_message(app, monkeypatch):
    monkeypatch.setattr(
        fetcher, "discover_providers", lambda _s: [_Fake("bad", boom=True), _Fake("ok")]
    )
    got = []
    f = fetcher.BackgroundFetcher(lambda p, s: got.append(s))
    f.start(Settings())
    assert _wait(app, lambda: got)
    bad, ok = got[0]
    assert bad.ok is False and "RuntimeError" in bad.error and "secret" not in bad.error
    assert ok.ok is True


def test_request_during_a_fetch_triggers_one_more_run(app, monkeypatch):
    calls = []

    def discover(_s):
        calls.append(1)
        return [_Fake("a", delay=0.2)]

    monkeypatch.setattr(fetcher, "discover_providers", discover)
    got = []
    f = fetcher.BackgroundFetcher(lambda p, s: got.append(s))
    f.start(Settings())
    f.start(Settings())
    f.start(Settings())
    assert _wait(app, lambda: len(got) == 2, timeout=4.0)
    assert len(calls) == 2
    assert _wait(app, lambda: not f.busy)


def test_discovery_failure_keeps_the_previous_view(app, monkeypatch):
    def boom(_s):
        raise OSError("disk")

    monkeypatch.setattr(fetcher, "discover_providers", boom)
    got = []
    f = fetcher.BackgroundFetcher(lambda p, s: got.append(s))
    f.start(Settings())
    assert _wait(app, lambda: not f.busy)
    assert got == []
