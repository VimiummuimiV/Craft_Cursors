---
name: cursor-style-rules
description: Style, geometry and pixel-perfect rules for the shared PhotoCraft/VectorCraft cursor set (cursors.py, gridfit.py, main.py, preview.py) - 32 grid, 2 px outline and halo, grid fitting per size, hotspots, badges, padding, delivery rules. Use when drawing, editing, reviewing or exporting any cursor (SVG, PNG, .cur) of this project.
---

# Cursor Set Rules

## Files

- `cursors.py` - style constants, `Shape` primitives, every cursor's geometry, the `CURSORS` registry, `build_svg`.
- `gridfit.py` - pixel grid fitting of one render size (`Fit`, `pixel`, `number`). Knows nothing about cursors.
- `main.py` - build: padding check, SVG/PNG/.cur export, manifest. `preview.py` - preview.html and contact sheets.
- Output: `svg/`, `png/{dark,light}/<size>/name.png`, `cur/{dark,light}/<size>/name.cur`, `cur/{dark,light}/multi/name.cur` (all sizes in one file, for installing), `preview.html`, `sheet_*.png`, `cursors.json`. Run: `python main.py [out]` (needs PyQt6).

## Look

- One unified look for every program: the same tool is the same cursor in PhotoCraft and VectorCraft. Windows 11 tailless concept, thin outline, no light/dark variants of the design itself (the two themes are only the color inversion).
- Themes: `dark` = white outline on black paper (default export), `light` = black on white. Halo has the paper color.
- Glyph only, or the default cursor plus one small badge. No clutter, no blobs, no different cursor per tool unless the tool truly needs it. Path Selection reuses the standard pointer; Direct Selection uses the same silhouette with an inverse fill/outline.
- No red hotspot dot in SVGs or previews. No badges on the default arrow.
- Move/resize cursors follow the W11 concept: separate arrowheads, vertical and horizontal pairs.
- Shape kinds (use these, never raw colors): `paper` outlined light form, `fill` light form with outline over it (folds), `inverse` solid ink form with a paper-colored outline, `ink` solid, `solid` solid with outline (arrowheads), `line`, `dot` (solid circle with halo, always on top). `top=True` draws a detail above everything without halo.

## Grid and style numbers

- Logical grid 32x32; one grid unit is exactly one pixel at the base size (100% scaling).
- `SW = 2` (outline and line thickness), `H = 2` (halo width). Both must stay whole pixels and even, so centered lines land on pixel edges.
- `PADDING = 1`: every cursor, halo included, stays 1 unit from all four canvas edges. `check_padding()` stops the build and lists offenders.
- Derived: `LINE_REACH = SW/2 + H`, `PAPER_REACH = SW + H`, `LINE_INSET = PADDING + LINE_REACH` (nearest a line centerline may get to an edge, 4), `LINE_FAR_EDGE = GRID - LINE_INSET` (28). Line ends, arrow tips and tool tips use these, never literals.
- Canvas grows only when a badge does not fit (`CANVAS`); the hotspot and the top-left origin never move.

## Pixel-perfect rules

- Every coordinate of axis-aligned geometry is a whole number. Edges of `paper`/`ink` shapes and centerlines of `line`/`fill`/`solid` (even `SW`) sit on integers; the 32 base render then has zero gray fringe.
- Axis-aligned lines, brackets, arms, sheets, finger edges: `sharp=True` (square caps, mitered corners). Round caps and joins only on organic shapes and arrowheads.
- Never use half or arbitrary offsets (`3.8`, `27.4`) for anything on the grid. Hand-drawn curves keep their anchors on whole numbers; control points may be free.
- Diagonals: prefer exact 45 degrees with whole-number endpoints (arrowheads: length = half width; zoom handle edges on `x - y = +-3`; note fold). Other angles are antialiased by nature; keep their anchors on the grid and their tip on a whole pixel.
- Rotated tools (pen, eyedropper, knife, magnet at 45; scissors, wand, bucket at their tilt): draw upright around a local origin, `transform=(x, y, angle)`, with the origin (the hotspot) on a whole number. Only the origin is snapped for rotated shapes.
- Circles: whole radius and whole center keep them symmetric; the fitter moves the center to a pixel center when the outer diameter is odd.
- Equal gaps and spacings are whole numbers (text rows step 4, finger width 4, gap 2).
- Hotspot is a whole grid point, defined once in `CURSORS`, on the feature the user aims with. Hotspot pixel = `pixel(hotspot * size / GRID)` (round half up, never `round()`).

## Grid fitting per size

- `.cur` carries `CUR_SIZES = 32, 40, 48, 56, 64, 72, 80, 96, 112, 128`: Windows picks the exact size at 100-300% scaling and the cursor-size slider, so the OS never resamples. Every size is also exported as PNG and as a single-size .cur into its own folder.
- `build_svg(name, size)` fits the geometry to `size` and writes it in pixels: stroke = `SW` rounded half up, halo = `H` rounded half down (whole pixels), odd stroke centers on pixel centers, unrotated endpoints snap, control points follow their endpoint.
- Geometry passed to the fitter uses absolute path commands only (`M L H V C S Q T A Z`); relative commands raise an error.
- `render_image` must call `build_svg(name, size, ...)` with the real size, never the default, otherwise the SVG is scaled unfitted.
- The exported `svg/` files are fitted for the 32 base: crisp at 1x, 2x, 3x. A renderer that needs a fractional scale should use the fitted PNG/.cur sizes instead of scaling the SVG.

## Badges

- Glyphs are drawn once around their own origin on whole units; none reaches farther right or down than `_BADGE_HALF_SIZE` (3). All badges share `BADGE_ORIGIN` in the bottom-right corner of the allowed region.
- `shared` group: `plus`, `minus`, `ring`. Tool groups (`pen`: `wave`, `curve`, `caret`) keep bulky marks from constraining others.
- New badged cursor: one `add_badged(name, base, badge)` entry. Never copy a base cursor's shapes.

## Workflow

- One cursor at a time until approved. Keep the approved designs; change geometry only where the grid requires it, and say what moved.
- Verify after any change: build passes the padding check; at 32 px dump the alpha of the cursor (full 0/255 coverage on axis-aligned parts); look at the 32 px render zoomed with nearest-neighbor (`preview.html` Pixels view), then at 48 and 64.
- A soft pixel on an axis-aligned line or edge is a bug (off-grid coordinate, odd `SW`, wrong `sharp`), not a style choice.
- Deliver only modified files, complete, as native file attachments. Send the API zip (`cursors.py`, `gridfit.py`, `main.py`, `preview.py`, Rust manager) only when the API itself changes; otherwise just the new or changed cursor files. No markdown files in the API archive.

## Code

- Follow the personal coding rules: no duplication, no overcomplication, full descriptive names, no magic numbers in function bodies, import groups (stdlib, third party, local), one name per line in multi-name imports (functions first, then ALL-CAPS constants).
- Comments are terse one-liners only where something is genuinely non-obvious. No multi-line explanatory blocks, no file history.
- Discussion in Russian, code and comments in English.
