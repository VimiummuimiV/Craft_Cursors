"""Cursor shapes, drawing primitives, and shared style settings."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, replace
from typing import Callable

from config import (
    GRID,
    H,
    PADDING,
    SW,
    THEMES,
)
from gridfit import (
    Fit,
    number,
    path_extent,
    pixel,
)

# ============================== DERIVED ====================================
# Allowed region: every cursor, halo included, stays at least PADDING away from all four canvas edges.
# Shapes derived from the constants below follow PADDING automatically; hand-drawn geometry
# (hands, arrow, scissors, wand, bucket) is verified by the padding check in main.py.
_LINE_REACH = SW / 2 + H            # how far a line's halo sticks out past its centerline
_PAPER_REACH = SW + H               # same for outlined forms (stroke on both sides of the edge)
_LINE_INSET = PADDING + _LINE_REACH  # nearest a line's centerline may get to a canvas edge
_LINE_FAR_EDGE = GRID - _LINE_INSET  # farthest a line's centerline may reach
# ===========================================================================

# Cursor rotation angles, in degrees.
_TOOL_TIP_ANGLE = 45

# Shared rendering and canvas geometry.
_STROKED_KINDS = ("fill", "solid", "line", "inverse")   # kinds whose outline is centered on the path
_CANVAS_CENTER = GRID // 2
_CENTER_DOT_RADIUS = 2

# Shared by eyedropper, pen nib, and knife.
_TOOL_TIP = (PADDING + _PAPER_REACH, GRID - PADDING - _PAPER_REACH)
_TOOL_TRANSFORM = (*_TOOL_TIP, _TOOL_TIP_ANGLE)
_TOOL_LENGTH = 29.5


@dataclass
class _Shape:
    """A single cursor element, drawn in grid units around its own origin.

    kind:
      paper - light form with a dark outline (closed path, circle)
      fill  - light form with an outline of thickness SW drawn over the fill (folds stay visible)
      inverse - solid ink form with paper-colored halo only (like ink, colors swapped; arrow family)
      ink   - solid dark form
      solid - solid dark form with an outline of thickness SW (arrowheads, corners)
      line  - dark line with thickness SW (symbols +, -, ^, etc.)
      dot   - solid dark circle with a halo, always drawn above everything else
    top: drawn above everything else, without a halo (details inside forms)
    transform: (x, y, angle) moves the origin to x, y and rotates by angle degrees; an unrotated shape
      is snapped to the pixel grid, a rotated one only has its origin snapped
    sharp: square line ends and mitered corners, for axis-aligned geometry that must stay crisp
    name: element id in the SVG, unique inside a cursor (its halo and fill elements add _halo / _fill)
    group: the <g> that holds the shape's elements; empty = the cursor's own group. A cursor with a badge
      splits into the base cursor's group and `badge`, nested under a group named after the cursor.
      A group keeps its own painting order (halo, outline, fill, details)
    snap: whether a circle is aligned to the pixel grid when rendered
    """
    kind: str
    path: str = ""
    circle: tuple[float, float, float] | None = None
    top: bool = False
    transform: tuple[float, float, float] = (0.0, 0.0, 0.0)
    sharp: bool = False
    name: str = ""
    group: str = ""
    snap: bool = True


def _stroke(color: str, width: float, fill: str = "none", sharp: bool = False) -> str:
    cap, join = ("square", "miter") if sharp else ("round", "round")
    return f'fill="{fill}" stroke="{color}" stroke-width="{number(width)}" stroke-linecap="{cap}" stroke-linejoin="{join}"'


def _flat(color: str) -> str:
    return f'fill="{color}" stroke="none"'


def _place(shape: _Shape, fit: Fit) -> Callable[..., str]:
    """Returns tag(attrs, ident, grow=0): the shape as an SVG element in pixel units; grow widens a circle."""
    origin_x, origin_y, angle = shape.transform
    rotated = angle != 0
    origin = (0.0, 0.0) if rotated else (origin_x, origin_y)
    rotation = (f' transform="translate({number(pixel(origin_x * fit.scale))} '
                f'{number(pixel(origin_y * fit.scale))}) rotate({number(angle)})"') if rotated else ""
    if shape.circle is None:
        on_center = shape.kind in _STROKED_KINDS and fit.stroke % 2 == 1
        data = fit.path(shape.path, on_center, origin, snap=not rotated)
        return lambda attrs, ident, grow=0.0: f'<path id="{ident}" d="{data}" {attrs}{rotation}/>'
    outline_reach = fit.stroke if shape.kind in ("paper", "inverse") else fit.stroke / 2 if shape.kind in _STROKED_KINDS else 0
    center_x, center_y, radius = fit.circle(shape.circle, origin, not rotated and shape.snap, outline_reach)
    return lambda attrs, ident, grow=0.0: (f'<circle id="{ident}" cx="{number(center_x)}" cy="{number(center_y)}" '
                                           f'r="{number(radius + grow)}" {attrs}{rotation}/>')


def _render(shapes: list[_Shape], fit: Fit, theme: str, cursor: str = "cursor") -> str:
    """theme: a key of THEMES. A cursor of one group is a single <g> named `cursor`; several groups nest in it.
    Inside a group the painting order is halo, outline, fill, details."""
    colors = THEMES[theme]
    ink, paper, halo = colors["ink"], colors["paper"], colors["halo"]
    stroke, halo_width = fit.stroke, fit.halo
    placed = [(shape, shape.name or f"{shape.kind}_{index}", _place(shape, fit))
              for index, shape in enumerate(shapes, 1)]
    body = [item for item in placed if not item[0].top and item[0].kind != "dot"]
    details = [item for item in placed if item[0].top or item[0].kind == "dot"]
    halos: list[tuple[str, str]] = []
    outlines: list[tuple[str, str]] = []
    covers: list[tuple[str, str]] = []
    tops: list[tuple[str, str]] = []
    # 1) halo
    for shape, ident, tag in body:
        if shape.kind == "paper":
            attrs = _stroke(halo, 2 * (stroke + halo_width), halo, shape.sharp)
        elif shape.kind == "inverse":
            attrs = _stroke(ink, 2 * halo_width, ink, shape.sharp)  # pure opposite of ink
        elif shape.kind == "ink":
            attrs = _stroke(halo, 2 * halo_width, halo, shape.sharp)
        elif shape.kind in ("fill", "solid"):
            attrs = _stroke(halo, stroke + 2 * halo_width, halo, shape.sharp)
        else:
            attrs = _stroke(halo, stroke + 2 * halo_width, sharp=shape.sharp)
        halos.append((shape.group, tag(attrs, f"{ident}_halo")))
    # 2) outline / dark forms
    for shape, ident, tag in body:
        if shape.kind == "paper":
            attrs = _stroke(ink, 2 * stroke, ink, shape.sharp)
        elif shape.kind == "inverse":
            attrs = _flat(paper)
        elif shape.kind == "ink":
            attrs = _flat(ink)
        elif shape.kind == "fill":
            attrs = _stroke(ink, stroke, paper, shape.sharp)
        elif shape.kind == "solid":
            attrs = _stroke(ink, stroke, ink, shape.sharp)
        else:
            attrs = _stroke(ink, stroke, sharp=shape.sharp)
        outlines.append((shape.group, tag(attrs, ident)))
    # 3) light fill on top (eraser for internal intersection lines)
    for shape, ident, tag in body:
        if shape.kind == "paper":
            covers.append((shape.group, tag(_flat(paper), f"{ident}_fill")))
    # 4) top details
    for shape, ident, tag in details:
        if shape.kind == "dot":
            tops.append((shape.group, tag(_flat(halo), f"{ident}_halo", halo_width)))
            tops.append((shape.group, tag(_flat(ink), ident)))
        elif shape.kind == "inverse":
            tops.append((shape.group, tag(_stroke(paper, stroke, ink, shape.sharp), ident)))
        elif shape.kind == "ink":
            tops.append((shape.group, tag(_flat(ink), ident)))
        else:
            tops.append((shape.group, tag(_stroke(ink, stroke, sharp=shape.sharp), ident)))
    groups: dict[str, list[str]] = {}
    for group, element in (*halos, *outlines, *covers, *tops):
        groups.setdefault(group or cursor, []).append(element)
    parts = ["\n".join([f'<g id="{group}">', *elements, "</g>"]) for group, elements in groups.items()]
    return parts[0] if len(parts) == 1 else "\n".join([f'<g id="{cursor}">', *parts, "</g>"])


# ============================ GEOMETRY ====================================

def _path(*segments: str) -> str:
    """Joins named path segments into one path string."""
    return " ".join(segments)


def _path_shape(
    path_data: str,
    kind: str,
    top: bool = False,
    transform: tuple[float, float, float] = (0.0, 0.0, 0.0),
    sharp: bool = False,
    name: str = "",
    group: str = "",
) -> _Shape:
    return _Shape(kind, path_data, None, top, transform, sharp, name, group)


def _circle(center_x: float, center_y: float, radius: float, kind: str, top: bool = False,
            transform: tuple[float, float, float] = (0.0, 0.0, 0.0), name: str = "",
            snap: bool = True) -> _Shape:
    return _Shape(kind, "", (center_x, center_y, radius), top, transform, name=name, snap=snap)


def _square(center_x: float, center_y: float, half: float, kind: str, name: str = "") -> _Shape:
    return _path_shape(_rectangle(center_x - half, center_y - half, center_x + half, center_y + half), kind, sharp=True, name=name)


def _dot(center_x: float, center_y: float, radius: float,
         transform: tuple[float, float, float] = (0.0, 0.0, 0.0), name: str = "center") -> _Shape:
    return _circle(center_x, center_y, radius, "dot", transform=transform, name=name)


def _direction(origin: tuple[float, float], target: tuple[float, float]) -> tuple[float, float, float]:
    """Unit vector from origin to target and the distance between them."""
    delta_x, delta_y = target[0] - origin[0], target[1] - origin[1]
    distance = math.hypot(delta_x, delta_y)
    return delta_x / distance, delta_y / distance, distance


_MAX_CURVE_SWEEP = math.pi / 2   # one cubic per corner up to this angle, two (three nodes) beyond it


def _corner_curves(start: tuple[float, float], end: tuple[float, float], corner: tuple[float, float],
                   arc_radius: float, sweep: float) -> str:
    """Circular corner arc as one cubic, or two when it turns more than _MAX_CURVE_SWEEP."""
    start_x, start_y, _ = _direction(corner, start)
    end_x, end_y, _ = _direction(corner, end)
    # travel directions: start -> corner at the start, corner -> end at the end
    tangents = [(-start_x, -start_y), (end_x, end_y)]
    points = [start, end]
    if sweep > _MAX_CURVE_SWEEP:
        bisector_x, bisector_y = start_x + end_x, start_y + end_y
        length = math.hypot(bisector_x, bisector_y)
        middle_tangent = (end_x - start_x, end_y - start_y)
        tangent_length = math.hypot(*middle_tangent)
        center_distance = arc_radius / math.sin((math.pi - sweep) / 2)
        points.insert(1, (corner[0] + bisector_x / length * (center_distance - arc_radius),
                          corner[1] + bisector_y / length * (center_distance - arc_radius)))
        tangents.insert(1, (middle_tangent[0] / tangent_length, middle_tangent[1] / tangent_length))
    handle = 4 / 3 * math.tan(sweep / (len(points) - 1) / 4) * arc_radius
    curves = []
    for (from_point, from_tangent), (to_point, to_tangent) in zip(zip(points, tangents), zip(points[1:], tangents[1:])):
        curves.append(f"C{number(from_point[0] + from_tangent[0] * handle)} {number(from_point[1] + from_tangent[1] * handle)} "
                      f"{number(to_point[0] - to_tangent[0] * handle)} {number(to_point[1] - to_tangent[1] * handle)} "
                      f"{number(to_point[0])} {number(to_point[1])}")
    return " ".join(curves)


def _rounded_polygon(points: list[tuple[float, float]], radius: float | list[float]) -> str:
    """Closed path through `points` with every corner replaced by a circular arc drawn as one or two cubics
    (two or three nodes). radius is shared by all corners or given per corner; 0 keeps a corner sharp."""
    count = len(points)
    radii = [radius] * count if isinstance(radius, (int, float)) else list(radius)
    segments: list[str] = []
    for index, (corner, corner_radius) in enumerate(zip(points, radii)):
        previous_x, previous_y, previous_length = _direction(corner, points[index - 1])
        next_x, next_y, next_length = _direction(corner, points[(index + 1) % count])
        command = "M" if index == 0 else "L"
        if corner_radius == 0:
            segments.append(f"{command}{number(corner[0])} {number(corner[1])}")
            continue
        half_angle = math.acos(max(-1.0, min(1.0, previous_x * next_x + previous_y * next_y))) / 2
        cut = min(corner_radius / math.tan(half_angle), previous_length / 2, next_length / 2)
        arc_radius = cut * math.tan(half_angle)
        start = (corner[0] + previous_x * cut, corner[1] + previous_y * cut)
        end = (corner[0] + next_x * cut, corner[1] + next_y * cut)
        segments.append(f"{command}{number(start[0])} {number(start[1])} "
                        + _corner_curves(start, end, corner, arc_radius, math.pi - 2 * half_angle))
    return _path(*segments, "Z")


def _rectangle(left: float, top: float, right: float, bottom: float, radius: float = 0) -> str:
    return _rounded_polygon([(left, top), (right, top), (right, bottom), (left, bottom)], radius)


_STAR_POINTS = 5
_STAR_INNER_RATIO = 0.45     # inner point radius / outer point radius
_STAR_ROUNDING_RATIO = 0.1   # corner radius / outer point radius


def _star(outer_radius: float) -> str:
    """Grid-snapped star with _STAR_POINTS outer and as many inner points, all corners rounded."""
    points = []
    for index in range(2 * _STAR_POINTS):
        radius = outer_radius if index % 2 == 0 else outer_radius * _STAR_INNER_RATIO
        angle = math.radians(-90 + index * 180 / _STAR_POINTS)
        x, y = radius * math.cos(angle), radius * math.sin(angle)
        points.append((int(math.copysign(pixel(abs(x)), x)), int(math.copysign(pixel(abs(y)), y))))
    return _rounded_polygon(points, pixel(outer_radius * _STAR_ROUNDING_RATIO))


_ARROW_HOTSPOT = (5, 3)


def _arrow() -> list[_Shape]:
    """Default pointer: rounded triangle, minimal points (two per corner), the top-left corner is the hotspot.
    The left edge is a whole-pixel vertical, every anchor sits on a grid point."""
    start = "M4 5"
    top_left_corner = "C4 3 6 3 7 4"
    upper_edge = "L20 16"
    right_tip = "C21 17 20.4 18.6 19 19"
    concave_lower_edge = "C14 20.4 9.5 22.4 6 24.5"
    bottom_left_corner = "C5 25.1 4 25 4 24"  # tangent to the lower edge; the left edge closes the path
    outline = _path(start, top_left_corner, upper_edge, right_tip, concave_lower_edge, bottom_left_corner, "Z")
    return [_path_shape(outline, "ink", name="pointer")]


def _arrow_path_selection() -> list[_Shape]:
    """Path Selection uses the default pointer silhouette."""
    return _arrow()


def _arrow_direct_selection() -> list[_Shape]:
    """White pointer for selecting and editing path anchors."""
    return [replace(shape, kind="inverse") for shape in _arrow()]


_TEXT_CAP_HALF = 3       # half width of the I-beam caps
_TEXT_LETTER_HALF = 2    # half width of the T crossbar
_TEXT_FRAME_SIDE = 12    # frame centerline side: 14 with its outline
_TEXT_BEAM_X = 8         # area text: puts the beam and the frame, _TEXT_GAP apart, in the middle of the canvas
_TEXT_GAP = SW           # clear space between the beam and the frame
_AREA_HOTSPOT = (_TEXT_BEAM_X, _CANVAS_CENTER)
_POINT = re.compile(r"(-?[\d.]+) (-?[\d.]+)")


def _turn_point(x: float, y: float) -> tuple[float, float]:
    """Quarter turn clockwise about the canvas center."""
    return GRID - y, x


def _turn_path(path: str) -> str:
    """Quarter turn of an absolute M/L/Z path."""
    return _POINT.sub(lambda point: " ".join(map(number, _turn_point(float(point[1]), float(point[2])))), path)


def _text_cursor(vertical: bool = False, area: bool = False) -> list[_Shape]:
    """I-beam insertion cursor. Area text (dragging a text frame) moves the beam left and adds a framed T
    on the right. Vertical text turns everything a quarter turn clockwise: beam on top, frame below."""
    cap, near, far, center = _TEXT_CAP_HALF, _LINE_INSET, _LINE_FAR_EDGE, _CANVAS_CENTER
    beam_x = _TEXT_BEAM_X if area else center
    beam = _path(f"M{beam_x - cap} {near} L{beam_x + cap} {near}", f"M{beam_x} {near} L{beam_x} {far}",
                 f"M{beam_x - cap} {far} L{beam_x + cap} {far}")
    shapes = [_path_shape(beam, "line", sharp=True, name="beam")]
    if area:
        tee, side, inset = _TEXT_LETTER_HALF, _TEXT_FRAME_SIDE, SW // 2
        left, top = beam_x + cap + SW + _TEXT_GAP, center - side // 2
        right, bottom, middle = left + side, top + side, left + side // 2
        glyph = _path(f"M{middle - tee} {center - tee} L{middle + tee} {center - tee}",
                      f"M{middle} {center - tee} L{middle} {center + tee}")
        shapes += [_path_shape(_rectangle(left + inset, top + inset, right - inset, bottom - inset), "paper", sharp=True, name="frame"),
                   _path_shape(glyph, "line", top=True, sharp=True, name="frame_letter")]
    return [replace(shape, path=_turn_path(shape.path)) for shape in shapes] if vertical else shapes


def _type_on_path() -> list[_Shape]:
    """Type on path: left-shifted I-beam with a bottom-right curve badge."""
    beam = [replace(shape, group="type") for shape in _text_cursor(area=True) if shape.name == "beam"]
    origin = _BADGE_ORIGIN
    badge = [
        replace(shape, transform=(origin, origin, 0), name=f"badge_{shape.name}", group="badge")
        for shape in _BADGES["pen"]["curve"]
    ]
    return beam + badge


_CORNER_MARK = "M28 17 C28 23 25 26 19 26"


def _arrow_corner() -> list[_Shape]:
    """Pointer with a rounded-corner arc."""
    return [replace(shape, group="arrow") for shape in _arrow()] + [
        _path_shape(_CORNER_MARK, "line", name="badge_corner_arc", group="badge")]


_LENS_RADIUS = 8
_LENS_CENTER = PADDING + _PAPER_REACH + _LENS_RADIUS   # the lens touches the top left of the allowed region
_ZOOM_SIGN_ARM = 4
_HANDLE_SIDE = 1.5               # offset of the handle edges from its axis on each grid axis: they run on x - y = +-3
_HALF_DIAGONAL = math.sqrt(0.5)  # cos(45 degrees): the handle runs along the grid diagonal
_HANDLE_RADIUS = _HANDLE_SIDE / _HALF_DIAGONAL
_HANDLE_START = _LENS_CENTER + 6   # the flat end hides under the lens outline
_HANDLE_END = GRID - PADDING - H - _HANDLE_RADIUS   # round end touches the bottom right of the allowed region


def _zoom(sign: str) -> list[_Shape]:
    center, arm, side = _LENS_CENTER, _ZOOM_SIGN_ARM, _HANDLE_SIDE
    handle = _path(f"M{number(_HANDLE_START - side)} {number(_HANDLE_START + side)}",
                   f"L{number(_HANDLE_START + side)} {number(_HANDLE_START - side)}",
                   f"L{number(_HANDLE_END + side)} {number(_HANDLE_END - side)}",
                   f"A{number(_HANDLE_RADIUS)} {number(_HANDLE_RADIUS)} 0 0 1 "
                   f"{number(_HANDLE_END - side)} {number(_HANDLE_END + side)}",
                   "Z")
    horizontal_bar = f"M{center - arm} {center} H{center + arm}"
    vertical_bar = f"M{center} {center - arm} V{center + arm}"
    bars = _path(horizontal_bar, vertical_bar) if sign == "+" else horizontal_bar
    return [
        _circle(center, center, _LENS_RADIUS, "paper", name="lens"),
        _path_shape(handle, "ink", name="handle"),
        _path_shape(bars, "line", top=True, sharp=True, name="sign"),
    ]


def _eyedropper() -> list[_Shape]:
    tip, neck, tube_end = "M0 0", "-7", "-17.5"
    tube = _path(tip, f"L-2.7 {neck}", f"L-2.7 {tube_end}", f"L2.7 {tube_end}", f"L2.7 {neck}", "Z")
    cap = _rounded_polygon([(-4.5, -21.5), (4.5, -21.5), (4.5, -17), (-4.5, -17)], 1.2)
    bulb = _rectangle(-3.5, -_TOOL_LENGTH, 3.5, -19.5, 3.5)
    return [
        _path_shape(_path(tube, cap), "paper", transform=_TOOL_TRANSFORM, name="tube"),
        _path_shape(bulb, "ink", transform=_TOOL_TRANSFORM, name="bulb"),
    ]


# Hands are in 32x32 grid coordinates on whole pixels, fitted to the allowed region with outline and halo.
# The closed hand has the same scale and anchor (two states of one cursor, so it is not enlarged).
# One outline runs from the wrist over thumb and fingers, then down the palm back to the wrist.
# The line between two fingers is part of the outline: it runs down the edge of a finger to the knuckle
# and back up along the next one, so every finger edge is a whole-pixel vertical.
_HAND_START = "M16 28"
_HAND_WRIST = "C14.5 28 13 27.5 12 26"
_HAND_PALM = "C28 21 27 25 24 27 C23.4 27.7 22.8 28 22 28 L16 28"
_HAND_THUMBS = {
    "grab": "C10 24 7 19.5 6 17 C5.4 15.8 6.4 14 8 14 L12 18",
    "grabbing": "C10 24 9 22 8.5 21 C8.2 20 8.4 19.4 8.8 19 C9.5 18 10.5 16.7 12 16 L12 18",
}
_FINGER_WIDTH = 4
_FINGERS_LEFT = 12
_KNUCKLE_Y = 16
# per pose: thumb variant and the top of each fingertip arc (index, middle, ring, little)
_HAND_POSES = {
    "grab": ("grab", (5, 4, 6, 8)),
    "grabbing": ("grabbing", (12, 11, 12, 14)),
    "pointer": ("grab", (5, 11, 12, 14)),
}
_POINTER_HOTSPOT = (_FINGERS_LEFT + _FINGER_WIDTH // 2, _HAND_POSES["pointer"][1][0])


def _finger(left: float, tip_top: float) -> str:
    """Up the left edge, over a semicircular tip, down the right edge to the knuckle."""
    radius, right = _FINGER_WIDTH / 2, left + _FINGER_WIDTH
    return (f"L{left} {tip_top + radius} A{radius} {radius} 0 0 1 {right} {tip_top + radius} "
            f"L{right} {_KNUCKLE_Y}")


def _hand(pose: str) -> list[_Shape]:
    thumb, tips = _HAND_POSES[pose]
    fingers = [_finger(_FINGERS_LEFT + index * _FINGER_WIDTH, tip_top) for index, tip_top in enumerate(tips)]
    outline = _path(_HAND_START, _HAND_WRIST, _HAND_THUMBS[thumb], *fingers, _HAND_PALM, "Z")
    return [_path_shape(outline, "fill", name="hand")]


_NIB_SLIT = 13.14  # slit length from the tip; the dot sits at its end


def _pen_nib() -> list[_Shape]:
    tip = "M0 0"
    left_flank = "L-5.4 -11.79"
    left_shoulder = "Q-6 -17.97 -4.2 -20.44"
    top_edge = "L4.2 -20.44"
    right_shoulder = "Q6 -17.97 5.4 -11.79"
    nib = _path(tip, left_flank, left_shoulder, top_edge, right_shoulder, "Z")
    return [
        _path_shape(nib, "paper", transform=_TOOL_TRANSFORM, name="nib"),
        _path_shape(_rectangle(-4.2, -_TOOL_LENGTH, 4.2, -19.32, 1.6), "ink", transform=_TOOL_TRANSFORM, name="cap"),
        _path_shape(f"M0 0 V{-_NIB_SLIT}", "line", top=True, transform=_TOOL_TRANSFORM, name="slit"),
        _circle(0, -_NIB_SLIT, 1.65, "ink", top=True, transform=_TOOL_TRANSFORM, name="vent"),
    ]


# Solid (ink) tools drawn upright from the tip: the tip is the hotspot, the far end reaches the same corner as the other tools.
_INK_TOOL_TIP = (_LINE_INSET, _LINE_FAR_EDGE)
_INK_TOOL_TRANSFORM = (*_INK_TOOL_TIP, _TOOL_TIP_ANGLE)
_PENCIL_HALF_WIDTH = 2
_PENCIL_TIP_LENGTH = 3
_PENCIL_BODY_END = 25
_PENCIL_CAP_START = 26
_PENCIL_CAP_END = 30


def _pencil() -> list[_Shape]:
    half = _PENCIL_HALF_WIDTH
    cap = f"M{-half} {-_PENCIL_CAP_END} L{half} {-_PENCIL_CAP_END} L{half} {-_PENCIL_CAP_START} L{-half} {-_PENCIL_CAP_START} Z"
    body = (f"M0 0 L{-half} {-_PENCIL_TIP_LENGTH} L{-half} {-_PENCIL_BODY_END} "
            f"L{half} {-_PENCIL_BODY_END} L{half} {-_PENCIL_TIP_LENGTH} Z")
    return [_path_shape(_path(cap, body), "ink", transform=_INK_TOOL_TRANSFORM, name="pencil")]


# Brush: one plain silhouette, a teardrop tuft on a neck, then a handle widening to a round end.
_BRUSH_HANDLE_HALF_WIDTH = 3
_BRUSH_HANDLE_END = 27


def _brush() -> list[_Shape]:
    handle, end = _BRUSH_HANDLE_HALF_WIDTH, _BRUSH_HANDLE_END
    outline = _path("M0 0",
                    "C1 -3 4 -4 4 -7",
                    "C4 -10 2 -10 2 -12",
                    f"L{handle} {-end}",
                    f"A{handle} {handle} 0 0 0 {-handle} {-end}",
                    "L-2 -12",
                    "C-2 -10 -4 -10 -4 -7",
                    "C-4 -4 -1 -3 0 0",
                    "Z")
    return [_path_shape(outline, "ink", transform=_INK_TOOL_TRANSFORM, name="brush")]


# Knife: blade (outlined) sits on the handle (solid); the blade tip is the hotspot, the tip is off the handle axis.
_KNIFE_SEAM = -17.92         # where the blade ends and the handle starts
_KNIFE_SPINE = -2.54         # the blunt upper edge; the handle is flush with its outline
_KNIFE_HANDLE_WIDTH = 5.47


def _knife() -> list[_Shape]:
    seam, side_a = _KNIFE_SEAM, _KNIFE_SPINE - SW
    side_b, end_radius = side_a + _KNIFE_HANDLE_WIDTH, _KNIFE_HANDLE_WIDTH / 2
    blade = _path("M0 0", f"Q-3.17 -5.34 {_KNIFE_SPINE} {seam}", f"L4.31 {seam}", "L3.68 -7.94", "C3.39 -3.48 0 0 0 0", "Z")
    handle = _rounded_polygon([(side_a, seam), (side_b, seam), (side_b, -_TOOL_LENGTH), (side_a, -_TOOL_LENGTH)],
                             [0, 0, end_radius, end_radius])
    return [_path_shape(blade, "paper", transform=_TOOL_TRANSFORM, name="blade"),
            _path_shape(handle, "ink", transform=_TOOL_TRANSFORM, name="handle")]


# Magnet: horseshoe and poles sit above the hotspot, matching the other rotated tool cursors.
_MAGNET_ORIGIN = (8, 24)
_MAGNET_OUTER = 9.8
_MAGNET_ARM = 5.93
_MAGNET_BEND_Y = -15.96
_MAGNET_POLE_Y = -4.33       # pole faces
_MAGNET_POLE_LENGTH = 5.47
_MAGNET_POLE_GAP = SW        # visible gap between a pole and the body
_MAGNET_DOT_RADIUS = 2
_MAGNET_TRANSFORM = (*_MAGNET_ORIGIN, _TOOL_TIP_ANGLE)


def _magnet() -> list[_Shape]:
    outer, inner, bend = _MAGNET_OUTER, _MAGNET_OUTER - _MAGNET_ARM, _MAGNET_BEND_Y
    pole_top = _MAGNET_POLE_Y - _MAGNET_POLE_LENGTH
    body_end = pole_top - _MAGNET_POLE_GAP
    body = _path(f"M{-outer} {body_end} V{bend} A{outer} {outer} 0 0 1 {outer} {bend} V{body_end}",
                 f"H{inner} V{bend} A{inner} {inner} 0 0 0 {-inner} {bend} V{body_end} Z")
    poles = [_rectangle(left, pole_top, left + _MAGNET_ARM, _MAGNET_POLE_Y) for left in (-outer, inner)]
    return [
        _path_shape(_path(body, *poles), "ink", transform=_MAGNET_TRANSFORM, sharp=True, name="magnet"),
        _dot(*_MAGNET_ORIGIN, _MAGNET_DOT_RADIUS, name="pivot"),
    ]


def _crosshair() -> list[_Shape]:
    """Precision crosshair with four separate arms and an open center; the arm ends touch the allowed region."""
    center, gap, near, far = _CANVAS_CENTER, 5, _LINE_INSET, _LINE_FAR_EDGE
    left_arm = f"M{near} {center} H{center - gap}"
    right_arm = f"M{center + gap} {center} H{far}"
    top_arm = f"M{center} {near} V{center - gap}"
    bottom_arm = f"M{center} {center + gap} V{far}"
    return [
        _path_shape(_path(left_arm, right_arm, top_arm, bottom_arm), "line", sharp=True, name="arms"),
        _dot(center, center, _CENTER_DOT_RADIUS),
    ]


def _artboard() -> list[_Shape]:
    """Artboard cursor with the stepped lower-right frame; the line ends touch the allowed region."""
    near, far = _LINE_INSET, _LINE_FAR_EDGE
    outline = f"M{near} 16 H11 M21 16 H{far} V{far} M16 {near} V11 M16 21 V{far} H{far}"
    return [
        _path_shape(outline, "line", sharp=True, name="frame"),
        _dot(_CANVAS_CENTER, _CANVAS_CENTER, _CENTER_DOT_RADIUS),
    ]


_CROP_RING_RADIUS = 6
_CROP_ARM_OUTER_RADIUS = _CANVAS_CENTER - _LINE_INSET   # the arm ends touch the allowed region


def _crop() -> list[_Shape]:
    """Crop tool target with arms meeting the circular ring."""
    center = _CANVAS_CENTER
    inner, outer = _CROP_RING_RADIUS, _CROP_ARM_OUTER_RADIUS
    arms = _path(
        f"M{center} {center - outer} V{center - inner}",
        f"M{center + inner} {center} H{center + outer}",
        f"M{center} {center + inner} V{center + outer}",
        f"M{center - outer} {center} H{center - inner}",
    )
    return [
        _path_shape(arms, "line", sharp=True, name="arms"),
        _circle(center, center, _CROP_RING_RADIUS, "paper", name="ring"),
        _dot(center, center, _CENTER_DOT_RADIUS),
    ]


# Crop frame: corner brackets in the allowed region; the top left corner is closed into a solid triangle
# (arrow-like) and is the hotspot.
_CROP_FRAME_ARM = 7
_CROP_FRAME_HOTSPOT = (_LINE_INSET, _LINE_INSET)


def _crop_frame() -> list[_Shape]:
    """Crop tool: arrow corner at the top left plus three corner brackets of the frame."""
    near, far, arm = _LINE_INSET, _LINE_FAR_EDGE, _CROP_FRAME_ARM
    triangle = _path(f"M{near} {near}", f"H{near + arm}", f"L{near} {near + arm}", "Z")
    top_right = f"M{far - arm} {near} H{far} V{near + arm}"
    bottom_right = f"M{far} {far - arm} V{far} H{far - arm}"
    bottom_left = f"M{near + arm} {far} H{near} V{far - arm}"
    return [
        _path_shape(triangle, "solid", name="corner"),
        _path_shape(_path(top_right, bottom_right, bottom_left), "line", sharp=True, name="brackets"),
    ]


# Note tool: a corner bracket marks the hotspot, the sheet with text lines and a folded corner sits inside it.
# The last, half-length text line is level with the top edge of the fold. Every edge and line center sits on
# a whole grid unit, so at 32 px each 2 px line covers exactly two pixel rows or columns.
_NOTE_SHEET = (9, 9, 25, 26)    # left, top, right, bottom
_NOTE_FOLD = 5
_NOTE_TEXT_INSET = 4
_NOTE_TEXT_STEP = 4
_NOTE_BRACKET_INSET = 4    # bracket corner, also the hotspot
_NOTE_BRACKET_END = 27


def _note() -> list[_Shape]:
    left, top, right, bottom = _NOTE_SHEET
    near, end, fold = _NOTE_BRACKET_INSET, _NOTE_BRACKET_END, _NOTE_FOLD
    bracket = f"M{end} {near} H{near} V{end}"
    sheet = _path(f"M{left} {top}", f"H{right}", f"V{bottom - fold}", f"L{right - fold} {bottom}", f"H{left}", "Z")
    flap = f"M{right - fold} {bottom} V{bottom - fold} H{right}"
    text_start, text_end = left + _NOTE_TEXT_INSET, right - _NOTE_TEXT_INSET
    text_rows = [bottom - fold - _NOTE_TEXT_STEP * step for step in (2, 1, 0)]
    short_end = right - fold - SW - (_NOTE_TEXT_STEP - SW)   # the gap to the fold equals the gap between rows
    text = _path(f"M{text_start} {text_rows[0]} H{text_end}", f"M{text_start} {text_rows[1]} H{text_end}",
                 f"M{text_start} {text_rows[2]} H{short_end}")
    return [
        _path_shape(bracket, "line", sharp=True, name="bracket"),
        _path_shape(sheet, "paper", sharp=True, name="sheet"),
        _path_shape(_path(flap, text), "line", top=True, sharp=True, name="fold_and_text"),
    ]


# Direction cursors: solid arrowheads at the allowed region edge, joined by shafts through the canvas center.
# A head's length equals its half width, so both head edges run exactly along the pixel diagonal.
_ARROW_REACH = _CANVAS_CENTER - _LINE_INSET   # center to arrow tip
_ARROW_HEAD_SIZE = 4
_MOVE_BADGE_REACH = 8        # neighbouring head corners stay (reach - 2 * head size) * sqrt(2) apart
_MOVE_BADGE_HEAD_SIZE = 3


def _arrow_head(direction_x: int, direction_y: int, center: int, reach: int, head_size: int) -> str:
    """Triangle path with its tip `reach` from the center, pointing along the direction."""
    tip_x, tip_y = center + direction_x * reach, center + direction_y * reach
    base_x, base_y = tip_x - direction_x * head_size, tip_y - direction_y * head_size
    side_x, side_y = -direction_y * head_size, direction_x * head_size
    return _path(f"M{tip_x} {tip_y}",
                 f"L{base_x + side_x} {base_y + side_y}",
                 f"L{base_x - side_x} {base_y - side_y}", "Z")


def _arrow_cross(horizontal: bool, vertical: bool, center: int, reach: int, head_size: int,
                 flat: bool = False) -> list[_Shape]:
    """Double arrows along the chosen axes around `center`. Builds both the direction cursors and the move badge.
    flat: unoutlined heads and a round-capped shaft, so the shaft halo stays inside the heads' halos."""
    shaft_reach = reach - head_size
    axes = [axis for axis, enabled in (((1, 0), horizontal), ((0, 1), vertical)) if enabled]
    shafts = [f"M{center - axis_x * shaft_reach} {center - axis_y * shaft_reach} "
              f"L{center + axis_x * shaft_reach} {center + axis_y * shaft_reach}"
              for axis_x, axis_y in axes]
    heads = [_arrow_head(sign * axis_x, sign * axis_y, center, reach, head_size)
             for axis_x, axis_y in axes for sign in (-1, 1)]
    return [_path_shape(_path(*shafts), "line", sharp=not flat, name="shaft"),
            _path_shape(_path(*heads), "ink" if flat else "solid", name="heads")]


