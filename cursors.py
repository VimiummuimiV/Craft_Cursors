"""
Generator for a unified cursor set.

Usage:   python cursors.py [output_folder]
Result: svg/, png/, cur/, preview.html, cursors.json

The shared style is controlled by the tokens in the STYLE block (THEME selects dark/light
palette). Each cursor is described only by geometry on a 32x32 grid, so changing
thickness/colors rebuilds the entire set.

Dependency for PNG/.cur and preview: PyQt6 (pip install PyQt6)
"""
from __future__ import annotations

import json
import math
import struct
import sys
from dataclasses import dataclass, replace
from pathlib import Path

# ============================== STYLE ======================================
GRID = 32            # logical cursor grid
SW = 1.8             # thickness of all outlines and lines
H = 1.8              # halo width
CUR_SIZES = (96,)    # sizes included in .cur files
PNG_SIZE = max(CUR_SIZES)  # the PNG is exported at the largest .cur size

# Color themes: "dark" = white outline on black paper (default), "light" = black on white
THEMES = {
    "dark":  {"ink": "#ffffff", "paper": "#000000", "halo": "#000000"},
    "light": {"ink": "#000000", "paper": "#ffffff", "halo": "#ffffff"},
}
THEME = "dark"       # default export theme; change to "light" for the inverse
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


def render(shapes: list[Shape], theme: str | None = None) -> str:
    """theme: 'dark' | 'light' | None (= THEME)."""
    t = THEMES[theme or THEME]
    ink, paper, halo = t["ink"], t["paper"], t["halo"]
    out: list[str] = []
    # 1) halo
    for s in shapes:
        if s.top:
            continue
        if s.kind == "paper":
            a = f'fill="{halo}" stroke="{halo}" stroke-width="{2 * (SW + H)}" {ROUND}'
        elif s.kind == "pline":
            a = f'fill="none" stroke="{halo}" stroke-width="{s.w + 2 * (SW + H)}" {ROUND}'
        elif s.kind == "ink":
            a = f'fill="{halo}" stroke="{halo}" stroke-width="{2 * H}" {ROUND}'
        else:
            a = f'fill="none" stroke="{halo}" stroke-width="{s.w + 2 * H}" {ROUND}'
        out.append(s.tag(a))
    # 2) outline / dark forms
    for s in shapes:
        if s.top:
            continue
        if s.kind == "paper":
            a = f'fill="{ink}" stroke="{ink}" stroke-width="{2 * SW}" {ROUND}'
        elif s.kind == "pline":
            a = f'fill="none" stroke="{ink}" stroke-width="{s.w + 2 * SW}" {ROUND}'
        elif s.kind == "ink":
            a = f'fill="{ink}" stroke="none"'
        else:
            a = f'fill="none" stroke="{ink}" stroke-width="{s.w}" {ROUND}'
        out.append(s.tag(a))
    # 3) light fill on top (eraser for internal intersection lines)
    for s in shapes:
        if s.top:
            continue
        if s.kind in ("paper", "fill"):
            out.append(s.tag(f'fill="{paper}" stroke="none"'))
        elif s.kind == "pline":
            out.append(s.tag(f'fill="none" stroke="{paper}" stroke-width="{s.w}" {ROUND}'))
    # 4) top details
    for s in shapes:
        if not s.top:
            continue
        if s.kind == "ink":
            out.append(s.tag(f'fill="{ink}" stroke="none"'))
        else:
            out.append(s.tag(f'fill="none" stroke="{ink}" stroke-width="{s.w}" {ROUND}'))
    return "\n".join(out)


# ============================ GEOMETRY ====================================

def _path(*segments: str) -> str:
    """Joins named path segments into one path string."""
    return " ".join(segments)


def path_shape(path_data: str, kind: str, width: float = 0.0, top: bool = False, xf: str = "") -> Shape:
    return Shape("path", f'd="{path_data}"', kind, width, top, xf)


def _number(value: float) -> str:
    return f"{round(value, 2) + 0.0:g}"


def _direction(origin: tuple[float, float], target: tuple[float, float]) -> tuple[float, float, float]:
    """Unit vector from origin to target and the distance between them."""
    delta_x, delta_y = target[0] - origin[0], target[1] - origin[1]
    distance = math.hypot(delta_x, delta_y)
    return delta_x / distance, delta_y / distance, distance


