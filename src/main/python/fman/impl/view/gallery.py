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


from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtWidgets import QListView


DEFAULT_TILE_SIZE_PX = 160
MIN_TILE_SIZE_PX = 80
MAX_TILE_SIZE_PX = 400
TILE_SIZE_STEP_PX = 20

# Vertical padding reserved beneath the icon for the filename label.
_LABEL_AREA_PX = 28
# Horizontal padding around the tile contents.
_TILE_PADDING_PX = 12


class GalleryView(QListView):
	"""Grid/icon view for `DirectoryPaneWidget`.

	Shares the model and selection-model with the pane's `FileListView`.
	"""

	tile_size_changed = pyqtSignal(int)   # new tile size in px

	def __init__(self, parent=None):
		super().__init__(parent)
		self.setViewMode(QListView.IconMode)
		self.setMovement(QListView.Static)
		self.setResizeMode(QListView.Adjust)
		self.setWrapping(True)
		self.setFlow(QListView.LeftToRight)
		self.setUniformItemSizes(True)
		self.setWordWrap(True)
		self.setSelectionMode(QListView.ExtendedSelection)
		self.setEditTriggers(QListView.NoEditTriggers)
		self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
		self._tile_size = DEFAULT_TILE_SIZE_PX
		self._apply_tile_size()

	def set_tile_size(self, px):
		"""Clamp `px` to [MIN, MAX] and update the icon/grid size."""
		px = max(MIN_TILE_SIZE_PX, min(MAX_TILE_SIZE_PX, int(px)))
		if px == self._tile_size:
			return
		self._tile_size = px
		self._apply_tile_size()
		self.tile_size_changed.emit(px)

	def get_tile_size(self):
		return self._tile_size

	def _apply_tile_size(self):
		icon_px = self._tile_size
		self.setIconSize(QSize(icon_px, icon_px))
		self.setGridSize(QSize(
			icon_px + _TILE_PADDING_PX,
			icon_px + _LABEL_AREA_PX
		))

	def keyPressEvent(self, event):
		mod = event.modifiers()
		ctrl_or_cmd = bool(mod & Qt.ControlModifier) or bool(mod & Qt.MetaModifier)
		if ctrl_or_cmd:
			key = event.key()
			if key in (Qt.Key_Plus, Qt.Key_Equal):
				self.set_tile_size(self._tile_size + TILE_SIZE_STEP_PX)
				event.accept()
				return
			if key == Qt.Key_Minus:
				self.set_tile_size(self._tile_size - TILE_SIZE_STEP_PX)
				event.accept()
				return
			if key == Qt.Key_0:
				self.set_tile_size(DEFAULT_TILE_SIZE_PX)
				event.accept()
				return
		super().keyPressEvent(event)
