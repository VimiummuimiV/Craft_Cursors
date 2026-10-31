"""
Generator for a unified cursor set.

Usage:   python cursors.py [output_folder]
Result: svg/, png/, cur/, preview.html, cursors.json

The shared style is controlled by the tokens in the STYLE block. Each cursor is described
only by geometry on a 32x32 grid, so changing thickness/colors rebuilds the entire set.

Dependency for PNG/.cur and preview: PyQt6 (pip install PyQt6)
"""
from __future__ import annotations

import json
import struct
import sys
from dataclasses import dataclass, replace
from pathlib import Path

# ============================== STYLE ======================================
GRID = 32            # logical cursor grid
INK = "#000000"      # outline and dark detail color
PAPER = "#ffffff"    # fill for light forms
HALO = "#ffffff"     # halo outside the outline (readable on dark backgrounds)
SW = 1.8             # thickness of all outlines and lines
H = 1.8              # halo width
CUR_SIZES = (96,)    # sizes included in .cur files
PNG_SIZE = max(CUR_SIZES)  # the PNG is exported at the largest .cur size
# ===========================================================================

ROUND = 'stroke-linecap="round" stroke-linejoin="round"'


@dataclass
class Shape:
    """A single cursor element.

    kind:
      paper - light form with a dark outline (closed path, rect, circle)
      fill  - light form whose outline is a top line drawn over it (folds stay visible)
      pline - thick light line with rounded ends and outline (fingers, thumb)
      ink   - solid dark form
      line  - dark line with thickness w (symbols +, -, ^, etc.)
    top: drawn above everything else, without a halo (details inside forms)
    """
    el: str
    geom: str
    kind: str
    w: float = 0.0
    top: bool = False
    xf: str = ""

    def tag(self, attrs: str) -> str:
        t = f' transform="{self.xf}"' if self.xf else ""
        return f"<{self.el} {self.geom} {attrs}{t}/>"


def render(shapes: list[Shape]) -> str:
    out: list[str] = []
    # 1) halo
    for s in shapes:
        if s.top:
            continue
        if s.kind == "paper":
            a = f'fill="{HALO}" stroke="{HALO}" stroke-width="{2 * (SW + H)}" {ROUND}'
        elif s.kind == "pline":
            a = f'fill="none" stroke="{HALO}" stroke-width="{s.w + 2 * (SW + H)}" {ROUND}'
        elif s.kind == "ink":
            a = f'fill="{HALO}" stroke="{HALO}" stroke-width="{2 * H}" {ROUND}'
        else:
            a = f'fill="none" stroke="{HALO}" stroke-width="{s.w + 2 * H}" {ROUND}'
        out.append(s.tag(a))
    # 2) outline / dark forms
    for s in shapes:
        if s.top:
            continue
        if s.kind == "paper":
            a = f'fill="{INK}" stroke="{INK}" stroke-width="{2 * SW}" {ROUND}'
        elif s.kind == "pline":
            a = f'fill="none" stroke="{INK}" stroke-width="{s.w + 2 * SW}" {ROUND}'
        elif s.kind == "ink":
            a = f'fill="{INK}" stroke="none"'
        else:
            a = f'fill="none" stroke="{INK}" stroke-width="{s.w}" {ROUND}'
        out.append(s.tag(a))
    # 3) light fill on top (eraser for internal intersection lines)
    for s in shapes:
        if s.top:
            continue
        if s.kind in ("paper", "fill"):
            out.append(s.tag(f'fill="{PAPER}" stroke="none"'))
        elif s.kind == "pline":
            out.append(s.tag(f'fill="none" stroke="{PAPER}" stroke-width="{s.w}" {ROUND}'))
    # 4) top details
    for s in shapes:
        if not s.top:
            continue
        if s.kind == "ink":
            out.append(s.tag(f'fill="{INK}" stroke="none"'))
        else:
            out.append(s.tag(f'fill="none" stroke="{INK}" stroke-width="{s.w}" {ROUND}'))
    return "\n".join(out)


# ============================ GEOMETRY ====================================

