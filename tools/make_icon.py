"""Generate the Przepiórka app icon — a raven, drawn as a clean outline (not
a flat-filled illustration like the earlier quail glyph): a single stroked
silhouette path, so the mark stays legible as a tray-sized glyph instead of
depending on color contrast between several filled shapes.

Run once at build/branding time, not at app startup:
    .venv\\Scripts\\python.exe tools\\make_icon.py
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "src" / "usage_hud" / "assets"

_BG = QColor("#232a35")  # matches the app's dark chip theme
_LINE = QColor("#d7deea")  # the outline itself — everything the glyph is
_EYE = QColor("#7fd7ff")  # the one filled accent, so the mark isn't dead-eyed


def _raven_path(s: float, *, detailed: bool = True) -> QPainterPath:
    """One closed contour, side profile, facing right: rounded back, a
    strongly hooked beak (the "under-curl" right past the tip is what
    reads as raptor/corvid rather than a generic songbird bill), a
    shaggy-throat hackle, and a fanned tail — drawn on a 32x32 design grid
    and scaled by ``s``.

    ``detailed=False`` drops the throat zigzag and tail-feather notches in
    favour of smooth curves: at tray/taskbar scale those fine notches are
    thinner than a pixel and just turn into noise rather than detail — see
    ``draw_raven``.
    """
    path = QPainterPath()
    path.moveTo(3.0 * s, 18.0 * s)  # tail tip
    # back, up and over the crown
    path.quadTo(6.0 * s, 8.5 * s, 14.5 * s, 7.0 * s)
    # crown down to the base of the upper beak
    path.quadTo(19.5 * s, 7.3 * s, 23.5 * s, 9.7 * s)
    # upper beak out to the tip
    path.quadTo(27.5 * s, 10.8 * s, 30.5 * s, 13.2 * s)
    # the hook: curls back up under the tip before dropping to the chin —
    # this single notch is what makes the bill read as hooked, not straight
    path.quadTo(27.0 * s, 13.8 * s, 25.2 * s, 12.6 * s)
    path.lineTo(23.5 * s, 15.2 * s)  # chin
    if detailed:
        # shaggy throat — two soft hackle bumps, not a jagged zigzag
        path.quadTo(25.3 * s, 17.0 * s, 23.2 * s, 18.6 * s)
        path.quadTo(24.8 * s, 20.2 * s, 22.0 * s, 21.6 * s)
    else:
        path.quadTo(24.2 * s, 18.4 * s, 21.0 * s, 21.6 * s)
    # chest and belly
    path.quadTo(18.0 * s, 27.3 * s, 12.0 * s, 27.7 * s)
    path.quadTo(6.8 * s, 26.7 * s, 4.8 * s, 20.5 * s)
    if detailed:
        # tail fan: two feather notches, tucked under the back so they read
        # as feathers rather than overlapping the belly curve
        path.lineTo(7.0 * s, 19.3 * s)
        path.lineTo(2.2 * s, 21.2 * s)
        path.lineTo(5.6 * s, 17.6 * s)
    path.closeSubpath()
    return path


# Below this size a stroked outline just smears into a grey smudge — Windows
# uses 16/24px for the tray and taskbar, where individual hairline strokes
# are thinner than a pixel. Those sizes get a solid silhouette instead of
# an outline, cut from the same contour, with the eye punched out as a
# background-colour dot rather than drawn as a separate filled accent.
_SOLID_MAX_SIZE = 24


def draw_raven(size: int) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    s = size / 32.0  # design grid is 32x32, scaled to the requested size

    # Rounded-square backing plate so the glyph reads at any size/theme.
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_BG)
    painter.drawRoundedRect(0, 0, size, size, 7 * s, 7 * s)

    if size <= _SOLID_MAX_SIZE:
        path = _raven_path(s, detailed=False)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_LINE)
        painter.drawPath(path)
        painter.setBrush(_BG)
        painter.drawEllipse(QPointF(20.0 * s, 11.6 * s), max(1.0, 1.1 * s), max(1.0, 1.1 * s))
        painter.end()
        return pix

    # Above tray scale: the raven itself is stroke only, no fill — an
    # outline, not a silhouette.
    pen = QPen(_LINE)
    pen.setWidthF(max(1.1, 1.7 * s))
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(_raven_path(s, detailed=True))

    # Eye: the one filled dot, so the outline doesn't read as a dead husk.
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_EYE)
    painter.drawEllipse(QPointF(20.0 * s, 11.6 * s), 0.8 * s, 0.8 * s)

    # Legs — thin strokes, same treatment as the outline.
    painter.setPen(pen)
    painter.drawLine(QPointF(12.5 * s, 27.3 * s), QPointF(11.3 * s, 30.2 * s))
    painter.drawLine(QPointF(16.5 * s, 27.3 * s), QPointF(17.7 * s, 30.2 * s))

    painter.end()
    return pix


def _pixmap_png_bytes(pix: QPixmap) -> bytes:
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    pix.save(buf, "PNG")
    return bytes(buf.data())


def write_multi_res_ico(pixmaps: list[QPixmap], path: Path) -> None:
    """Hand-rolled ICO: Qt has no multi-resolution ICO writer, but the
    modern (Vista+) ICO format is simple enough to build directly — a
    6-byte header, one 16-byte directory entry per image, then each
    image's raw PNG bytes back to back. Windows reads PNG-compressed ICO
    entries natively, so each size stays crisp instead of one image
    being scaled for every use (taskbar vs. Explorer vs. Alt-Tab)."""
    entries = [(pix, _pixmap_png_bytes(pix)) for pix in pixmaps]
    header = struct.pack("<HHH", 0, 1, len(entries))
    dir_bytes = b""
    data_bytes = b""
    offset = 6 + 16 * len(entries)
    for pix, png in entries:
        side = pix.width()  # square icons; 0 in the format means 256
        dir_bytes += struct.pack(
            "<BBBBHHII",
            side if side < 256 else 0,
            side if side < 256 else 0,
            0,  # no palette
            0,  # reserved
            1,  # color planes
            32,  # bits per pixel
            len(png),
            offset,
        )
        data_bytes += png
        offset += len(png)
    path.write_bytes(header + dir_bytes + data_bytes)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv)

    draw_raven(256).save(str(OUT_DIR / "przepiorka.png"), "PNG")

    sizes = [16, 24, 32, 48, 64, 128, 256]
    pixmaps = [draw_raven(sz) for sz in sizes]
    ico_path = OUT_DIR / "przepiorka.ico"
    write_multi_res_ico(pixmaps, ico_path)

    print(f"wrote {ico_path}")
    print(f"wrote {OUT_DIR / 'przepiorka.png'}")

    del app


if __name__ == "__main__":
    main()