def rounded_polygon(points: list[tuple[float, float]], radius: float | list[float]) -> str:
    """Closed path through `points` with every corner replaced by a circular arc.
    radius is shared by all corners or given per corner; 0 keeps a corner sharp."""
    count = len(points)
    radii = [radius] * count if isinstance(radius, (int, float)) else list(radius)
    segments: list[str] = []
    for index, (corner, corner_radius) in enumerate(zip(points, radii)):
        previous_x, previous_y, previous_length = _direction(corner, points[index - 1])
        next_x, next_y, next_length = _direction(corner, points[(index + 1) % count])
        command = "M" if index == 0 else "L"
        if corner_radius == 0:
            segments.append(f"{command}{_number(corner[0])} {_number(corner[1])}")
            continue
        half_angle = math.acos(max(-1.0, min(1.0, previous_x * next_x + previous_y * next_y))) / 2
        cut = min(corner_radius / math.tan(half_angle), previous_length / 2, next_length / 2)
        arc_radius = cut * math.tan(half_angle)
        turn = (-previous_x) * next_y - (-previous_y) * next_x
        start = (corner[0] + previous_x * cut, corner[1] + previous_y * cut)
        end = (corner[0] + next_x * cut, corner[1] + next_y * cut)
        segments.append(
            f"{command}{_number(start[0])} {_number(start[1])} "
            f"A{_number(arc_radius)} {_number(arc_radius)} 0 0 {int(turn > 0)} {_number(end[0])} {_number(end[1])}")
    return _path(*segments, "Z")


_SPARKLE_INNER_RATIO = 0.4      # inner point radius / outer point radius
_SPARKLE_ROUNDING_RATIO = 0.16  # corner radius / outer point radius


def sparkle(center_x: float, center_y: float, outer_radius: float) -> str:
    """Four-point star: 4 outer and 4 inner points, all 8 corners rounded."""
    points = []
    for index in range(8):
        radius = outer_radius if index % 2 == 0 else outer_radius * _SPARKLE_INNER_RATIO
        angle = math.radians(-90 + 45 * index)
        points.append((center_x + radius * math.cos(angle), center_y + radius * math.sin(angle)))
    return rounded_polygon(points, outer_radius * _SPARKLE_ROUNDING_RATIO)


def arrow() -> list[Shape]:
    """Default pointer: rounded triangle, minimal points (two per corner), the top-left corner is the hotspot."""
    start = "M6 5.7"
    top_left_corner = "C6 3.8 7.7 3.8 8.6 4.6"
    upper_edge = "L22.06 16.8"
    right_tip = "C22.8 17.5 22.6 19 21.7 19.2"
    concave_lower_edge = "C15.7 21.1 11.1 23.8 8.3 26.6"
    bottom_left_corner = "C7.6 27.3 6 27 6 25.4"  # the left edge closes the path
    outline = _path(start, top_left_corner, upper_edge, right_tip, concave_lower_edge, bottom_left_corner, "Z")
    return [path_shape(outline, "paper")]


_LENS_CENTER = 13
_LENS_RADIUS = 8.5
_ZOOM_SIGN_ARM = 3.8


def zoom(sign: str) -> list[Shape]:
    center, arm = _LENS_CENTER, _ZOOM_SIGN_ARM
    # handle: flat end hidden under the lens outline, round end on the far side
    handle = _path("M18.16 21.27", "L21.27 18.16", "L29.06 25.94", "A2.2 2.2 0 0 1 25.94 29.06", "Z")
    horizontal_bar = f"M{center - arm} {center} H{center + arm}"
    vertical_bar = f"M{center} {center - arm} V{center + arm}"
    shapes = [
        Shape("circle", f'cx="{center}" cy="{center}" r="{_LENS_RADIUS}"', "paper"),
        path_shape(handle, "ink"),
        path_shape(horizontal_bar, "line", SW, top=True),
    ]
    if sign == "+":
        shapes.append(path_shape(vertical_bar, "line", SW, top=True))
    return shapes


# Eyedropper and pen nib are drawn along the local -y axis from the tip at the hotspot, tilted 45 degrees
_TOOL_TIP_XF = "translate(3.8 28.2) rotate(45)"


def eyedropper() -> list[Shape]:
    tip, neck, tube_end = "M0 0", "-7", "-17.5"
    tube = _path(tip, f"L-2.7 {neck}", f"L-2.7 {tube_end}", f"L2.7 {tube_end}", f"L2.7 {neck}", "Z")
    return [
        path_shape(tube, "paper", xf=_TOOL_TIP_XF),
        Shape("rect", 'x="-4.5" y="-21.5" width="9" height="4.5" rx="1.2"', "paper", xf=_TOOL_TIP_XF),
        Shape("rect", 'x="-3.5" y="-31" width="7" height="10.5" rx="3.5"', "ink", xf=_TOOL_TIP_XF),
    ]