def arrow() -> list[Shape]:
    """Default pointer: rounded triangle, minimal points (two per corner), the top-left corner is the hotspot."""
    d = ("M6 5.7 "
         "C6 3.8 7.7 3.8 8.6 4.6 "          # top-left corner (2 points)
         "L22.06 16.8 "                     # upper edge
         "C22.8 17.5 22.6 19 21.7 19.2 "    # right tip (2 points)
         "C15.7 21.1 11.1 23.8 8.3 26.6 "   # concave lower edge
         "C7.6 27.3 6 27 6 25.4 Z")         # bottom-left corner (2 points), left edge closes
    return [Shape("path", f'd="{d}"', "paper")]


def zoom(sign: str) -> list[Shape]:
    cx = cy = 13
    sh = [
        Shape("circle", f'cx="{cx}" cy="{cy}" r="8.5"', "paper"),
        # handle: flat end hidden under the lens outline, round end on the far side
        Shape("path", 'd="M18.16 21.27 L21.27 18.16 L29.06 25.94 A2.2 2.2 0 0 1 25.94 29.06 Z"', "ink"),
        Shape("path", f'd="M{cx - 3.8} {cy} H{cx + 3.8}"', "line", SW, top=True),
    ]
    if sign == "+":
        sh.append(Shape("path", f'd="M{cx} {cy - 3.8} V{cy + 3.8}"', "line", SW, top=True))
    return sh


def eyedropper() -> list[Shape]:
    xf = "translate(3.8 28.2) rotate(45)"
    return [
        Shape("path", 'd="M0 0 L-2.7 -7 L-2.7 -17.5 L2.7 -17.5 L2.7 -7 Z"', "paper", xf=xf),
        Shape("rect", 'x="-4.5" y="-21.5" width="9" height="4.5" rx="1.2"', "paper", xf=xf),
        Shape("rect", 'x="-3.5" y="-31" width="7" height="10.5" rx="3.5"', "ink", xf=xf),
    ]


# Hands are in 32x32 grid coordinates: the open hand is fitted to the grid with outline and halo,
# the closed hand has the same scale and anchor (two states of one cursor, so it is not enlarged).
_HAND_OPEN = (
    "M 14.26 29.79 C 11.35 29.79 7.93 23.27 5.41 20.82 C 3.97 19.42 1.67 18.92 2.53 16.57 "
    "C 3.23 14.67 6.18 14.36 8.38 15.76 C 9.97 16.77 11.25 18.09 11.25 18.09 "
    "C 11.25 18.09 8.77 9.05 8.42 7.73 C 8.07 6.41 8.85 5.07 10.17 4.7 "
    "C 11.48 4.34 12.82 5 13.21 6.45 C 13.6 7.91 14.96 12.91 14.96 12.91 "
    "C 14.96 12.91 14.25 6.06 14.13 4.7 C 14 3.35 15.14 2.32 16.5 2.21 "
    "C 17.75 2.12 19.03 3.33 19.08 4.7 C 19.13 6.07 19.33 12.72 19.33 12.72 "
    "C 19.33 12.72 20 7.15 20.15 5.79 C 20.31 4.39 21.61 3.68 22.93 3.95 "
    "C 24.2 4.21 24.88 5.74 24.66 7.09 C 24.46 8.41 23.51 14 23.51 14 "
    "C 23.51 14 24.78 9.85 25.14 8.72 C 25.55 7.42 27.15 7.04 28.28 7.47 "
    "C 29.51 7.94 29.97 9.39 29.43 11.2 C 28.89 13.02 28.42 14.54 27.59 17.08 "
    "C 27.06 18.7 27.21 22.62 25.84 24.99 C 23.12 29.67 22.4 29.79 20.36 29.79 L 14.26 29.79 Z"
)
_HAND_CLOSED = (
    "M 14.26 29.79 C 11.91 29.79 7.78 23.66 7.18 20.2 C 6.89 18.53 10.6 15.77 10.6 15.77 "
    "L 11.25 18.09 C 11.25 18.09 10.65 15.95 10.31 14.69 C 9.97 13.42 9.96 11.89 11.75 11.22 "
    "C 13.03 10.74 14.61 11.59 14.96 12.91 L 14.63 11.63 C 14.41 10.3 15.66 9.12 17.03 9.12 "
    "C 18.39 9.12 19.51 10.07 19.51 11.43 L 19.33 12.72 C 19.33 12.72 19.35 12.79 19.51 11.43 "
    "C 19.66 10.03 21.31 9.33 22.57 9.76 C 23.69 10.13 24.37 11.38 24 12.61 "
    "C 23.78 13.33 23.51 14 23.51 14 C 23.51 14 24.57 11.58 26.77 12.81 "
    "C 27.98 13.48 27.93 15.83 27.59 17.08 C 27.14 18.72 27.21 22.62 25.84 24.99 "
    "C 23.12 29.67 21.42 29.79 20.36 29.79 L 14.26 29.79 Z"
)