def _arrows(horizontal: bool, vertical: bool) -> list[_Shape]:
    """Double arrows along the chosen axes: resize for one axis, move for both."""
    return _arrow_cross(horizontal, vertical, _CANVAS_CENTER, _ARROW_REACH, _ARROW_HEAD_SIZE)


# Rotate: an arch of less than half a circle, an arrowhead of the direction cursors turned onto each end.
_ROTATE_HALF_WIDTH = 8   # arch ends, from the canvas center
_ROTATE_RISE = 6         # arch ends up to the top of the arch
_ROTATE_TOP = 11
_ROTATE_RADIUS = (_ROTATE_HALF_WIDTH ** 2 + _ROTATE_RISE ** 2) / (2 * _ROTATE_RISE)
_ROTATE_END_ANGLE = math.degrees(math.acos(_ROTATE_HALF_WIDTH / _ROTATE_RADIUS))   # tangent tilt at the arch ends


def _rotate() -> list[_Shape]:
    left, right, end_y = _CANVAS_CENTER - _ROTATE_HALF_WIDTH, _CANVAS_CENTER + _ROTATE_HALF_WIDTH, _ROTATE_TOP + _ROTATE_RISE
    radius = number(_ROTATE_RADIUS)
    head = _arrow_head(0, 1, 0, _ARROW_HEAD_SIZE, _ARROW_HEAD_SIZE)
    return [
        _path_shape(f"M{left} {end_y} A{radius} {radius} 0 0 1 {right} {end_y}", "line", name="arch"),
        _path_shape(head, "solid", transform=(left, end_y, _ROTATE_END_ANGLE), name="head_left"),
        _path_shape(head, "solid", transform=(right, end_y, -_ROTATE_END_ANGLE), name="head_right"),
    ]


