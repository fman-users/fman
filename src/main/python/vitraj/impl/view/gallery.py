"""Gallery view widget and supporting helpers.

The Qt widget classes are defined at the bottom. Pure helpers live at the
top so they can be unit-tested without spinning up a QApplication.
"""

import os

from PyQt5.QtCore import (
	QItemSelectionModel as QISM, QRect, QRectF, QSize, Qt, pyqtSignal
)
from PyQt5.QtGui import (
	QBrush, QColor, QFontMetrics, QPainter, QPainterPath, QPen
)
from PyQt5.QtWidgets import QListView, QStyle, QStyledItemDelegate

from vitraj.impl.view.context_menu import ContextMenuMixin
from vitraj.impl.view.drag_and_drop import DragAndDrop
from vitraj.impl.view.thumbnails import format_human_size
from vitraj.url import as_human_readable, splitscheme


ELLIPSIS = '…'

# Filename truncation: first 3 chars are sacred; last 5 are preferred but
# droppable when the budget can't fit ``first3 + … + last5``.
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


DEFAULT_TILE_SIZE_PX = 160
MIN_TILE_SIZE_PX = 80
MAX_TILE_SIZE_PX = 400
TILE_SIZE_STEP_PX = 20

# Vertical padding reserved beneath the icon for the filename label.
_LABEL_AREA_PX = 28
# Horizontal padding around the tile contents.
_TILE_PADDING_PX = 12

_IMAGE_EXTS = frozenset({
	'png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'tif', 'tiff', 'heic',
	'heif', 'avif', 'svg',
})


def _ext_lower(path):
	"""Return the extension of ``path`` lowercased and without the dot, or ``''``."""
	if not path:
		return ''
	return os.path.splitext(path)[1][1:].lower()


def _is_image_path(path):
	return _ext_lower(path) in _IMAGE_EXTS


def _strip_ext(name):
	if not name:
		return ''
	root, _ = os.path.splitext(name)
	return root or name


def _local_path(url):
	if not url:
		return None
	scheme, _ = splitscheme(url)
	if scheme != 'file://':
		return None
	return as_human_readable(url)