def _hand(d: str) -> list[Shape]:
    g = f'd="{d}"'
    return [Shape("path", g, "fill", SW), Shape("path", g, "line", SW, top=True)]


def hand_open() -> list[Shape]:
    """Open hand."""
    return _hand(_HAND_OPEN)


def hand_closed() -> list[Shape]:
    """Closed hand: the same cursor, fingers bent."""
    return _hand(_HAND_CLOSED)


_NIB_XF = "translate(3.8 28.2) rotate(45)"
_NIB_SLIT = 13.14  # slit length from the tip; the dot sits at its end


def pen_nib() -> list[Shape]:
    xf = _NIB_XF
    return [
        Shape("path", 'd="M0 0 L-5.4 -11.79 Q-6 -17.97 -4.2 -20.44 L4.2 -20.44 Q6 -17.97 5.4 -11.79 Z"',
              "paper", xf=xf),
        Shape("rect", 'x="-4.2" y="-31" width="8.4" height="11.68" rx="1.6"', "ink", xf=xf),
        Shape("path", f'd="M0 0 V{-_NIB_SLIT}"', "line", SW, top=True, xf=xf),
        Shape("circle", f'cx="0" cy="{-_NIB_SLIT}" r="1.65"', "ink", top=True, xf=xf),
    ]


def crosshair(cx: float = 16, cy: float = 16, arm: float = 13.5, gap: float = 3.2) -> list[Shape]:
    """Precision crosshair: four long thin arms with an open center, so the pixel under the
    hotspot stays visible and the cursor does not read as a '+' sign. (cx, cy) is the hotspot."""
    d = (f"M{cx - arm} {cy} H{cx - gap} M{cx + gap} {cy} H{cx + arm} "
         f"M{cx} {cy - arm} V{cy - gap} M{cx} {cy + gap} V{cy + arm}")
    return [Shape("path", f'd="{d}"', "line", SW)]


# Extra elements ("badges") are attached next to a base cursor; the base is never shrunk.
# If an element does not fit into the base's 32x32 grid, the canvas of that cursor grows to the right
# and down (the hotspot stays where it was, the origin is the top left corner).
# Every glyph is drawn once around its own origin (0, 0); where it sits is set per base in BADGE_ANCHOR:
#   "shared" - universal marks (+, -), usable on any cursor;
#   "<base>" - marks of one tool, so a bulky mark never constrains the others.
# add_badged() looks in the base's group first, then in "shared".
BADGES: dict[str, dict[str, list[Shape]]] = {
    "shared": {
        "plus": [Shape("path", 'd="M-2.8 0 H2.8 M0 -2.8 V2.8"', "line", SW)],
        "minus": [Shape("path", 'd="M-2.8 0 H2.8"', "line", SW)],
    },
    "pen": {
        "wave": [Shape("path", 'd="M-3.8 1.4 Q-2.15 -1.4 -0.5 1.4 T2.8 1.4"', "line", SW)],
        "curve": [Shape("path", 'd="M-4.6 2.8 C-1.4 2.8 -1.4 -3.6 2.8 -3.6"', "line", SW)],
        "caret": [Shape("path", 'd="M-3 2.6 L0 -1.8 L2.8 2.6"', "line", SW)],
        "ring": [Shape("circle", 'cx="0" cy="0" r="2.5"', "line", SW)],
    },
    "crosshair": {
        # artboard: rounded frame + short header bar (Affinity-like proportions)
        "artboard": [
            Shape("rect", 'x="-7.4" y="-7.4" width="14.8" height="14.8" rx="2.0"', "paper"),
            Shape("path", 'd="M-3.6 -3.9 H3.6"', "line", SW, top=True),
        ],
    },
}