# Scissors: two blades along 3:1 and 1:3 (whole lattice steps) cross at their midpoints; each ends tangent to a ring.
_BLADE_RUN = 3                    # units along one axis per unit along the other
_SCISSORS_LENGTH = 7              # blade length in lattice steps
_SCISSORS_RING_OFFSET = (0, -3)   # ring center from the blade end: 2.85 from the blade line, the ring's centerline radius is 3
_SCISSORS_RING_RADIUS = 2         # hole radius, the outline grows outward


def _scissors_shapes(inset: int, length: int, ring_offset: tuple[int, int], ring_radius: int) -> list[_Shape]:
    """The first blade starts at (inset, inset + length); the second blade and ring mirror it across the diagonal,
    where the blades cross."""
    tip = (inset, inset + length)
    end = (inset + _BLADE_RUN * length, inset + 2 * length)
    ring = (end[0] + ring_offset[0], end[1] + ring_offset[1])
    blades = _path(f"M{tip[0]} {tip[1]} L{end[0]} {end[1]}", f"M{tip[1]} {tip[0]} L{end[1]} {end[0]}")
    return [
        _path_shape(blades, "line", name="blades"),
        _circle(*ring, ring_radius, "paper", name="ring_1"),
        _circle(*ring[::-1], ring_radius, "paper", name="ring_2"),
    ]