class GalleryView(ContextMenuMixin, DragAndDrop, QListView):
	"""Grid/icon view for `DirectoryPaneWidget`.

	Shares the model and selection-model with the pane's `FileListView`.
	"""

	tile_size_changed = pyqtSignal(int)   # new tile size in px

	def __init__(self, parent=None, get_context_menu=None):
		super().__init__(parent, get_context_menu=get_context_menu)
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
		# setMovement(Static) clobbered the drag flags — re-apply.
		self._install_drag_and_drop()
		# The owning DirectoryPaneWidget overrides this with a controller hook
		# so plugin shortcuts (e.g. Ctrl+G to leave gallery mode) keep working.
		self.key_press_event_filter = lambda event: False
		self._apply_tile_size(DEFAULT_TILE_SIZE_PX)

	def set_tile_size(self, px):
		"""Clamp `px` to [MIN, MAX] and update the icon/grid size."""
		px = max(MIN_TILE_SIZE_PX, min(MAX_TILE_SIZE_PX, int(px)))
		if px == self.get_tile_size():
			return
		self._apply_tile_size(px)
		self.tile_size_changed.emit(px)

	def get_tile_size(self):
		return self.iconSize().width() or DEFAULT_TILE_SIZE_PX

	def _apply_tile_size(self, px):
		self.setIconSize(QSize(px, px))
		self.setGridSize(QSize(px + _TILE_PADDING_PX, px + _LABEL_AREA_PX))

	def _handle_arrow_key(self, key, modifiers):
		model = self.model()
		if model is None or model.rowCount() == 0:
			return
		sm = self.selectionModel()
		current = sm.currentIndex()
		if not current.isValid():
			sm.setCurrentIndex(model.index(0, 0), QISM.NoUpdate)
			self.scrollTo(sm.currentIndex())
			return
		row = current.row()
		cols = max(1, self.viewport().width() // self.gridSize().width())
		if key == Qt.Key_Left:
			new_row = row - 1
		elif key == Qt.Key_Right:
			new_row = row + 1
		elif key == Qt.Key_Up:
			new_row = row - cols
		else:  # Key_Down
			new_row = row + cols
		new_row = max(0, min(new_row, model.rowCount() - 1))
		new_index = model.index(new_row, 0)
		# Match FileListView's convention: plain arrows move the cursor
		# only (no selection change). Shift+arrows extend selection.
		# Note: QAbstractItemView.setCurrentIndex() goes through
		# selectionCommand(), which for ExtendedSelection returns
		# ClearAndSelect — that would wipe the existing selection. Drive
		# the selection model directly with NoUpdate to keep selection
		# intact while moving the cursor.
		if modifiers & Qt.ShiftModifier:
			sm.select(new_index, QISM.Select | QISM.Rows)
		sm.setCurrentIndex(new_index, QISM.NoUpdate)
		self.scrollTo(new_index)

	def keyPressEvent(self, event):
		# Arrow keys are owned by the gallery view: handle them before the
		# pane's key filter so the controller doesn't report them as
		# "unassigned" shortcuts. In the regular (table) view, arrow keys
		# are intentionally unassigned because the controller defers to
		# Qt's own row navigation; here we own the grid layout, so we
		# implement navigation ourselves.
		key = event.key()
		if key in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
			self._handle_arrow_key(key, event.modifiers())
			event.accept()
			return
		if self.key_press_event_filter(event):
			return
		mod = event.modifiers()
		ctrl_or_cmd = bool(mod & Qt.ControlModifier) or bool(mod & Qt.MetaModifier)
		if ctrl_or_cmd:
			current = self.get_tile_size()
			if key in (Qt.Key_Plus, Qt.Key_Equal):
				self.set_tile_size(current + TILE_SIZE_STEP_PX)
				event.accept()
				return
			if key == Qt.Key_Minus:
				self.set_tile_size(current - TILE_SIZE_STEP_PX)
				event.accept()
				return
			if key == Qt.Key_0:
				self.set_tile_size(DEFAULT_TILE_SIZE_PX)
				event.accept()
				return
		super().keyPressEvent(event)

_OVERLAY_BG = QColor(20, 20, 28, int(0.55 * 255))
_OVERLAY_STROKE = QColor(255, 255, 255, int(0.18 * 255))
_OVERLAY_TEXT = QColor(255, 255, 255)
_OVERLAY_INSET_PX = 4
_OVERLAY_GAP_PX = 3
_OVERLAY_PADDING_X = 5
_OVERLAY_PADDING_Y = 2
_OVERLAY_RADIUS_PX = 3
_LABEL_GAP_PX = 4


class GalleryItemDelegate(QStyledItemDelegate):
	"""Paints a single gallery tile."""

	def __init__(self, get_model_url, get_thumbnail_cache, parent=None):
		super().__init__(parent)
		self._get_model_url = get_model_url
		self._get_cache = get_thumbnail_cache

	def paint(self, painter, option, index):
		painter.save()
		painter.setRenderHint(QPainter.Antialiasing, True)
		painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

		# QSS doesn't style QListView::item, so the default
		# PE_PanelItemViewItem call renders nothing here — we draw the
		# cursor fill explicitly. `cursor_bg` maps to QPalette.Highlight.
		view = option.widget
		if view is not None and index == view.currentIndex():
			painter.fillRect(option.rect, QBrush(option.palette.highlight()))

		tile_rect = option.rect
		tile_w = tile_rect.width()
		icon_size = min(tile_w, tile_rect.height() - _LABEL_AREA_PX)
		icon_rect = QRect(
			tile_rect.left() + (tile_w - icon_size) // 2,
			tile_rect.top(),
			icon_size,
			icon_size,
		)

		url = self._get_model_url(index) if self._get_model_url else None
		path = _local_path(url) if url else None
		cache = self._get_cache() if self._get_cache else None

		pixmap = None
		if path and _is_image_path(path) and cache is not None:
			pixmap = cache.get(path, icon_size)
			if pixmap is None:
				cache.request(path, icon_size)

		if pixmap is not None and not pixmap.isNull():
			scaled = pixmap.scaled(
				icon_rect.size(),
				Qt.KeepAspectRatio,
				Qt.SmoothTransformation,
			)
			x = icon_rect.left() + (icon_rect.width() - scaled.width()) // 2
			y = icon_rect.top() + (icon_rect.height() - scaled.height()) // 2
			painter.drawPixmap(x, y, scaled)
		else:
			decoration = index.data(Qt.DecorationRole)
			if decoration is not None:
				icon_px = decoration.pixmap(icon_rect.size())
				if not icon_px.isNull():
					px_scaled = icon_px.scaled(
						icon_rect.size(),
						Qt.KeepAspectRatio,
						Qt.SmoothTransformation,
					)
					x = icon_rect.left() + (icon_rect.width() - px_scaled.width()) // 2
					y = icon_rect.top() + (icon_rect.height() - px_scaled.height()) // 2
					painter.drawPixmap(x, y, px_scaled)

		name = index.data(Qt.DisplayRole) or ''
		stripped = _strip_ext(name)
		label_rect = QRect(
			tile_rect.left(),
			icon_rect.bottom() + _LABEL_GAP_PX,
			tile_w,
			_LABEL_AREA_PX - _LABEL_GAP_PX,
		)
		# Label color: match FileListView's QSS — selected items use
		# `selected_color` (QPalette.BrightText), unselected use the
		# default text color.
		if option.state & QStyle.State_Selected:
			label_color = option.palette.brightText().color()
		else:
			label_color = option.palette.text().color()
		painter.setPen(QPen(label_color))
		fm = QFontMetrics(painter.font())
		avg = max(1, fm.averageCharWidth())
		max_chars = max(0, label_rect.width() // avg)
		text = truncate_filename(stripped, max_chars)
		painter.drawText(label_rect, Qt.AlignHCenter | Qt.AlignTop, text)

		if path and _is_image_path(path) and cache is not None:
			self._paint_overlays(painter, icon_rect, path, cache)

		painter.restore()

	def _paint_overlays(self, painter, icon_rect, path, cache):
		ext = _ext_lower(path).upper()
		size_bytes = cache.get_size_bytes(path)
		size_text = format_human_size(size_bytes) if size_bytes is not None else None
		resolution = cache.get_resolution(path)
		res_text = '%d×%d' % (resolution.width(), resolution.height()) \
			if resolution is not None else None

		layout = pick_overlay_layout(icon_rect.width())

		if layout == SPREAD:
			if ext:
				self._draw_badge(painter, ext, icon_rect, anchor='tl')
			if res_text:
				self._draw_badge(painter, res_text, icon_rect, anchor='tr')
			if size_text:
				self._draw_badge(painter, size_text, icon_rect, anchor='br')
		else:
			max_col_w = int(icon_rect.width() * 0.6)
			fm = QFontMetrics(painter.font())
			y = icon_rect.top() + _OVERLAY_INSET_PX
			x = icon_rect.left() + _OVERLAY_INSET_PX
			# (text, should_elide) in display order. Only resolution elides —
			# extension and size are already short.
			rows = [
				(ext, False),
				(res_text, True),
				(size_text, False),
			]
			for text, should_elide in rows:
				if not text:
					continue
				display = text
				if should_elide:
					display = fm.elidedText(
						text, Qt.ElideRight,
						max_col_w - 2 * _OVERLAY_PADDING_X
					)
				w, h = self._badge_size(painter, display)
				w = min(w, max_col_w)
				self._fill_badge(painter, QRect(x, y, w, h), display)
				y += h + _OVERLAY_GAP_PX

	def _badge_size(self, painter, text):
		fm = QFontMetrics(painter.font())
		w = fm.horizontalAdvance(text) + 2 * _OVERLAY_PADDING_X
		h = fm.height() + 2 * _OVERLAY_PADDING_Y
		return w, h

	def _draw_badge(self, painter, text, icon_rect, anchor):
		w, h = self._badge_size(painter, text)
		if anchor == 'tl':
			rect = QRect(
				icon_rect.left() + _OVERLAY_INSET_PX,
				icon_rect.top() + _OVERLAY_INSET_PX,
				w, h
			)
		elif anchor == 'tr':
			rect = QRect(
				icon_rect.right() - _OVERLAY_INSET_PX - w,
				icon_rect.top() + _OVERLAY_INSET_PX,
				w, h
			)
		else:
			rect = QRect(
				icon_rect.right() - _OVERLAY_INSET_PX - w,
				icon_rect.bottom() - _OVERLAY_INSET_PX - h,
				w, h
			)
		self._fill_badge(painter, rect, text)

	def _fill_badge(self, painter, rect, text):
		path = QPainterPath()
		path.addRoundedRect(
			QRectF(rect),
			_OVERLAY_RADIUS_PX,
			_OVERLAY_RADIUS_PX,
		)
		painter.fillPath(path, _OVERLAY_BG)
		painter.setPen(QPen(_OVERLAY_STROKE, 1))
		painter.drawPath(path)
		painter.setPen(QPen(_OVERLAY_TEXT))
		painter.drawText(rect, Qt.AlignCenter, text)
