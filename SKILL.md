---
name: cursor-style-rules
description: Style, geometry and pixel-perfect rules for the shared PhotoCraft/VectorCraft... cursor set (config.py, cursors.py, gridfit.py, main.py, preview.py) - single config file, 32 grid, 2 px outline and halo, grid fitting per size, hotspots, badges, padding, delivery rules. Use when drawing, editing, reviewing or exporting any cursor (SVG, PNG, .cur) of this project.
---

# Cursor Set Rules

## Files

- `config.py` - the single place for every setting (see Config). Imports nothing from the project.
- `cursors.py` - derived style constants, `_Shape` primitives, every cursor's geometry, the `CURSORS` registry, `build_svg`.
- `gridfit.py` - pixel grid fitting of one render size (`Fit`, `pixel`, `number`, `path_extent`; one path parser shared by fitting and extents). Knows nothing about cursors.
- `main.py` - build: padding check, SVG/PNG/.cur export, stale generated-file cleanup, manifest. `preview.py` - preview.html and contact sheets.
- `requirements.txt` - `PyQt6` only (PNG/.cur rendering, contact sheets). `config.py`, `cursors.py` and `gridfit.py` use the standard library; `preview.html` loads html2canvas from a CDN for its Save PNG button.
- Output: `svg/<theme>/name.svg`, `png/{dark,light}/<size>/name.png`, `cur/{dark,light}/<size>/name.cur`, `cur/{dark,light}/multi/name.cur` (all sizes in one file, for installing), `preview.html`, `sheet_*.png`, `cursors.json`. Run: `pip install -r requirements.txt`, then `python main.py [out]`; the folder argument is optional, `OUTPUT_FOLDER` is the default.

## Config

- Every setting that is worth changing lives in `config.py`, with a one-line comment: output folder, `EXPORT_CURSORS` (() = all), `SVG_THEMES` / `PNG_THEMES` / `CUR_THEMES` (themes exported per format, () switches the format off), `CUR_SIZES`, `SVG_SIZE`, `CUR_SINGLE_SIZE_FILES`, `CUR_MULTI_SIZE_FILE`, style (`GRID`, `SW`, `H`, `PADDING`, `THEMES` palette), preview options (`EXPORT_PREVIEW`, `ACTUAL_SIZE`, `LARGE_PIXELS_PER_UNIT`, `PIXEL_ZOOM`, `SHEET_COLUMNS`, `SHEET_SIZES`).
- Nothing is changed by hunting through code or by console flags: a new tunable setting goes into `config.py` and the other files import it from there. Never define the same setting twice and never hard-code a value that has a config entry.
- No implicit default theme: `build_svg`, `_render` and `_render_image` take `theme` explicitly; each export format reads its own theme list. Themes shape no geometry, so the padding check uses the first theme of `THEMES`.
- `main.py` stops with a list when `config.py` names an unknown theme or cursor. Stale files of a format or theme that was switched off are removed, together with emptied folders; with `EXPORT_CURSORS` set, files of the other cursors stay.
- Defaults reproduce the approved output byte for byte (SVG: dark only); verify that after touching the build code.

## Look

- One unified look for every program: the same tool is the same cursor in PhotoCraft and VectorCraft. Windows 11 tailless concept, thin outline, no light/dark variants of the design itself (the two themes are only the color inversion).
- Themes: `dark` = white outline on black paper (default export), `light` = black on white. Halo has the paper color.
- Glyph only, or the default cursor plus one small badge. No clutter, no blobs, no different cursor per tool unless the tool truly needs it. Path Selection reuses the standard pointer; Direct Selection uses the same silhouette with an inverse fill/outline.
- No red hotspot dot in SVGs or previews. No badges on the default arrow.
- Move/resize cursors follow the W11 concept: separate arrowheads, vertical and horizontal pairs.
- Type Tool: `type_horizontal` and `type_vertical` use the same centered I-beam, oriented to match the writing direction. `type_area_horizontal` and `type_area_vertical` (dragging a text frame) move the beam left (up) and add a framed T on the right (below); vertical is the horizontal one turned a quarter turn clockwise.
- Underscore rule: a name used only inside its own file starts with `_` (functions, variables, constants, classes: `_arrow`, `_LINE_INSET`, `_Shape`, `_render_image`); a name used by other files, or meant for outside code, has no underscore (`CURSORS`, `build_svg`, `canvas_size`, `image_side`, `Fit`, `pixel`, `number`, `path_extent`, `contact_sheet`, `preview_html`, `qcursor`, every `config.py` setting). A name that gains a second user in another file loses its underscore, and one that loses all outside users gets it. Check this on every new or edited name.
- Names: a cursor derived from another carries its root's name as a prefix, `<root>_<variant>` (`arrow_corner`, `arrow_direct_selection_add`, `pen_close`), so the origin is clear from the name alone; modifiers come last (`_add`, `_delete`). Registry keys, exported files and factory functions use the same name.
- Arrow-family cursors share a silhouette shifted 2 units up-left, with its hotspot shifted equally, to fit the Corner arc and selection modifiers on 32x32.
- Corner Tool combines the pointer with a rounded-corner arc.
- Prohibition (`not_allowed`, the disabled / not-clickable state; CSS `not-allowed`, Windows "Unavailable") and `help` (CSS `help`, Windows "Help Select") are one family: `_not_allowed_mark(radius)` (ring plus a slash from top left to bottom right, ends on the whole-number diagonal) and `_help_mark(half_width)` (hook, stem, dot, whole anchors) are drawn once around their origin. The standalone cursors (`not_allowed`, `help`: the same marks in a ring of radius 12, hotspot at the center) and the badges (`shared` `not_allowed` radius 5, `help` half width 2) both come from them, so `arrow_not_allowed` and `arrow_help` match the standalone ones. The badge `help` has no ring; the standalone `help` adds it. Any base may take these badges, but a base other than `arrow` needs its own `_BADGE_SHIFT`.
- Shape kinds (use these, never raw colors): `paper` outlined light form, `fill` light form with outline over it (folds), `inverse` solid ink form with a paper-colored outline, `ink` solid, `solid` solid with outline (arrowheads), `line`, `dot` (solid circle with halo, always on top). `top=True` draws a detail above everything without halo.