# Hands are in 32x32 grid coordinates: the open hand is fitted to the grid with outline and halo,
# the closed hand has the same scale and anchor (two states of one cursor, so it is not enlarged).
# Both outlines start and end at the wrist; each part is listed in drawing order.
_HAND_START = "M 14.26 29.79"
_HAND_END = "L 14.26 29.79 Z"

_HAND_OPEN_PARTS = {
    "wrist_to_thumb": "C 11.35 29.79 7.93 23.27 5.41 20.82",
    "thumb": "C 3.97 19.42 1.67 18.92 2.53 16.57 C 3.23 14.67 6.18 14.36 8.38 15.76 "
             "C 9.97 16.77 11.25 18.09 11.25 18.09",
    "index_finger": "C 11.25 18.09 8.77 9.05 8.42 7.73 C 8.07 6.41 8.85 5.07 10.17 4.7 "
                    "C 11.48 4.34 12.82 5 13.21 6.45 C 13.6 7.91 14.96 12.91 14.96 12.91",
    "middle_finger": "C 14.96 12.91 14.25 6.06 14.13 4.7 C 14 3.35 15.14 2.32 16.5 2.21 "
                     "C 17.75 2.12 19.03 3.33 19.08 4.7 C 19.13 6.07 19.33 12.72 19.33 12.72",
    "ring_finger": "C 19.33 12.72 20 7.15 20.15 5.79 C 20.31 4.39 21.61 3.68 22.93 3.95 "
                   "C 24.2 4.21 24.88 5.74 24.66 7.09 C 24.46 8.41 23.51 14 23.51 14",
    "little_finger": "C 23.51 14 24.78 9.85 25.14 8.72 C 25.55 7.42 27.15 7.04 28.28 7.47 "
                     "C 29.51 7.94 29.97 9.39 29.43 11.2 C 28.89 13.02 28.42 14.54 27.59 17.08",
    "palm_to_wrist": "C 27.06 18.7 27.21 22.62 25.84 24.99 C 23.12 29.67 22.4 29.79 20.36 29.79",
}
_HAND_CLOSED_PARTS = {
    "wrist_to_thumb": "C 11.91 29.79 7.78 23.66 7.18 20.2",
    "thumb": "C 6.89 18.53 10.6 15.77 10.6 15.77 L 11.25 18.09",
    "index_finger": "C 11.25 18.09 10.65 15.95 10.31 14.69 C 9.97 13.42 9.96 11.89 11.75 11.22 "
                    "C 13.03 10.74 14.61 11.59 14.96 12.91",
    "middle_finger": "L 14.63 11.63 C 14.41 10.3 15.66 9.12 17.03 9.12 C 18.39 9.12 19.51 10.07 19.51 11.43",
    "ring_finger": "L 19.33 12.72 C 19.33 12.72 19.35 12.79 19.51 11.43 C 19.66 10.03 21.31 9.33 22.57 9.76 "
                   "C 23.69 10.13 24.37 11.38 24 12.61 C 23.78 13.33 23.51 14 23.51 14",
    "little_finger": "C 23.51 14 24.57 11.58 26.77 12.81 C 27.98 13.48 27.93 15.83 27.59 17.08",
    "palm_to_wrist": "C 27.14 18.72 27.21 22.62 25.84 24.99 C 23.12 29.67 21.42 29.79 20.36 29.79",
}


def _hand(parts: dict[str, str]) -> list[Shape]:
    outline = _path(_HAND_START, *parts.values(), _HAND_END)
    return [path_shape(outline, "fill", SW), path_shape(outline, "line", SW, top=True)]


def hand_open() -> list[Shape]:
    """Open hand."""
    return _hand(_HAND_OPEN_PARTS)


def hand_closed() -> list[Shape]:
    """Closed hand: the same cursor, fingers bent."""
    return _hand(_HAND_CLOSED_PARTS)


_NIB_SLIT = 13.14  # slit length from the tip; the dot sits at its end


