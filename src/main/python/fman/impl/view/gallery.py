"""Gallery view widget and supporting helpers.

The Qt widget classes are defined at the bottom. Pure helpers live at the
top so they can be unit-tested without spinning up a QApplication.
"""

ELLIPSIS = '…'  # "…"

# Filename truncation anchors (see design spec, section "Filename truncation"):
#   first 3 chars are sacred; last 5 are preferred but droppable.
_FIRST_N = 3
_LAST_N = 5


def truncate_filename(name, max_chars):
	"""Truncate `name` to `max_chars` while preserving the first 3 characters.

	- If `name` already fits, return it unchanged.
	- Otherwise return ``first3 + … + last5`` if that fits.
	- Otherwise return ``first3 + …`` (the last 5 are sacrificed before the
	  first 3 ever are).
	- Names shorter than 3 characters are returned unchanged.
	"""
	if len(name) <= max_chars:
		return name
	if len(name) < _FIRST_N:
		return name
	first = name[:_FIRST_N]
	last = name[-_LAST_N:]
	full = first + ELLIPSIS + last
	if len(full) <= max_chars:
		return full
	return first + ELLIPSIS

# Overlay layout (see design spec, section "Overlay layouts").
SPREAD = 'spread'
STACKED = 'stacked'
STACK_BREAKPOINT_PX = 140


def pick_overlay_layout(tile_width_px):
	"""Return ``SPREAD`` or ``STACKED`` based on tile width.

	At or above ``STACK_BREAKPOINT_PX``, the three overlay badges sit in
	the corners (TL, TR, BR). Below it, they collapse into a single
	vertical column in the top-left to avoid overlap.
	"""
	if tile_width_px >= STACK_BREAKPOINT_PX:
		return SPREAD
	return STACKED