# Badge origin on the grid per base cursor; DEFAULT is used for bases not listed.
# The pen nib occupies the diagonal, so its badges sit lower in the corner: the halos must not
# touch the nib, and the outer halo stays inside the grid. The crosshair keeps its full size;
# the artboard icon is placed further south-east with clear air from the arms (and their halos).
BADGE_ANCHOR_DEFAULT = (24.5, 24.5)
BADGE_ANCHOR = {"pen": (26.4, 26.4), "crosshair": (34.0, 34.0)}

# Canvas size in grid units, only for cursors that do not fit 32x32 (name -> (width, height)).
CANVAS: dict[str, tuple[float, float]] = {}


# name -> (hotspot on the 32x32 grid, shape factory)
CURSORS: dict[str, tuple[tuple[int, int], callable]] = {
    "arrow": ((7, 4), arrow),
    "zoom_in": ((13, 13), lambda: zoom("+")),
    "zoom_out": ((13, 13), lambda: zoom("-")),
    "eyedropper": ((4, 28), eyedropper),
    "hand_open": ((16, 16), hand_open),
    "hand_closed": ((16, 16), hand_closed),
    "pen": ((4, 28), pen_nib),
    "crosshair": ((16, 16), crosshair),
}


def add_badged(name: str, base: str, badge: str, canvas: tuple[float, float] | None = None) -> None:
    """Registers cursor `name` = base cursor + badge. The hotspot is taken from the base.
    canvas: size in grid units if the badge goes beyond the base's 32x32 grid."""
    hot, base_factory = CURSORS[base]
    shapes = BADGES.get(base, {}).get(badge) or BADGES["shared"][badge]
    ax, ay = BADGE_ANCHOR.get(base, BADGE_ANCHOR_DEFAULT)
    placed = [replace(s, xf=f"translate({ax} {ay})") for s in shapes]
    CURSORS[name] = (hot, lambda: base_factory() + placed)
    if canvas:
        CANVAS[name] = canvas


for _name, (_base, _badge) in {
    "pen_freeform": ("pen", "wave"),
    "pen_curvature": ("pen", "curve"),
    "pen_add": ("pen", "plus"),
    "pen_delete": ("pen", "minus"),
    "pen_convert": ("pen", "caret"),
    "pen_close": ("pen", "ring"),
}.items():
    add_badged(_name, _base, _badge)
add_badged("artboard", "crosshair", "artboard", canvas=(46, 46))
# other tools reuse the same badges, e.g.: add_badged("select_add", "select", "plus")


def canvas_size(name: str) -> tuple[float, float]:
    return CANVAS.get(name, (GRID, GRID))


# ============================== BUILD ======================================

def build_svg(name: str, size: int = GRID) -> str:
    """size = pixels per GRID units, so the scale is the same for every canvas."""
    hot, factory = CURSORS[name]
    cw, ch = canvas_size(name)
    body = render(factory())
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{cw * size / GRID:g}" '
            f'height="{ch * size / GRID:g}" viewBox="0 0 {cw:g} {ch:g}">\n'
            f'<!-- hotspot: {hot[0]},{hot[1]} -->\n{body}\n</svg>\n')


def hotspot(name: str, px: int) -> tuple[int, int]:
    hx, hy = CURSORS[name][0]
    return round(hx * px / GRID), round(hy * px / GRID)


# --------------------------- Qt: PNG, .cur, QCursor ------------------------

def _qt():
    from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, Qt
    from PyQt6.QtGui import QGuiApplication, QImage, QPainter
    from PyQt6.QtSvg import QSvgRenderer
    if QGuiApplication.instance() is None:
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        global _app
        _app = QGuiApplication([])
    return QBuffer, QByteArray, QIODevice, Qt, QImage, QPainter, QSvgRenderer


def image_side(name: str, px: int) -> int:
    """Side of the square image: px pixels per GRID units, the larger canvas side decides."""
    return round(max(canvas_size(name)) * px / GRID)