def pen_nib() -> list[Shape]:
    tip = "M0 0"
    left_flank = "L-5.4 -11.79"
    left_shoulder = "Q-6 -17.97 -4.2 -20.44"
    top_edge = "L4.2 -20.44"
    right_shoulder = "Q6 -17.97 5.4 -11.79"
    nib = _path(tip, left_flank, left_shoulder, top_edge, right_shoulder, "Z")
    return [
        path_shape(nib, "paper", xf=_TOOL_TIP_XF),
        Shape("rect", 'x="-4.2" y="-31" width="8.4" height="11.68" rx="1.6"', "ink", xf=_TOOL_TIP_XF),
        path_shape(f"M0 0 V{-_NIB_SLIT}", "line", SW, top=True, xf=_TOOL_TIP_XF),
        Shape("circle", f'cx="0" cy="{-_NIB_SLIT}" r="1.65"', "ink", top=True, xf=_TOOL_TIP_XF),
    ]


def crosshair(cx: float = 16, cy: float = 16, arm: float = 13.5, gap: float = 5.0) -> list[Shape]:
    """Precision crosshair with four separate arms and an open center."""
    left_arm = f"M{cx - arm} {cy} H{cx - gap}"
    right_arm = f"M{cx + gap} {cy} H{cx + arm}"
    top_arm = f"M{cx} {cy - arm} V{cy - gap}"
    bottom_arm = f"M{cx} {cy + gap} V{cy + arm}"
    return [path_shape(_path(left_arm, right_arm, top_arm, bottom_arm), "line", SW)]


def artboard() -> list[Shape]:
    """Artboard cursor with the stepped lower-right frame from the supplied SVG."""
    outline = "M2.5 16 H11 M21 16 H29.5 V29.5 M16 2.5 V11 M16 21 V29.5 H29.5"
    detail = "M2.5 16 H11 M16 2.5 V11 M21 16 H29.5 V29.5 H16 V21"
    return [
        path_shape(outline, "line", SW),
        path_shape(detail, "line", SW, top=True),
    ]


# Magic wand: a stick narrowing towards the hotspot, drawn along the local y axis and tilted up-left,
# with one sparkle above-left of the hotspot, upright.
_WAND_TIP = (13, 12)         # hotspot: the top end of the stick
_WAND_TILT = 32              # degrees from vertical
_WAND_TIP_WIDTH = 2.6        # the stick narrows slightly towards the hotspot
_WAND_HANDLE_WIDTH = 4.2
_WAND_LENGTH = 18
_WAND_SPARKLE_OFFSET = (-4.5, -4.5)  # sparkle center relative to the hotspot
_WAND_SPARKLE_RADIUS = 4.6


def magic_wand() -> list[Shape]:
    """Magic wand: tapered stick with a sparkle at its top end."""
    tip_x, tip_y = _WAND_TIP
    transform = f"translate({tip_x} {tip_y}) rotate({-_WAND_TILT})"
    tip_half, handle_half = _WAND_TIP_WIDTH / 2, _WAND_HANDLE_WIDTH / 2
    corners = [(-tip_half, 0), (tip_half, 0), (handle_half, _WAND_LENGTH), (-handle_half, _WAND_LENGTH)]
    outline = rounded_polygon(corners, [tip_half, tip_half, handle_half, handle_half])
    offset_x, offset_y = _WAND_SPARKLE_OFFSET
    star = sparkle(tip_x + offset_x, tip_y + offset_y, _WAND_SPARKLE_RADIUS)
    return [path_shape(star, "ink"), path_shape(outline, "paper", xf=transform)]


# Fill (paint bucket): the bucket is drawn upright around its own origin and tilted to pour to the left;
# the drop falls below the lower rim end and its lowest point is the hotspot.
_BUCKET_CENTER = (19.5, 17.2)
_BUCKET_TILT = 35            # degrees counter-clockwise
_BUCKET_RIM_HALF = 8.7       # half width at the rim (top)
_BUCKET_BASE_HALF = 5.5      # half width at the base (bottom)
_BUCKET_HALF_HEIGHT = 7.7
_BUCKET_RIM_ROUNDING = 1.1
_BUCKET_BASE_ROUNDING = 2.2
_BUCKET_HANDLE_RISE = 8.4   # how far the handle arc rises above the rim
_DROP_HOTSPOT = (6, 30)
_DROP_RADIUS = 2.6
_DROP_HEIGHT = 6.8           # from the pointed top to the lowest point