## Grid and style numbers

- Logical grid 32x32; one grid unit is exactly one pixel at the base size (100% scaling).
- `SW = 2` (outline and line thickness), `H = 2` (halo width), both in `config.py`. Both must stay whole pixels and even, so centered lines land on pixel edges. `GRID = 32` is fixed: all geometry is drawn on it.
- `PADDING = 1` (`config.py`): every cursor, halo included, stays 1 unit from all four canvas edges. `_check_padding()` stops the build and lists offenders.
- Derived: `_LINE_REACH = SW/2 + H`, `_PAPER_REACH = SW + H`, `_LINE_INSET = PADDING + _LINE_REACH` (nearest a line centerline may get to an edge, 4), `_LINE_FAR_EDGE = GRID - _LINE_INSET` (28). Line ends, arrow tips and tool tips use these, never literals.
- The canvas is 32x32 unless a badge needs more room; then it grows (square, right and down) by itself, see Badges. Never set a canvas by hand. When cursor artwork is translated, translate its hotspot equally.

## Pixel-perfect rules

- Every coordinate of axis-aligned geometry is a whole number. Edges of `paper`/`ink` shapes and centerlines of `line`/`fill`/`solid` (even `SW`) sit on integers; the 32 base render then has zero gray fringe.
- Axis-aligned lines, brackets, arms, sheets, finger edges: `sharp=True` (square caps, mitered corners). Round caps and joins only on organic shapes and arrowheads.
- Never use half or arbitrary offsets (`3.8`, `27.4`) for anything on the grid. Hand-drawn curves keep their anchors on whole numbers; control points may be free.
- Diagonals: prefer exact 45 degrees with whole-number endpoints (arrowheads: length = half width; zoom handle edges on `x - y = +-3`; note fold). Other angles are antialiased by nature; keep their anchors on the grid and their tip on a whole pixel.
- Rotated tools (pen, eyedropper, knife, magnet at 45; wand, bucket at their tilt): draw upright around a local origin, `transform=(x, y, angle)`, with the origin (the hotspot) on a whole number. Only the origin is snapped for rotated shapes.
- Scissors are lattice geometry: blades run along 3:1 and 1:3 between whole points and cross at their midpoints, each ring is tangent to its blade end (whole center and radius, within 0.15 px). `_scissors()` builds both the tool and the `arrow_scissors` badge.
- Circles: whole radius and whole center keep them symmetric; the fitter moves the center to a pixel center when the outer diameter is odd.
- Equal gaps and spacings are whole numbers (text rows step 4, finger width 4, gap 2).
- Hotspot is a whole grid point, defined once in `CURSORS`, on the feature the user aims with. Hotspot pixel = `pixel(hotspot * size / GRID)` (round half up, never `round()`).

## Grid fitting per size

- `.cur` carries `CUR_SIZES = 32, 40, 48, 56, 64, 72, 80, 96, 112, 128` (`config.py`): Windows picks the exact size at 100-300% scaling and the cursor-size slider, so the OS never resamples. Every size is also exported as PNG and as a single-size .cur into its own folder.
- `build_svg(name, size)` fits the geometry to `size` and writes it in pixels: stroke = `SW` rounded half up, halo = `H` rounded half down (whole pixels), odd stroke centers on pixel centers, unrotated endpoints snap, control points follow their endpoint.
- Geometry passed to the fitter uses absolute path commands only (`M L H V C S Q T A Z`); relative commands raise an error.
- `_render_image` must call `build_svg(name, size, ...)` with the real size, never the default, otherwise the SVG is scaled unfitted.
- The exported `svg/<theme>/` files are fitted for `SVG_SIZE` (32 by default): crisp at 1x, 2x, 3x. A renderer that needs a fractional scale should use the fitted PNG/.cur sizes instead of scaling the SVG.