_SCISSORS_HOTSPOT = (_LINE_INSET + _SCISSORS_LENGTH // 2,) * 2   # between the blade tips


def _scissors() -> list[_Shape]:
    return _scissors_shapes(_LINE_INSET, _SCISSORS_LENGTH, _SCISSORS_RING_OFFSET, _SCISSORS_RING_RADIUS)


# Magic wand: a star on top of a straight stick that narrows towards it; the whole cursor rotates together.
_WAND_TILT = 45
_WAND_CENTER = (10, 10)    # hotspot: the star center
_WAND_STAR_RADIUS = 8
_WAND_TIP_WIDTH = 2
_WAND_HANDLE_WIDTH = 4
_WAND_LENGTH = 24
_WAND_STAR_STICK_GAP = 0


def _magic_wand() -> list[_Shape]:
    """Magic wand: star on a tapered stick."""
    tip_half, handle_half = _WAND_TIP_WIDTH / 2, _WAND_HANDLE_WIDTH / 2
    star_notch = pixel(_WAND_STAR_RADIUS * _STAR_INNER_RATIO)
    stick_start = star_notch + 2 * SW + _WAND_STAR_STICK_GAP - tip_half
    corners = [(-tip_half, stick_start), (tip_half, stick_start),
               (handle_half, _WAND_LENGTH), (-handle_half, _WAND_LENGTH)]
    stick = _rounded_polygon(corners, [tip_half, tip_half, handle_half, handle_half])
    return [_path_shape(_path(_star(_WAND_STAR_RADIUS), stick), "ink", transform=(*_WAND_CENTER, -_WAND_TILT), name="wand")]


# Fill (paint bucket): the bucket is drawn upright around its own origin and tilted to pour to the left;
# the drop falls below the lower rim end and its lowest point is the hotspot.
_BUCKET_TILT = 35
_BUCKET_CENTER = (18, 18)
_BUCKET_RIM_HALF = 8.7       # half width at the rim (top)
_BUCKET_BASE_HALF = 5.5      # half width at the base (bottom)
_BUCKET_HALF_HEIGHT = 7.7
_BUCKET_RIM_ROUNDING = 1.1
_BUCKET_BASE_ROUNDING = 2.2
_BUCKET_HANDLE_RISE = 8.4  # how far the handle arc rises above the rim
_DROP_HOTSPOT = (6, GRID - PADDING - H)   # the lowest point touches the bottom of the allowed region
_DROP_RADIUS = 2.6
_DROP_HEIGHT = 6.8           # from the pointed top to the lowest point


def _fill() -> list[_Shape]:
    """Paint bucket tilted to pour, with a drop under the rim."""
    transform = (*_BUCKET_CENTER, -_BUCKET_TILT)
    rim, base = -_BUCKET_HALF_HEIGHT, _BUCKET_HALF_HEIGHT
    body = _rounded_polygon([(-_BUCKET_RIM_HALF, rim), (_BUCKET_RIM_HALF, rim),
                            (_BUCKET_BASE_HALF, base), (-_BUCKET_BASE_HALF, base)],
                           [_BUCKET_RIM_ROUNDING, _BUCKET_RIM_ROUNDING, _BUCKET_BASE_ROUNDING, _BUCKET_BASE_ROUNDING])
    handle_top = rim - _BUCKET_HANDLE_RISE
    handle = _path(f"M{-_BUCKET_RIM_HALF} {rim}",
                   f"C{-_BUCKET_RIM_HALF} {handle_top} {_BUCKET_RIM_HALF} {handle_top} {_BUCKET_RIM_HALF} {rim}")
    drop_x, drop_bottom = _DROP_HOTSPOT
    drop_center_y = drop_bottom - _DROP_RADIUS
    drop_top = drop_bottom - _DROP_HEIGHT
    drop = _path(f"M{drop_x} {number(drop_top)}",
                 f"C{number(drop_x - _DROP_RADIUS * 0.5)} {number(drop_top + 2.2)} {number(drop_x - _DROP_RADIUS)} "
                 f"{number(drop_center_y - 1.2)} {number(drop_x - _DROP_RADIUS)} {number(drop_center_y)}",
                 f"A{_DROP_RADIUS} {_DROP_RADIUS} 0 0 0 {number(drop_x + _DROP_RADIUS)} {number(drop_center_y)}",
                 f"C{number(drop_x + _DROP_RADIUS)} {number(drop_center_y - 1.2)} "
                 f"{number(drop_x + _DROP_RADIUS * 0.5)} {number(drop_top + 2.2)} {drop_x} {number(drop_top)}",
                 "Z")
    return [
        _path_shape(handle, "line", transform=transform, name="bucket_handle"),
        _path_shape(body, "paper", transform=transform, name="bucket"),
        _path_shape(drop, "ink", name="drop"),
    ]


# Prohibition and help marks: each is drawn once around its own origin and serves both the standalone cursors
# (centered on the canvas) and the badges, so the same circle and question mark appear everywhere.
_NOT_ALLOWED_RADIUS = _CANVAS_CENTER - _LINE_INSET   # standalone ring touches the allowed region
_NOT_ALLOWED_BADGE_RADIUS = _MOVE_BADGE_REACH - SW / 2
_SLASH_REACH = _HALF_DIAGONAL                        # slash ends meet the ring on the nearest whole-number diagonal
_HELP_RING_RADIUS = _NOT_ALLOWED_RADIUS
_HELP_STANDALONE_HALF_WIDTH = 3
_HELP_BADGE_HALF_WIDTH = _HELP_STANDALONE_HALF_WIDTH
_HELP_DOT_RATIO = 0.5       # dot radius / mark half width
_HELP_DOT_DEPTH = 2.5       # leaves a one-unit gap below the hook's halo
_HELP_STANDALONE_DOT_DEPTH = 8 / 3  # centers the dot on the next horizontal grid line
_HELP_HOOK_HEIGHT = 7 / 3   # the hook's actual top lands on a whole grid unit
_HELP_STANDALONE_SHIFT = -1


def _not_allowed_mark(radius: float) -> list[_Shape]:
    """Ring with a slash from the top left to the bottom right, centered on the origin."""
    end = round(radius * _SLASH_REACH)
    return [
        _circle(0, 0, radius, "line", name="not_allowed_ring"),
        _path_shape(f"M{-end} {-end} L{end} {end}", "line", name="not_allowed_slash"),
    ]


def _help_mark(half_width: int, dot_depth: float = _HELP_DOT_DEPTH) -> list[_Shape]:
    """Question mark: hook over a stem and a dot, centered on the origin."""
    side, top = half_width, _HELP_HOOK_HEIGHT * half_width
    hook = _path(f"M{-side} {-side}", f"C{-side} {-top} {side} {-top} {side} {-side}", f"C{side} 0 0 0 0 {side}")
    return [
        _path_shape(hook, "line", name="help_hook"),
        _circle(0, dot_depth * half_width, half_width * _HELP_DOT_RATIO, "ink",
                name="help_dot", snap=False),   # not a dot: its halo must stay under the ring
    ]


def _centered(shapes: list[_Shape], y_shift: float = 0.0) -> list[_Shape]:
    """Moves shapes drawn around their own origin to the canvas center."""
    return [replace(shape, transform=(_CANVAS_CENTER, _CANVAS_CENTER + y_shift, 0)) for shape in shapes]


def _not_allowed() -> list[_Shape]:
    return _centered(_not_allowed_mark(_NOT_ALLOWED_RADIUS))


def _help() -> list[_Shape]:
    ring = _circle(0, 0, _HELP_RING_RADIUS, "line", name="help_ring")
    mark = _help_mark(_HELP_STANDALONE_HALF_WIDTH, _HELP_STANDALONE_DOT_DEPTH)
    return _centered([ring]) + _centered(mark, _HELP_STANDALONE_SHIFT)


# Extra elements ("badges") are attached next to a base cursor; the base is never shrunk.
# Every glyph is drawn once around its own origin (0, 0) on whole units. A small glyph (no farther than
# _BADGE_HALF_SIZE from it) sits on _BADGE_ORIGIN in the bottom right corner of the allowed region; _BADGE_SHIFT
# moves the badges of a base right and down from there: clear of the base, or room for a bulky glyph.
# The canvas of the cursor follows from where its badge ends (the hotspot stays where it was, the origin is the
# top left corner), so a canvas is never set by hand.
#   "shared" - universal marks (+, -), usable on any cursor;
#   "<base>" - marks of one tool, so a bulky mark never constrains the others.
# _add_badged() looks in the base's group first, then in "shared".
_BADGE_HALF_SIZE = 3
_BADGE_ORIGIN = GRID - PADDING - _LINE_REACH - _BADGE_HALF_SIZE
_ANCHOR_HALF_SIZE = 2        # square badge: its corner is the closest point to the arrow, so it is smaller than other glyphs
_SEGMENT_HALF_WIDTH = 3      # curve badge: arch ends from the origin
_SEGMENT_DOT_RADIUS = 2      # curve badge: end points, half the size of a full anchor dot
_SCISSORS_BADGE_LENGTH = 4
_SCISSORS_BADGE_INSET = -_BLADE_RUN * _SCISSORS_BADGE_LENGTH // 2   # blade tip: the crossing point sits on the origin
_BADGE_SHIFT = {"arrow": 3, "pen": 2}   # base -> units its badges move right and down from _BADGE_ORIGIN
_BADGES: dict[str, dict[str, list[_Shape]]] = {
    "shared": {
        "plus": [_path_shape("M-3 0 H3 M0 -3 V3", "line", sharp=True, name="plus")],
        "minus": [_path_shape("M-3 0 H3", "line", sharp=True, name="minus")],
        "ring": [_circle(0, 0, 3, "line", name="ring")],
        "anchor": [_square(0, 0, _ANCHOR_HALF_SIZE, "ink", name="anchor")],
        "segment": [
            _path_shape(f"M{-_SEGMENT_HALF_WIDTH} 2 C{-_SEGMENT_HALF_WIDTH} -4 {_SEGMENT_HALF_WIDTH} -4 {_SEGMENT_HALF_WIDTH} 2",
                        "line", name="segment_curve"),
            _circle(-_SEGMENT_HALF_WIDTH, 2, _SEGMENT_DOT_RADIUS, "ink", name="segment_start"),
            _circle(_SEGMENT_HALF_WIDTH, 2, _SEGMENT_DOT_RADIUS, "ink", name="segment_end"),
        ],
        "not_allowed": _not_allowed_mark(_NOT_ALLOWED_BADGE_RADIUS),
        "help": _help_mark(_HELP_BADGE_HALF_WIDTH),
    },
    "arrow": {
        "scissors": _scissors_shapes(_SCISSORS_BADGE_INSET, _SCISSORS_BADGE_LENGTH, (0, -2), 1),
        "move": _arrow_cross(True, True, 0, _MOVE_BADGE_REACH, _MOVE_BADGE_HEAD_SIZE, flat=True),
    },
    "pen": {
        "wave": [_path_shape("M-3 1 Q-1.5 -2 0 1 T3 1", "line", name="wave")],
        "curve": [_path_shape("M-5 3 C-1 3 -1 -3 3 -3", "line", name="curve")],
        "arc": [_path_shape("M3 -3 A4 4 0 0 0 -3 3", "line", name="arc")],
        "caret": [_path_shape("M-3 3 L0 -1 L3 3", "line", name="caret")],
    },
}

# name -> (hotspot on the 32x32 grid, shape factory)
CURSORS: dict[str, tuple[tuple[float, float], Callable[[], list[_Shape]]]] = {
    # arrow
    "arrow": (_ARROW_HOTSPOT, _arrow),
    "arrow_path_selection": (_ARROW_HOTSPOT, _arrow_path_selection),
    "arrow_direct_selection": (_ARROW_HOTSPOT, _arrow_direct_selection),
    "arrow_corner": (_ARROW_HOTSPOT, _arrow_corner),
    # type
    "type_horizontal": ((_CANVAS_CENTER, _CANVAS_CENTER), _text_cursor),
    "type_vertical": ((_CANVAS_CENTER, _CANVAS_CENTER), lambda: _text_cursor(vertical=True)),
    "type_area_horizontal": (_AREA_HOTSPOT, lambda: _text_cursor(area=True)),
    "type_area_vertical": (_turn_point(*_AREA_HOTSPOT), lambda: _text_cursor(vertical=True, area=True)),
    "type_on_path": (_AREA_HOTSPOT, _type_on_path),
    # zoom
    "zoom_in": ((_LENS_CENTER, _LENS_CENTER), lambda: _zoom("+")),
    "zoom_out": ((_LENS_CENTER, _LENS_CENTER), lambda: _zoom("-")),
    # hand
    "grab": ((_CANVAS_CENTER, _CANVAS_CENTER), lambda: _hand("grab")),
    "grabbing": ((_CANVAS_CENTER, _CANVAS_CENTER), lambda: _hand("grabbing")),
    "pointer": (_POINTER_HOTSPOT, lambda: _hand("pointer")),
    # pen
    "pen": (_TOOL_TIP, _pen_nib),
    "pencil": (_INK_TOOL_TIP, _pencil),
    "brush": (_INK_TOOL_TIP, _brush),
    # eyedropper
    "eyedropper": (_TOOL_TIP, _eyedropper),
    # crop
    "crop": ((_CANVAS_CENTER, _CANVAS_CENTER), _crop),
    "crop_frame": (_CROP_FRAME_HOTSPOT, _crop_frame),
    # direction
    "move": ((_CANVAS_CENTER, _CANVAS_CENTER), lambda: _arrows(horizontal=True, vertical=True)),
    "resize_horizontal": ((_CANVAS_CENTER, _CANVAS_CENTER), lambda: _arrows(horizontal=True, vertical=False)),
    "resize_vertical": ((_CANVAS_CENTER, _CANVAS_CENTER), lambda: _arrows(horizontal=False, vertical=True)),
    "rotate": ((_CANVAS_CENTER, _CANVAS_CENTER), _rotate),
    # selection tools
    "scissors": (_SCISSORS_HOTSPOT, _scissors),
    "magic_wand": (_WAND_CENTER, _magic_wand),
    "magnetic_lasso": (_MAGNET_ORIGIN, _magnet),
    "knife": (_TOOL_TIP, _knife),
    # other
    "crosshair": ((_CANVAS_CENTER, _CANVAS_CENTER), _crosshair),
    "artboard": ((_CANVAS_CENTER, _CANVAS_CENTER), _artboard),
    "note": ((_NOTE_BRACKET_INSET, _NOTE_BRACKET_INSET), _note),
    "fill": (_DROP_HOTSPOT, _fill),
    "not_allowed": ((_CANVAS_CENTER, _CANVAS_CENTER), _not_allowed),
    "help": ((_CANVAS_CENTER, _CANVAS_CENTER), _help),
}

_CANVAS: dict[str, tuple[float, float]] = {}

def canvas_size(name: str) -> tuple[float, float]:
    return _CANVAS.get(name, (GRID, GRID))


# How far the halo of each shape kind sticks out past its path.
_KIND_REACH = {"paper": _PAPER_REACH, "line": _LINE_REACH, "fill": _LINE_REACH, "solid": _LINE_REACH,
               "ink": H, "inverse": H, "dot": H}


def _extent(shape: _Shape) -> tuple[float, float]:
    """Farthest right and down the shape's halo reaches from its origin."""
    reach = _KIND_REACH[shape.kind]
    if shape.circle is not None:
        center_x, center_y, radius = shape.circle
        return center_x + radius + reach, center_y + radius + reach
    far_x, far_y = path_extent(shape.path)
    return far_x + reach, far_y + reach


def _add_badged(name: str, base: str, badge: str) -> None:
    """Registers cursor `name` = base cursor + badge. The hotspot is taken from the base; the square canvas grows
    past the base's if the shifted badge, with its halo and PADDING, does not fit."""
    hot, base_factory = CURSORS[base]
    shapes = _BADGES.get(base, {}).get(badge) or _BADGES["shared"][badge]
    origin = _BADGE_ORIGIN + _BADGE_SHIFT.get(base, 0)
    placed = [replace(shape, transform=(origin, origin, 0), name=f"badge_{shape.name}", group="badge")
              for shape in shapes]
    CURSORS[name] = (hot, lambda: [replace(shape, group=base) for shape in base_factory()] + placed)
    side = max(*canvas_size(base), *(math.ceil(origin + max(_extent(shape)) + PADDING) for shape in shapes))
    _CANVAS[name] = (side, side)


for _name, (_base, _badge) in {
    "pen_freeform": ("pen", "wave"),
    "pen_curvature": ("pen", "curve"),
    "pen_arc": ("pen", "arc"),
    "pen_add": ("pen", "plus"),
    "pen_delete": ("pen", "minus"),
    "pen_convert": ("pen", "caret"),
    "pen_close": ("pen", "ring"),
    "color_sampler": ("eyedropper", "ring"),
    "arrow_direct_selection_add": ("arrow_direct_selection", "plus"),
    "arrow_direct_selection_delete": ("arrow_direct_selection", "minus"),
    "arrow_direct_selection_anchor": ("arrow_direct_selection", "anchor"),
    "arrow_direct_selection_segment": ("arrow_direct_selection", "segment"),
}.items():
    _add_badged(_name, _base, _badge)
_add_badged("arrow_scissors", "arrow", "scissors")
_add_badged("arrow_move", "arrow", "move")
_add_badged("arrow_help", "arrow", "help")
_add_badged("arrow_not_allowed", "arrow", "not_allowed")


def image_side(name: str, size: int) -> int:
    """Side of the square image: size pixels per GRID units, the larger canvas side decides."""
    return round(max(canvas_size(name)) * size / GRID)


def build_svg(name: str, size: int, theme: str) -> str:
    """size = pixels per GRID units, so the scale is the same for every canvas. The geometry is fitted to that
    size and written in pixels, so the rasterizer hits whole pixels."""
    hot, factory = CURSORS[name]
    scale = size / GRID
    canvas_width, canvas_height = canvas_size(name)
    width, height = round(canvas_width * scale), round(canvas_height * scale)
    fit = Fit.for_style(scale, SW, H)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" shape-rendering="geometricPrecision">\n'
            f'<!-- hotspot: {number(hot[0])},{number(hot[1])} -->\n{_render(factory(), fit, theme=theme, cursor=name)}\n</svg>\n')