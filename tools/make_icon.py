"""Generate the Przepiórka app icon — a raven perched on a boar (the app's
own mascot plus the user's personal animal, both "woven in" per an explicit
request), in a military color palette, drawn as a clean outline above tray
scale and a solid silhouette below it. The contour and paint logic live in
usage_hud.ui.emblem_glyph — this is the STATIC branding icon only; the LIVE
tray/taskbar status icon stays a plain severity-tinted raven (usage_hud.ui.
raven_glyph, via ui/tray.py and ui/formatters.py) and must not pick up a
fixed palette here.

Run once at build/branding time, not at app startup:
    .venv\\Scripts\\python.exe tools\\make_icon.py
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from usage_hud.ui.emblem_glyph import SOLID_MAX_SIZE, paint_emblem_outline, paint_emblem_solid

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "src" / "usage_hud" / "assets"

# Military palette: deep olive plate, khaki/tan line, a muted brass accent —
# replaces the raven-only icon's blue-grey/cyan, which was a live-status
# convention (severity color) that has no place on a static branding mark.
_BG = QColor("#333a24")  # deep olive
_LINE = QColor("#cbbf8f")  # khaki/tan — the emblem itself
_ACCENT = QColor("#c9a24a")  # muted brass, the one accent dot


def draw_emblem(size: int) -> QPixmap:
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
        paint_emblem_solid(painter, s, fill_color=_LINE)
    else:
        paint_emblem_outline(painter, s, line_color=_LINE, accent_color=_ACCENT)

    painter.end()
    return pix


def _pixmap_png_bytes(pix: QPixmap) -> bytes:
    from PySide6.QtCore import QBuffer, QIODevice

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

    draw_emblem(256).save(str(OUT_DIR / "przepiorka.png"), "PNG")

    sizes = [16, 24, 32, 48, 64, 128, 256]
    pixmaps = [draw_emblem(sz) for sz in sizes]
    ico_path = OUT_DIR / "przepiorka.ico"
    write_multi_res_ico(pixmaps, ico_path)

    print(f"wrote {ico_path}")
    print(f"wrote {OUT_DIR / 'przepiorka.png'}")

    del app


if __name__ == "__main__":
    main()
