"""Every setting of the cursor generator lives here; cursors.py, main.py and preview.py only read it."""

# =============================== EXPORT ====================================
OUTPUT_FOLDER = "cursors_out"   # a folder given on the command line (python main.py <folder>) overrides it
EXPORT_CURSORS = ()             # cursor names to build, e.g. ("pen", "arrow"); () = all

# Themes to export per format: "dark" = white outline on black paper, "light" = black on white.
# One entry or both; () switches that format off (its old files are removed on the next build).
SVG_THEMES = ("dark",)
PNG_THEMES = ("dark", "light")
CUR_THEMES = ("dark", "light")

# Windows asks for 32 px at 100% and 40/48/56/64/72/80/96 px at 125-300% scaling; 112 and 128 serve the
# larger cursor-size settings. Each entry is grid-fitted on its own, so every size stays sharp.
CUR_SIZES = (32, 40, 48, 56, 64, 72, 80, 96, 112, 128)   # sizes of the PNG and .cur exports
SVG_SIZE = 32                   # pixels per grid unit the SVG is fitted to (32 = crisp at 1x, 2x, 3x)
CUR_SINGLE_SIZE_FILES = True    # cur/<theme>/<size>/<name>.cur, one file per size
CUR_MULTI_SIZE_FILE = True      # cur/<theme>/multi/<name>.cur, all sizes in one file, for installing

# ================================ STYLE ====================================
# Changing a number here rebuilds the whole set. SW and H must stay whole and even pixels.
GRID = 32      # logical cursor grid, fixed: all geometry is drawn on 32x32, one unit is one pixel at 100%
SW = 2         # thickness of all outlines and lines
H = 2          # halo width
PADDING = 1    # every cursor, halo included, stays this far from all four canvas edges

THEMES = {
    "dark":  {"ink": "#ffffff", "paper": "#000000", "halo": "#000000"},
    "light": {"ink": "#000000", "paper": "#ffffff", "halo": "#ffffff"},
}

# ================================ PREVIEW ==================================
EXPORT_PREVIEW = True           # preview.html
ACTUAL_SIZE = GRID              # pixels per grid unit of the 1:1 view in previews
LARGE_PIXELS_PER_UNIT = 2       # scale of the large SVG view in preview.html
PIXEL_ZOOM = 3                  # magnification of the Pixels view in preview.html
SHEET_COLUMNS = 4
SHEET_SIZES = {"": 96, "_small": ACTUAL_SIZE}   # contact sheets: file suffix -> pixels per grid unit; {} = none
