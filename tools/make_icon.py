"""Generate the Przepiórka (quail) app icon — a small QPainter vector glyph
saved as multi-size .ico (Windows) and .png (everywhere else, KDE included).

Run once at build/branding time, not at app startup:
    .venv\\Scripts\\python.exe tools\\make_icon.py
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "src" / "usage_hud" / "assets"

_BODY = QColor("#c98a4b")  # warm quail-brown
_BELLY = QColor("#e8c79a")
_DARK = QColor("#2a1c12")
_BG = QColor("#232a35")  # matches the app's dark chip theme


def draw_quail(size: int) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    s = size / 32.0  # design grid is 32x32, scaled to the requested size

    # Rounded-square backing plate so the glyph reads at any size/theme.
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_BG)
    painter.drawRoundedRect(0, 0, size, size, 7 * s, 7 * s)

    # Body: a plump tilted ellipse.
    painter.save()
    painter.translate(16.5 * s, 20 * s)
    painter.rotate(-8)
    painter.setBrush(_BODY)
    painter.drawEllipse(QPointF(0, 0), 9.5 * s, 7.2 * s)
    painter.restore()

    # Belly highlight.
    painter.save()
    painter.translate(15.5 * s, 22.5 * s)
    painter.rotate(-8)
    painter.setBrush(_BELLY)
    painter.drawEllipse(QPointF(0, 0), 6.2 * s, 4.0 * s)
    painter.restore()

    # Tail: a short upward feather fan at the back.
    tail = QPainterPath()
    tail.moveTo(25.5 * s, 15.5 * s)
    tail.quadTo(29.5 * s, 12.0 * s, 28.0 * s, 8.5 * s)
    tail.quadTo(26.0 * s, 13.0 * s, 23.5 * s, 14.5 * s)
    tail.closeSubpath()
    painter.setBrush(_BODY)
    painter.drawPath(tail)

    # Head.
    painter.setBrush(_DARK)
    head_c = QPointF(9.0 * s, 12.5 * s)
    painter.drawEllipse(head_c, 4.3 * s, 4.0 * s)

    # The signature quail topknot — a single forward-curling plume.
    plume = QPainterPath()
    plume.moveTo(9.5 * s, 8.7 * s)
    plume.cubicTo(9.0 * s, 4.5 * s, 13.0 * s, 3.0 * s, 12.5 * s, 6.5 * s)
    plume.cubicTo(12.0 * s, 5.0 * s, 9.8 * s, 6.0 * s, 10.3 * s, 9.0 * s)
    plume.closeSubpath()
    painter.setBrush(_DARK)
    painter.drawPath(plume)

    # Beak.
    beak = QPainterPath()
    beak.moveTo(5.0 * s, 12.8 * s)
    beak.lineTo(2.3 * s, 13.6 * s)
    beak.lineTo(5.0 * s, 14.4 * s)
    beak.closeSubpath()
    painter.setBrush(_DARK)
    painter.drawPath(beak)

    # Eye.
    painter.setBrush(_BELLY)
    painter.drawEllipse(QPointF(8.6 * s, 11.6 * s), 0.7 * s, 0.7 * s)

    # Legs.
    painter.setPen(_DARK)
    painter.drawLine(QPointF(12.5 * s, 26.5 * s), QPointF(11.5 * s, 29.5 * s))
    painter.drawLine(QPointF(19.5 * s, 26.5 * s), QPointF(20.5 * s, 29.5 * s))

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

    draw_quail(256).save(str(OUT_DIR / "przepiorka.png"), "PNG")

    sizes = [16, 24, 32, 48, 64, 128, 256]
    pixmaps = [draw_quail(sz) for sz in sizes]
    ico_path = OUT_DIR / "przepiorka.ico"
    write_multi_res_ico(pixmaps, ico_path)

    print(f"wrote {ico_path}")
    print(f"wrote {OUT_DIR / 'przepiorka.png'}")

    del app


if __name__ == "__main__":
    main()