def render_image(name: str, px: int):
    """Returns a square QImage; the cursor sits in its top left corner at px pixels per GRID units
    (a bigger canvas stays transparent below/right, so the hotspot position is the same)."""
    QBuffer, QByteArray, QIODevice, Qt, QImage, QPainter, QSvgRenderer = _qt()
    from PyQt6.QtCore import QRectF
    cw, ch = canvas_size(name)
    r = QSvgRenderer(QByteArray(build_svg(name).encode("utf-8")))
    side = image_side(name, px)
    img = QImage(side, side, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    r.render(p, QRectF(0, 0, cw * px / GRID, ch * px / GRID))
    p.end()
    return img


def png_bytes(img) -> bytes:
    QBuffer, QByteArray, QIODevice, *_ = _qt()
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)


def write_cur(path: Path, entries: list[tuple[int, int, int, bytes]]) -> None:
    """entries: (px, hotspot_x, hotspot_y, png_bytes). PNG inside .cur - Vista+."""
    n = len(entries)
    head = struct.pack("<HHH", 0, 2, n)
    offset = 6 + 16 * n
    dirs, blobs = b"", b""
    for px, hx, hy, png in entries:
        dim = px if px < 256 else 0
        dirs += struct.pack("<BBBBHHII", dim, dim, 0, 0, hx, hy, len(png), offset + len(blobs))
        blobs += png
    path.write_bytes(head + dirs + blobs)


def qcursor(name: str, size: int = 32):
    """Ready-to-use QCursor for PyQt6: widget.setCursor(qcursor("pen_add"))"""
    from PyQt6.QtGui import QCursor, QPixmap
    hx, hy = hotspot(name, size)
    return QCursor(QPixmap.fromImage(render_image(name, size)), hx, hy)


# ------------------------------- preview ------------------------------------

def preview_html() -> str:
    cards = []
    actual_preview_size = 24
    for name in CURSORS:
        hx, hy = CURSORS[name][0]
        cw, ch = canvas_size(name)
        svg = build_svg(name, 96)
        # the same scale for every canvas: 3 px per grid unit (big), actual_preview_size / GRID (compact)
        stage = f'style="width:{cw * 3:g}px;height:{ch * 3:g}px"'
        side = max(cw, ch) * actual_preview_size / GRID
        actual_image = (
            f'<img src="png/{name}_{PNG_SIZE}.png" width="{side:g}" height="{side:g}" alt="">')
        actual_stage = f'style="width:{side:g}px;height:{side:g}px"'
        hot = f'<i style="left:{hx * 3}px;top:{hy * 3}px"></i>'
        actual_hot = (
            f'<i style="left:{hx * actual_preview_size / GRID:g}px;'
            f'top:{hy * actual_preview_size / GRID:g}px"></i>')
        cards.append(
            f'<div class="card">'
            f'<div class="row">'
            f'<div class="panel light"><div class="stage" {stage}>{svg}{hot}</div></div>'
            f'<div class="panel dark"><div class="stage" {stage}>{svg}{hot}</div></div>'
            f'</div>'
            f'<div class="meta">'
            f'<div class="name">{name}</div>'
            f'<div class="hotspot">hotspot {hx},{hy}</div>'
            f'</div>'
            f'<div class="actual-label">Compact preview ({actual_preview_size}x{actual_preview_size})</div>'
            f'<div class="row actual-row">'
            f'<div class="panel actual-panel light"><div class="actual-stage" {actual_stage}>{actual_image}{actual_hot}</div></div>'
            f'<div class="panel actual-panel dark"><div class="actual-stage" {actual_stage}>{actual_image}{actual_hot}</div></div>'
            f'</div>'
            f'</div>')
    styles = """<style>
	/* Page layout */
	body {
		font: 14px 'Segoe UI', Arial, sans-serif;
		margin: 24px;
		background: #888;
		display: grid;
		grid-template-columns: repeat(auto-fill, 260px);
		gap: 16px;
		align-items: start;
	}

	/* Cursor cards */
	.card {
		background: rgba(255, 255, 255, .18);
		padding: 10px 10px 8px;
		border-radius: 10px;
		box-sizing: border-box;
		color: #111;
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.row {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 8px;
	}

	.panel {
		width: 100%;
		aspect-ratio: 1;
		display: grid;
		place-items: center;
		border-radius: 8px;
		overflow: hidden;
		box-sizing: border-box;
	}

	/* Light and dark preview backgrounds */
	.light { background: #f1f1f1; }
	.dark { background: #262626; }

	/* Enlarged cursor preview */
	/* the size of .stage is set inline from the canvas of each cursor */
	.stage {
		position: relative;
	}

	.stage svg {
		display: block;
	}

	.stage i {
		position: absolute;
		width: 5px;
		height: 5px;
		margin: -2px 0 0 -2px;
		border-radius: 50%;
		background: #e0245e;
	}

	/* Actual-size cursor preview */
	.actual-label {
		font-size: 12px;
		font-weight: 600;
		line-height: 1.2;
		color: #333;
	}

	.actual-panel {
		aspect-ratio: auto;
		height: 48px;
	}

	.actual-stage {
		position: relative;
	}

	.actual-stage img {
		display: block;
		image-rendering: auto;
	}

	.actual-stage i {
		position: absolute;
		width: 2px;
		height: 2px;
		margin: -1px 0 0 -1px;
		border-radius: 50%;
		background: #e0245e;
	}

	/* Cursor name and hotspot metadata */
	.meta {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
	}

	.name {
		font-size: 15px;
		font-weight: 600;
		line-height: 1.2;
		letter-spacing: .01em;
		color: #111;
		overflow-wrap: anywhere;
	}

	.hotspot {
		font-size: 12px;
		line-height: 1.2;
		color: #2c2c2c;
		opacity: .8;
	}
</style>"""
    return "<!doctype html><meta charset=utf-8><title>Cursors</title>" + styles + "".join(cards)


