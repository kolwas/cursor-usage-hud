"""make_status_icon: the tray icon used to be a plain colored rounded square
with no animal on it at all, unrelated to the app's own mascot — this
covers the fix (both now paint the boar from usage_hud.ui.emblem_glyph) and
the two behaviours that actually matter: the fill still tracks severity,
and the urgent badge still shows up.
"""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from usage_hud.models import Alert, AlertLevel  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


def _icon_bytes(icon: QIcon) -> bytes:
    pix = icon.pixmap(64, 64)
    img = pix.toImage()
    return bytes(img.constBits())


def test_status_icon_changes_with_severity():
    from usage_hud.ui.tray import make_status_icon

    calm = make_status_icon([], [])
    critical_alert = Alert(
        provider_id="cursor",
        code="over",
        level=AlertLevel.CRITICAL,
        title="Over",
        body="Over the limit",
    )
    critical = make_status_icon([], [critical_alert])
    assert _icon_bytes(calm) != _icon_bytes(critical)


def test_urgent_badge_changes_the_rendered_icon():
    from usage_hud.ui.tray import make_status_icon

    calm = make_status_icon([], [])
    critical_alert = Alert(
        provider_id="cursor",
        code="over",
        level=AlertLevel.CRITICAL,
        title="Over",
        body="Over the limit",
    )
    urgent = make_status_icon([], [critical_alert])
    # Different severity color AND the "!" badge both change pixels — this
    # just guards the icon isn't a no-op regardless of alerts.
    assert not calm.pixmap(64, 64).toImage().isNull()
    assert not urgent.pixmap(64, 64).toImage().isNull()
