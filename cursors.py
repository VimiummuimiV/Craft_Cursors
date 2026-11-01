"""Cursor shapes, drawing primitives, and shared style settings."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, replace
from typing import Callable

# ============================== STYLE ======================================
GRID = 32            # logical cursor grid
COMPACT_PREVIEW_SIZE = 28
SW = 1.8             # thickness of all outlines and lines
H = 1.8              # halo width
CUR_SIZES = (96,)    # sizes included in .cur files
PNG_SIZE = max(CUR_SIZES)  # the PNG is exported at the largest .cur size

# Allowed region: every cursor, halo included, stays at least PADDING away from all four canvas edges.
# Shapes derived from the constants below follow PADDING automatically; hand-drawn geometry
# (hands, arrow, scissors, wand, bucket) is verified by check_padding() in main.py.
PADDING = 1.0
LINE_REACH = SW / 2 + H            # how far a line's halo sticks out past its centerline
PAPER_REACH = SW + H               # same for outlined forms (stroke on both sides of the edge)
LINE_INSET = PADDING + LINE_REACH  # nearest a line's centerline may get to a canvas edge
LINE_FAR_EDGE = GRID - LINE_INSET  # farthest a line's centerline may reach

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


def _stroke(color: str, width: float, fill: str = "none") -> str:
    return f'fill="{fill}" stroke="{color}" stroke-width="{width}" {ROUND}'


def _flat(color: str) -> str:
    return f'fill="{color}" stroke="none"'


def render(shapes: list[Shape], theme: str | None = None) -> str:
    """theme: 'dark' | 'light' | None (= THEME)."""
    colors = THEMES[theme or THEME]
    ink, paper, halo = colors["ink"], colors["paper"], colors["halo"]
    body = [s for s in shapes if not s.top]
    details = [s for s in shapes if s.top]
    out: list[str] = []
    # 1) halo
    for s in body:
        if s.kind == "paper":
            attrs = _stroke(halo, 2 * (SW + H), fill=halo)
        elif s.kind == "pline":
            attrs = _stroke(halo, s.w + 2 * (SW + H))
        elif s.kind == "ink":
            attrs = _stroke(halo, 2 * H, fill=halo)
        else:
            attrs = _stroke(halo, s.w + 2 * H)
        out.append(s.tag(attrs))
    # 2) outline / dark forms
    for s in body:
        if s.kind == "paper":
            attrs = _stroke(ink, 2 * SW, fill=ink)
        elif s.kind == "pline":
            attrs = _stroke(ink, s.w + 2 * SW)
        elif s.kind == "ink":
            attrs = _flat(ink)
        else:
            attrs = _stroke(ink, s.w)
        out.append(s.tag(attrs))
    # 3) light fill on top (eraser for internal intersection lines)
    for s in body:
        if s.kind in ("paper", "fill"):
            out.append(s.tag(_flat(paper)))
        elif s.kind == "pline":
            out.append(s.tag(_stroke(paper, s.w)))
    # 4) top details
    for s in details:
        out.append(s.tag(_flat(ink) if s.kind == "ink" else _stroke(ink, s.w)))
    return "\n".join(out)


# ============================ GEOMETRY ====================================

def _path(*segments: str) -> str:
    """Joins named path segments into one path string."""
    return " ".join(segments)


def path_shape(
    path_data: str,
    kind: str,
    width: float = 0.0,
    top: bool = False,
    xf: str = "",
) -> Shape:
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


_STAR_POINTS = 5
_STAR_INNER_RATIO = 0.45     # inner point radius / outer point radius
_STAR_ROUNDING_RATIO = 0.1   # corner radius / outer point radius


def star(outer_radius: float) -> str:
    """Star around the origin with _STAR_POINTS outer and as many inner points, all corners rounded.
    One outer point looks straight up."""
    points = []
    for index in range(2 * _STAR_POINTS):
        radius = outer_radius if index % 2 == 0 else outer_radius * _STAR_INNER_RATIO
        angle = math.radians(-90 + index * 180 / _STAR_POINTS)
        points.append((radius * math.cos(angle), radius * math.sin(angle)))
    return rounded_polygon(points, outer_radius * _STAR_ROUNDING_RATIO)


def arrow() -> list[Shape]:
    """Default pointer: rounded triangle, minimal points (two per corner), the top-left corner is the hotspot."""
    start = "M6 6.2"
    top_left_corner = "C6 4.3 7.7 4.3 8.6 5.1"
    upper_edge = "L22.06 17.3"
    right_tip = "C22.8 18 22.6 19.5 21.7 19.7"
    concave_lower_edge = "C15.7 21.6 11.1 24.3 8.3 27.1"
    bottom_left_corner = "C7.6 27.8 6 27.5 6 25.9"  # the left edge closes the path
    outline = _path(start, top_left_corner, upper_edge, right_tip, concave_lower_edge, bottom_left_corner, "Z")
    return [path_shape(outline, "paper")]


_LENS_RADIUS = 8.4
_LENS_CENTER = PADDING + PAPER_REACH + _LENS_RADIUS   # the lens touches the top left of the allowed region
_ZOOM_SIGN_ARM = 3.8
_HANDLE_RADIUS = 2.2
_HANDLE_START_DISTANCE = 9.5   # from the lens center; the flat end hides under the lens outline
_HALF_DIAGONAL = math.sqrt(0.5)   # cos(45 degrees): the handle runs along the grid diagonal
_HANDLE_END = GRID - PADDING - H - _HANDLE_RADIUS   # round end touches the bottom right of the allowed region


def zoom(sign: str) -> list[Shape]:
    center, arm = _LENS_CENTER, _ZOOM_SIGN_ARM
    side = _HANDLE_RADIUS * _HALF_DIAGONAL   # offset of the handle edges from its axis on each grid axis
    start = center + _HANDLE_START_DISTANCE * _HALF_DIAGONAL
    handle = _path(f"M{_number(start - side)} {_number(start + side)}",
                   f"L{_number(start + side)} {_number(start - side)}",
                   f"L{_number(_HANDLE_END + side)} {_number(_HANDLE_END - side)}",
                   f"A{_HANDLE_RADIUS} {_HANDLE_RADIUS} 0 0 1 {_number(_HANDLE_END - side)} {_number(_HANDLE_END + side)}",
                   "Z")
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


# Eyedropper and pen nib are drawn along the local -y axis from the tip at the hotspot, tilted 45 degrees.
# The tip sits in the bottom left corner of the allowed region.
_TOOL_TIP = (PADDING + PAPER_REACH, GRID - PADDING - PAPER_REACH)
_TOOL_TIP_ANGLE = 45
_TOOL_TIP_XF = f"translate({_number(_TOOL_TIP[0])} {_number(_TOOL_TIP[1])}) rotate({_TOOL_TIP_ANGLE})"


def eyedropper() -> list[Shape]:
    tip, neck, tube_end = "M0 0", "-7", "-17.5"
    tube = _path(tip, f"L-2.7 {neck}", f"L-2.7 {tube_end}", f"L2.7 {tube_end}", f"L2.7 {neck}", "Z")
    return [
        path_shape(tube, "paper", xf=_TOOL_TIP_XF),
        Shape("rect", 'x="-4.5" y="-21.5" width="9" height="4.5" rx="1.2"', "paper", xf=_TOOL_TIP_XF),
        Shape("rect", 'x="-3.5" y="-31" width="7" height="10.5" rx="3.5"', "ink", xf=_TOOL_TIP_XF),
    ]


# Hands are in 32x32 grid coordinates, fitted to the allowed region with outline and halo.
# The closed hand has the same scale and anchor (two states of one cursor, so it is not enlarged).
# Both outlines start and end at the wrist; each part is listed in drawing order.
_HAND_WRIST = "14.45 28.3"

_HAND_OPEN_PARTS = {
    "wrist_to_thumb": "C 11.85 28.3 8.8 22.48 6.56 20.3",
    "thumb": "C 5.27 19.05 3.22 18.6 3.99 16.51 C 4.61 14.81 7.24 14.54 9.2 15.79 "
             "C 10.62 16.69 11.76 17.86 11.76 17.86",
    "index_finger": "C 11.76 17.86 9.55 9.8 9.24 8.62 C 8.93 7.45 9.62 6.25 10.8 5.92 "
                    "C 11.97 5.6 13.16 6.19 13.51 7.48 C 13.86 8.79 15.07 13.24 15.07 13.24",
    "middle_finger": "C 15.07 13.24 14.44 7.14 14.33 5.92 C 14.22 4.72 15.23 3.8 16.45 3.7 "
                     "C 17.56 3.62 18.7 4.7 18.75 5.92 C 18.79 7.14 18.97 13.07 18.97 13.07",
    "ring_finger": "C 18.97 13.07 19.57 8.11 19.7 6.89 C 19.84 5.65 21 5.01 22.18 5.25 "
                   "C 23.31 5.49 23.92 6.85 23.72 8.05 C 23.54 9.23 22.7 14.22 22.7 14.22",
    "little_finger": "C 22.7 14.22 23.83 10.52 24.15 9.51 C 24.52 8.35 25.94 8.01 26.95 8.39 "
                     "C 28.05 8.81 28.46 10.11 27.98 11.72 C 27.5 13.34 27.08 14.7 26.34 16.96",
    "palm_to_wrist": "C 25.86 18.41 26 21.9 24.78 24.02 C 22.35 28.19 21.71 28.3 19.89 28.3",
}
_HAND_CLOSED_PARTS = {
    "wrist_to_thumb": "C 12.35 28.3 8.67 22.83 8.13 19.75",
    "thumb": "C 7.88 18.26 11.18 15.79 11.18 15.79 L 11.76 17.86",
    "index_finger": "C 11.76 17.86 11.23 15.96 10.93 14.83 C 10.62 13.7 10.61 12.33 12.21 11.74 "
                    "C 13.35 11.31 14.76 12.07 15.07 13.24",
    "middle_finger": "L 14.78 12.1 C 14.58 10.92 15.7 9.86 16.92 9.86 C 18.13 9.86 19.13 10.71 19.13 11.92",
    "ring_finger": "L 18.97 13.07 C 18.97 13.07 18.99 13.14 19.13 11.92 C 19.26 10.68 20.74 10.05 21.86 10.44 "
                   "C 22.86 10.77 23.46 11.88 23.13 12.98 C 22.94 13.62 22.7 14.22 22.7 14.22",
    "little_finger": "C 22.7 14.22 23.64 12.06 25.6 13.16 C 26.68 13.75 26.64 15.85 26.34 16.96",
    "palm_to_wrist": "C 25.86 18.41 26 21.9 24.78 24.02 C 22.35 28.19 21.71 28.3 19.89 28.3",
}


def _hand(parts: dict[str, str]) -> list[Shape]:
    outline = _path(f"M {_HAND_WRIST}", *parts.values(), f"L {_HAND_WRIST} Z")
    return [path_shape(outline, "fill", SW), path_shape(outline, "line", SW, top=True)]


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


_CANVAS_CENTER = GRID // 2


def crosshair() -> list[Shape]:
    """Precision crosshair with four separate arms and an open center; the arm ends touch the allowed region."""
    center, gap, near, far = _CANVAS_CENTER, 5, _number(LINE_INSET), _number(LINE_FAR_EDGE)
    left_arm = f"M{near} {center} H{center - gap}"
    right_arm = f"M{center + gap} {center} H{far}"
    top_arm = f"M{center} {near} V{center - gap}"
    bottom_arm = f"M{center} {center + gap} V{far}"
    return [path_shape(_path(left_arm, right_arm, top_arm, bottom_arm), "line", SW)]


def artboard() -> list[Shape]:
    """Artboard cursor with the stepped lower-right frame; the line ends touch the allowed region."""
    near, far = _number(LINE_INSET), _number(LINE_FAR_EDGE)
    outline = f"M{near} 16 H11 M21 16 H{far} V{far} M16 {near} V11 M16 21 V{far} H{far}"
    detail = f"M{near} 16 H11 M16 {near} V11 M21 16 H{far} V{far} H16 V21"
    return [
        path_shape(outline, "line", SW),
        path_shape(detail, "line", SW, top=True),
    ]


_CROP_RING_RADIUS = 6.5
_CROP_ARM_OUTER_RADIUS = _CANVAS_CENTER - LINE_INSET   # the arm ends touch the allowed region
_CROP_CENTER_DOT_RADIUS = 2


def crop() -> list[Shape]:
    """Crop tool target with arms meeting the circular ring."""
    center = _CANVAS_CENTER
    inner, outer = _CROP_RING_RADIUS, _CROP_ARM_OUTER_RADIUS
    arms = _path(
        f"M{center} {_number(center - outer)} V{center - inner}",
        f"M{center + inner} {center} H{_number(center + outer)}",
        f"M{center} {center + inner} V{_number(center + outer)}",
        f"M{_number(center - outer)} {center} H{center - inner}",
    )
    return [
        path_shape(arms, "line", SW),
        Shape("circle", f'cx="{center}" cy="{center}" r="{_CROP_RING_RADIUS}"', "paper"),
        Shape("circle", f'cx="{center}" cy="{center}" r="{_CROP_CENTER_DOT_RADIUS}"', "ink", top=True),
    ]


_WAND_TILT = 32
_SCISSORS_HOTSPOT = (10, 5.6)
_SCISSORS_SCALE = 1.078   # the scissors span the same height as the magic wand
_SCISSORS_XF = f"translate({_SCISSORS_HOTSPOT[0]} {_SCISSORS_HOTSPOT[1]}) rotate({-_WAND_TILT})"
_SCISSORS_PATH = (
    "M0 15.078 L-1.155 17.079 C-0.952 18.006 -1.081 19.009 -1.594 19.895 "
    "C-2.684 21.785 -5.103 22.433 -6.993 21.342 C-8.883 20.252 -9.531 17.831 "
    "-8.44 15.942 C-7.414 14.165 -5.212 13.485 -3.381 14.319 L-1.911 11.77 "
    "L-5.276 5.94 C-7.223 2.569 -4.885 0 -4.885 0 L0 8.461 L4.885 0 "
    "C4.885 0 7.222 2.568 5.276 5.94 L1.911 11.77 L3.381 14.319 "
    "C5.212 13.485 7.414 14.164 8.44 15.942 C9.531 17.831 8.883 20.252 "
    "6.993 21.342 C5.103 22.433 2.684 21.785 1.594 19.895 "
    "C1.081 19.009 0.952 18.006 1.155 17.079 L0 15.078 Z "
    "M4.13 16.382 C3.282 16.872 2.991 17.958 3.48 18.806 "
    "C3.97 19.653 5.056 19.945 5.904 19.455 C6.751 18.965 7.042 17.879 "
    "6.553 17.032 C6.063 16.184 4.977 15.894 4.13 16.382 Z "
    "M-4.13 16.382 C-4.977 15.894 -6.063 16.184 -6.553 17.032 "
    "C-7.042 17.879 -6.751 18.965 -5.904 19.455 C-5.056 19.945 -3.97 19.653 "
    "-3.48 18.806 C-2.991 17.958 -3.282 16.872 -4.13 16.382 Z"
)


def scissors() -> list[Shape]:
    """Scissors point down in local coordinates and rotate to the Magic Wand angle."""
    # only the coordinates are scaled, so the halo keeps its width
    scaled = re.sub(r"-?\d+\.?\d*", lambda match: _number(float(match.group()) * _SCISSORS_SCALE), _SCISSORS_PATH)
    return [path_shape(scaled, "ink", xf=_SCISSORS_XF)]


# Magic wand: a star on top of a straight stick that narrows towards it; the whole cursor rotates together.
_WAND_CENTER = (10, 9.2)    # hotspot: the star center
_WAND_STAR_RADIUS = 8.8
_WAND_TIP_WIDTH = 2.8        # stick width next to the star
_WAND_HANDLE_WIDTH = 4.6
_WAND_LENGTH = 23.2           # from the star center to the handle end
_WAND_STAR_STICK_GAP = 0    # visible gap between the outlined star and stick


def magic_wand() -> list[Shape]:
    """Magic wand: star on a tapered stick."""
    center_x, center_y = _WAND_CENTER
    transform = f"translate({center_x} {center_y}) rotate({-_WAND_TILT})"
    tip_half, handle_half = _WAND_TIP_WIDTH / 2, _WAND_HANDLE_WIDTH / 2
    star_notch = _WAND_STAR_RADIUS * _STAR_INNER_RATIO
    stick_start = star_notch + 2 * SW + _WAND_STAR_STICK_GAP - tip_half
    corners = [(-tip_half, stick_start), (tip_half, stick_start),
               (handle_half, _WAND_LENGTH), (-handle_half, _WAND_LENGTH)]
    stick = rounded_polygon(corners, [tip_half, tip_half, handle_half, handle_half])
    return [
        path_shape(star(_WAND_STAR_RADIUS), "ink", xf=transform),
        path_shape(stick, "ink", xf=transform),
    ]


# Fill (paint bucket): the bucket is drawn upright around its own origin and tilted to pour to the left;
# the drop falls below the lower rim end and its lowest point is the hotspot.
_BUCKET_CENTER = (18.9, 17.2)
_BUCKET_TILT = 35            # degrees counter-clockwise
_BUCKET_RIM_HALF = 8.7       # half width at the rim (top)
_BUCKET_BASE_HALF = 5.5      # half width at the base (bottom)
_BUCKET_HALF_HEIGHT = 7.7
_BUCKET_RIM_ROUNDING = 1.1
_BUCKET_BASE_ROUNDING = 2.2
_BUCKET_HANDLE_RISE = 8.4  # how far the handle arc rises above the rim
_DROP_HOTSPOT = (6, GRID - PADDING - H)   # the lowest point touches the bottom of the allowed region
_DROP_RADIUS = 2.6
_DROP_HEIGHT = 6.8           # from the pointed top to the lowest point


def fill() -> list[Shape]:
    """Paint bucket tilted to pour, with a drop under the rim."""
    center_x, center_y = _BUCKET_CENTER
    transform = f"translate({center_x} {center_y}) rotate({-_BUCKET_TILT})"
    rim, base = -_BUCKET_HALF_HEIGHT, _BUCKET_HALF_HEIGHT
    body = rounded_polygon([(-_BUCKET_RIM_HALF, rim), (_BUCKET_RIM_HALF, rim),
                            (_BUCKET_BASE_HALF, base), (-_BUCKET_BASE_HALF, base)],
                           [_BUCKET_RIM_ROUNDING, _BUCKET_RIM_ROUNDING, _BUCKET_BASE_ROUNDING, _BUCKET_BASE_ROUNDING])
    handle_top = rim - _BUCKET_HANDLE_RISE
    handle = _path(f"M{-_BUCKET_RIM_HALF} {rim}",
                   f"C{-_BUCKET_RIM_HALF} {handle_top} {_BUCKET_RIM_HALF} {handle_top} {_BUCKET_RIM_HALF} {rim}")
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
# Every glyph is drawn once around its own origin (0, 0) and no glyph reaches farther than _BADGE_HALF_SIZE,
# so all badges share one origin in the bottom right corner of the allowed region.
#   "shared" - universal marks (+, -), usable on any cursor;
#   "<base>" - marks of one tool, so a bulky mark never constrains the others.
# add_badged() looks in the base's group first, then in "shared".
_BADGE_HALF_SIZE = 2.8
BADGE_ORIGIN = GRID - PADDING - LINE_REACH - _BADGE_HALF_SIZE
BADGES: dict[str, dict[str, list[Shape]]] = {
    "shared": {
        "plus": [path_shape("M-2.8 0 H2.8 M0 -2.8 V2.8", "line", SW)],
        "minus": [path_shape("M-2.8 0 H2.8", "line", SW)],
    },
    "pen": {
        "wave": [path_shape("M-3.8 1.4 Q-2.15 -1.4 -0.5 1.4 T2.8 1.4", "line", SW)],
        "curve": [path_shape("M-4.6 2.8 C-1.4 2.8 -1.4 -3.6 2.8 -3.6", "line", SW)],
        "caret": [path_shape("M-3 2.6 L0 -1.8 L2.8 2.6", "line", SW)],
        "ring": [Shape("circle", 'cx="0" cy="0" r="2.5"', "line", SW)],
    },
}

# Canvas size in grid units, only for cursors that do not fit 32x32 (name -> (width, height)).
CANVAS: dict[str, tuple[float, float]] = {}


# name -> (hotspot on the 32x32 grid, shape factory)
CURSORS: dict[str, tuple[tuple[float, float], Callable[[], list[Shape]]]] = {
    "arrow": ((7, 4.5), arrow),
    "zoom_in": ((_LENS_CENTER, _LENS_CENTER), lambda: zoom("+")),
    "zoom_out": ((_LENS_CENTER, _LENS_CENTER), lambda: zoom("-")),
    "eyedropper": (_TOOL_TIP, eyedropper),
    "hand_open": ((_CANVAS_CENTER, _CANVAS_CENTER), lambda: _hand(_HAND_OPEN_PARTS)),
    "hand_closed": ((_CANVAS_CENTER, _CANVAS_CENTER), lambda: _hand(_HAND_CLOSED_PARTS)),
    "pen": (_TOOL_TIP, pen_nib),
    "crosshair": ((_CANVAS_CENTER, _CANVAS_CENTER), crosshair),
    "artboard": ((_CANVAS_CENTER, _CANVAS_CENTER), artboard),
    "crop": ((_CANVAS_CENTER, _CANVAS_CENTER), crop),
    "scissors": (_SCISSORS_HOTSPOT, scissors),
    "magic_wand": (_WAND_CENTER, magic_wand),
    "fill": (_DROP_HOTSPOT, fill),
}


def add_badged(name: str, base: str, badge: str, canvas: tuple[float, float] | None = None) -> None:
    """Registers cursor `name` = base cursor + badge. The hotspot is taken from the base.
    canvas: size in grid units if the badge goes beyond the base's 32x32 grid."""
    hot, base_factory = CURSORS[base]
    shapes = BADGES.get(base, {}).get(badge) or BADGES["shared"][badge]
    placed = [replace(s, xf=f"translate({_number(BADGE_ORIGIN)} {_number(BADGE_ORIGIN)})") for s in shapes]
    CURSORS[name] = (hot, lambda: base_factory() + placed)
    if canvas:
        CANVAS[name] = canvas


for name, (base, badge) in {
    "pen_freeform": ("pen", "wave"),
    "pen_curvature": ("pen", "curve"),
    "pen_add": ("pen", "plus"),
    "pen_delete": ("pen", "minus"),
    "pen_convert": ("pen", "caret"),
    "pen_close": ("pen", "ring"),
}.items():
    add_badged(name, base, badge)
# other tools reuse the same badges, e.g.: add_badged("select_add", "select", "plus")


def canvas_size(name: str) -> tuple[float, float]:
    return CANVAS.get(name, (GRID, GRID))


def build_svg(name: str, size: int = GRID, theme: str | None = None) -> str:
    """size = pixels per GRID units, so the scale is the same for every canvas.
    Width/height are integers when size is integer so the rasterizer hits whole pixels."""
    hot, factory = CURSORS[name]
    canvas_width, canvas_height = canvas_size(name)
    width = round(canvas_width * size / GRID)
    height = round(canvas_height * size / GRID)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {canvas_width:g} {canvas_height:g}" shape-rendering="geometricPrecision">\n'
            f'<!-- hotspot: {_number(hot[0])},{_number(hot[1])} -->\n{render(factory(), theme=theme)}\n</svg>\n')