def fill() -> list[Shape]:
    """Paint bucket tilted to pour, with a drop under the rim."""
    center_x, center_y = _BUCKET_CENTER
    transform = f"translate({center_x} {center_y}) rotate({-_BUCKET_TILT})"
    rim, base = -_BUCKET_HALF_HEIGHT, _BUCKET_HALF_HEIGHT
    rim_rounding, base_rounding = _BUCKET_RIM_ROUNDING, _BUCKET_BASE_ROUNDING
    body = rounded_polygon([(-_BUCKET_RIM_HALF, rim), (_BUCKET_RIM_HALF, rim),
                            (_BUCKET_BASE_HALF, base), (-_BUCKET_BASE_HALF, base)],
                           [rim_rounding, rim_rounding, base_rounding, base_rounding])
    handle = _path(f"M{-_BUCKET_RIM_HALF} {rim}",
                   f"C{-_BUCKET_RIM_HALF} {rim - _BUCKET_HANDLE_RISE} "
                   f"{_BUCKET_RIM_HALF} {rim - _BUCKET_HANDLE_RISE} {_BUCKET_RIM_HALF} {rim}")
    drop_x, drop_bottom = _DROP_HOTSPOT
    drop_center_y = drop_bottom - _DROP_RADIUS
    drop_top = drop_bottom - _DROP_HEIGHT
    drop = _path(f"M{drop_x} {drop_top}",
                 f"C{drop_x - _DROP_RADIUS * 0.5} {drop_top + 2.2} {drop_x - _DROP_RADIUS} {drop_center_y - 1.2} "
                 f"{drop_x - _DROP_RADIUS} {drop_center_y}",
                 f"A{_DROP_RADIUS} {_DROP_RADIUS} 0 0 0 {drop_x + _DROP_RADIUS} {drop_center_y}",
                 f"C{drop_x + _DROP_RADIUS} {drop_center_y - 1.2} {drop_x + _DROP_RADIUS * 0.5} {drop_top + 2.2} "
                 f"{drop_x} {drop_top}",
                 "Z")
    return [
        path_shape(handle, "line", SW, xf=transform),
        path_shape(body, "paper", xf=transform),
        path_shape(drop, "ink"),
    ]


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
}

# Badge origin on the grid per base cursor; DEFAULT is used for bases not listed.
# The pen nib occupies the diagonal, so its badges sit lower in the corner: the halos must not
# touch the nib, and the outer halo stays inside the grid.
BADGE_ANCHOR_DEFAULT = (24.5, 24.5)
BADGE_ANCHOR = {"pen": (26.4, 26.4)}

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
    "artboard": ((16, 16), artboard),
    "magic_wand": (_WAND_TIP, magic_wand),
    "fill": (_DROP_HOTSPOT, fill),
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
# other tools reuse the same badges, e.g.: add_badged("select_add", "select", "plus")


def canvas_size(name: str) -> tuple[float, float]:
    return CANVAS.get(name, (GRID, GRID))


# ============================== BUILD ======================================

def build_svg(name: str, size: int = GRID, theme: str | None = None) -> str:
    """size = pixels per GRID units, so the scale is the same for every canvas.
    Width/height are integers when size is integer so the rasterizer hits whole pixels."""
    hot, factory = CURSORS[name]
    cw, ch = canvas_size(name)
    body = render(factory(), theme=theme)
    w = round(cw * size / GRID)
    h = round(ch * size / GRID)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {cw:g} {ch:g}" shape-rendering="geometricPrecision">\n'
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


def render_image(name: str, px: int, theme: str | None = None):
    """Returns a square QImage; the cursor sits in its top left corner at px pixels per GRID units
    (a bigger canvas stays transparent below/right, so the hotspot position is the same).
    Sizes and the paint rect are integers so the result stays pixel-aligned."""
    QBuffer, QByteArray, QIODevice, Qt, QImage, QPainter, QSvgRenderer = _qt()
    from PyQt6.QtCore import QRectF
    cw, ch = canvas_size(name)
    r = QSvgRenderer(QByteArray(build_svg(name, theme=theme).encode("utf-8")))
    side = image_side(name, px)
    img = QImage(side, side, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # integer pixel bounds (QRectF required by the API)
    w = round(cw * px / GRID)
    h = round(ch * px / GRID)
    r.render(p, QRectF(0, 0, w, h))
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


def main() -> None:
    from preview import contact_sheet, preview_html

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
    manifest["_meta"] = {"theme": THEME, "themes": list(THEMES)}
    (out / "cursors.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out / "preview.html").write_text(
        preview_html(CURSORS, canvas_size, build_svg, GRID, THEME),
        encoding="utf-8",
    )
    contact_sheet(out / "sheet.png", CURSORS, image_side, render_image, _qt)
    print(f"ready: {len(CURSORS)} cursors (theme={THEME}) -> {out.resolve()}")


if __name__ == "__main__":
    main()