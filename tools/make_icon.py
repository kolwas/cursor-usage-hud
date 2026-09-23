"""Generate the Przepiórka app icon — a raven, drawn as a clean outline (not
a flat-filled illustration like the earlier quail glyph). The contour and
paint logic live in usage_hud.ui.raven_glyph, shared with the live tray
status icon (ui/tray.py) so both actually draw the same bird.

Run once at build/branding time, not at app startup:
    .venv\\Scripts\\python.exe tools\\make_icon.py
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from usage_hud.ui.raven_glyph import SOLID_MAX_SIZE, paint_raven_outline, paint_raven_solid

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "src" / "usage_hud" / "assets"

_BG = QColor("#232a35")  # matches the app's dark chip theme
_LINE = QColor("#d7deea")  # the outline itself — everything the glyph is
_EYE = QColor("#7fd7ff")  # the one filled accent, so the mark isn't dead-eyed


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

    if size <= SOLID_MAX_SIZE:
        paint_raven_solid(painter, s, fill_color=_LINE, eye_punch_color=_BG)
    else:
        paint_raven_outline(painter, s, line_color=_LINE, eye_color=_EYE, legs=True)

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