## Badges

- Glyphs are drawn once around their own origin (0, 0) on whole units; a glyph is centered on it (scissors: the crossing point, move: the cross center). Small glyphs reach no farther than `_BADGE_HALF_SIZE` (3) and share `_BADGE_ORIGIN` in the bottom-right corner of the allowed region; bulky glyphs are allowed, they only need a shift.
- `shared` group: `plus`, `minus`, `ring`, `not_allowed`, `help`. Tool groups (`pen`: `wave`, `curve`, `caret`; `arrow`: `scissors`, `move`) keep bulky marks from constraining others.
- A badge never sits flush against the base: keep about 3 px of clear space between the badge ink and the base ink at 32 px, or the pair does not read. Measure it (render base group and badge group apart at 10 px per unit, ink-to-ink distance), do not judge by eye.
- One mechanism places every badge: `_BADGE_SHIFT` (base -> units its badges move right and down from `_BADGE_ORIGIN`; `arrow`: 3, `pen`: 2, absent = 0). It gives clearance from the base or room for a bulky glyph; never bake an offset into a glyph. The canvas is derived: `_add_badged()` takes the farthest reach of the glyph's shapes (`_extent`: path extent plus the halo of the kind) from the shifted origin plus `PADDING`, rounded up, square, never smaller than the base's. So there is no hand-set canvas, no 40x40 constant, and no bigger canvas for cursors that do not need it (`pen_*` 34, `arrow_scissors` 40, `arrow_move` 39, `arrow_help` 38, `arrow_not_allowed` 37, the rest 32). A bigger canvas never creates clearance, only room. The hotspot never moves.
- `_arrow_cross()` builds the move/resize cursors and the `arrow_move` badge (`flat=True`: unoutlined heads, round-capped shaft, so the shaft halo cannot poke out past the heads). Neighbouring head corners must stay `(reach - 2 * head size) * sqrt(2)` apart, at least about 2.8 px, otherwise the halos fuse into one blob. The badge cross is centered on its origin; the arrow shift keeps it clear of the arrow tip.
- New badged cursor: one `_add_badged(name, base, badge)` entry. Never copy a base cursor's shapes.

## SVG structure

- Every cursor is one `<g id="<cursor name>">`. A cursor with a badge nests two groups in it: the base cursor's group (named after the base: `arrow`, `pen`, `eyedropper`) and `badge`. A cursor without a badge holds its elements directly in the cursor group.
- One element per `Shape`, id = `Shape.name`, plus `<name>_halo` and `<name>_fill` (the halo and the paper eraser). Every shape gets a short descriptive name (`pointer`, `lens`, `nib`, `sheet`), never an editor default like Path or Curve. Ids are unique per file and use underscores, no hyphens.
- Inside a group the painting order is halo, outline, fill, details. Groups paint in document order, base first and badge on top, so a badge halo can trim a few pixels of the base outline where they touch (`pen_add`, `pen_delete`, `pen_close`, `pen_freeform`).
- New shape: pass `name=`. `_BADGES` glyphs are named by the glyph; `_add_badged()` adds the `badge_` prefix and the `badge` group and marks the base shapes with the base name. A variant built by hand (`arrow_corner`) sets `group="arrow"` on the base shapes and `group="badge"` on the badge itself.

## Workflow

- One cursor at a time until approved. Keep the approved designs; change geometry only where the grid requires it, and say what moved.
- Verify after any change: build passes the padding check; at 32 px dump the alpha of the cursor (full 0/255 coverage on axis-aligned parts); look at the 32 px render zoomed with nearest-neighbor (`preview.html` Pixels view), then at 48 and 64. SVG: the first `<g>` is named after the cursor, ids are unique and underscore-only.
- A soft pixel on an axis-aligned line or edge is a bug (off-grid coordinate, odd `SW`, wrong `sharp`), not a style choice.
- Deliver only modified files, complete, as native file attachments. Send the API zip (`config.py`, `cursors.py`, `gridfit.py`, `main.py`, `preview.py`, Rust manager) only when the API itself changes; otherwise just the new or changed cursor files. No markdown files in the API archive.

## Code

- Settings go to `config.py` (see Config); constants derived from them stay next to their use.
- Follow the personal coding rules: no duplication, no overcomplication, full descriptive names, no magic numbers in function bodies, import groups (stdlib, third party, local), one name per line in multi-name imports (functions first, then ALL-CAPS constants).
- Comments are terse one-liners only where something is genuinely non-obvious. No multi-line explanatory blocks, no file history.