def contact_sheet(path: Path) -> None:
    """Quick-check PNG sheet: light/dark background, red dot = hotspot."""
    QBuffer, QByteArray, QIODevice, Qt, QImage, QPainter, QSvgRenderer = _qt()
    from PyQt6.QtGui import QColor
    names = list(CURSORS)
    cols, px, panel = 4, 96, 124          # panel fits the biggest canvas at the same scale
    cell, row_h = 2 * panel + 20, panel + 20
    rows = (len(names) + cols - 1) // cols
    img = QImage(cols * cell, rows * row_h, QImage.Format.Format_ARGB32)
    img.fill(QColor("#888888"))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    for i, n in enumerate(names):
        x0, y0 = (i % cols) * cell + 10, (i // cols) * row_h + 8
        p.fillRect(x0, y0, panel, panel, QColor("#f1f1f1"))
        p.fillRect(x0 + panel, y0, panel, panel, QColor("#262626"))
        c = render_image(n, px)
        hx, hy = hotspot(n, px)
        for bx in (x0 + 7, x0 + panel + 7):
            p.drawImage(bx, y0 + 7, c)
            p.setBrush(QColor("#e0245e"))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(bx + hx - 2, y0 + 7 + hy - 2, 5, 5)
    p.end()
    img.save(str(path))


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "cursors_out")
    for d in ("svg", "png", "cur"):
        (out / d).mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name in CURSORS:
        (out / "svg" / f"{name}.svg").write_text(build_svg(name), encoding="utf-8")
        entries = []
        for px in CUR_SIZES:
            png = png_bytes(render_image(name, px))
            if px == PNG_SIZE:
                (out / "png" / f"{name}_{px}.png").write_bytes(png)
            else:
                stale_png = out / "png" / f"{name}_{px}.png"
                if stale_png.exists():
                    stale_png.unlink()
            hx, hy = hotspot(name, px)
            entries.append((image_side(name, px), hx, hy, png))
        write_cur(out / "cur" / f"{name}.cur", entries)
        manifest[name] = {
            "hotspot_32": CURSORS[name][0],
            "canvas": canvas_size(name),
        }
    (out / "cursors.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out / "preview.html").write_text(preview_html(), encoding="utf-8")
    contact_sheet(out / "sheet.png")
    print(f"ready: {len(CURSORS)} cursors -> {out.resolve()}")


if __name__ == "__main__":
    main()