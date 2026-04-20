from fbs_runtime.platform import is_mac
from fman.impl.util.qt import Key_Tab, Key_Down, Key_Up, Key_PageDown, \
	Key_Home, Key_End, Key_PageUp, UserRole, AlignRight, AlignVCenter, \
	NoFocus, FramelessWindowHint, AlignTop, AccessibleTextRole
from PyQt5.QtCore import QAbstractListModel, QVariant, QModelIndex, QSize, \
	QPointF, QRectF, QPoint, pyqtSignal
from PyQt5.QtGui import QFont, QTextLayout, QTextCharFormat, QBrush, \
	QKeySequence
from PyQt5.QtWidgets import QDialog, QLayout, QFrame, QVBoxLayout, QLineEdit, \
	QListView, QStyledItemDelegate, QApplication, QStyle

class Quicksearch(QDialog):

	shown = pyqtSignal()

	def __init__(
		self, parent, app, css, get_items, get_tab_completion=None, query='',
		item=0
	):
		if get_tab_completion is None:
			get_tab_completion = lambda q, i: None
		super().__init__(parent, FramelessWindowHint)
		# For accessibility / screen readers:
		self.setWindowTitle('Quicksearch')
		self._app = app
		self._css = css
		self._get_items = get_items
		self._get_tab_completion = get_tab_completion
		self._initial_query = query
		self._initial_item = item
		self._curr_items = []
		self._result = None
		self._init_ui()
	def exec(self):
		self._update_items(self._initial_query)
		self._place_cursor_at_item(self._initial_item)
		if super().exec():
			return self._result
	def showEvent(self, event):
		super().showEvent(event)
		self.shown.emit()
	def _init_ui(self):
		self._query = LineEdit(self._initial_query, self)
		self._query.keyPressEventFilter = self._on_key_pressed
		self._query.textChanged.connect(self._on_text_changed)
		self._query.returnPressed.connect(self._on_return_pressed)
		self._query.setSelection(0, len(self._initial_query))
		self._items = QListView()
		self._items.setUniformItemSizes(True)
		self._items.setModel(QuicksearchListModel(self))
		self._items.setItemDelegate(QuicksearchItemDelegate(self, self._css))
		self._items.setFocusPolicy(NoFocus)
		self._items.clicked.connect(self._on_item_clicked)
		div = lambda widget: self._layout_vertically(Div(), widget)
		query_container = div(div(self._query))
		query_container.setObjectName('query-container')
		items_container = div(self._items)
		items_container.setObjectName('items-container')
		self._layout_vertically(self, query_container, items_container)
		self.layout().setSizeConstraint(QLayout.SetFixedSize)
	def _on_return_pressed(self):
		self._accept(self._items.currentIndex())
	def _on_item_clicked(self, index):
		self._accept(index)
	def _accept(self, index):
		value = self._curr_items[index.row()].value if index.isValid() else None
		self._result = self._query.text(), value
		self.accept()
	def _on_key_pressed(self, event):
		if event.key() == Key_Tab:
			index = self._items.currentIndex()
			if index.isValid():
				item = self._curr_items[index.row()]
			else:
				item = None
			completion = self._get_tab_completion(self._query.text(), item)
			if completion is not None:
				self._query.setText(completion)
				return True
		if event.key() in (Key_Down, Key_Up, Key_PageDown, Key_PageUp) or \
				is_mac() and event.key() in (Key_Home, Key_End):
			self._items.keyPressEvent(event)
			return True
		if event.matches(QKeySequence.Quit):
			self._app.exit(0)
			return True
		return False
	def _on_text_changed(self, text):
		self._update_items(text)
		self._place_cursor_at_item(0)
	def _place_cursor_at_item(self, item):
		model = self._items.model()
		row = 0
		root = self._items.rootIndex()
		while True:
			index = model.index(row, 0, root)
			if index.isValid():
				if not self._items.isIndexHidden(index):
					if item == 0:
						self._items.setCurrentIndex(index)
						break
					else:
						item -= 1
			else:
				break
			row += 1
	def _update_items(self, query):
		self._curr_items = list(self._get_items(query))
		model = self._items.model()
		model.clear()
		model.extend(self._curr_items)
		self._adjust_item_list_ize()
	def _adjust_item_list_ize(self, min_num_items_to_display=7):
		num_items = len(self._curr_items)
		row_height = self._items.sizeHintForRow(0)
		max_height = num_items * row_height
		self._items.setMaximumHeight(max_height)
		if num_items >= min_num_items_to_display:
			min_height = min_num_items_to_display * row_height
		else:
			min_height = 0
		self._items.setMinimumHeight(min_height)
	def _layout_vertically(self, parent, *widgets):
		layout = QVBoxLayout()
		layout.setContentsMargins(0, 0, 0, 0)
		layout.setSpacing(0)
		layout.setAlignment(AlignTop)
		for widget in widgets:
			layout.addWidget(widget)
		parent.setLayout(layout)
		return parent

class LineEdit(QLineEdit):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.keyPressEventFilter = None
	def keyPressEvent(self, event):
		filter_ = self.keyPressEventFilter
		if not filter_ or not filter_(event):
			super().keyPressEvent(event)

class Div(QFrame):
	pass

class QuicksearchListModel(QAbstractListModel):
	def __init__(self, parent):
		super().__init__(parent)
		self._items = []
	def rowCount(self, parent=None):
		return len(self._items)
	def clear(self):
		if self._items:
			self.beginRemoveRows(QModelIndex(), 0, len(self._items) - 1)
			self._items.clear()
			self.endRemoveRows()
	def extend(self, items):
		if items:
			start = len(self._items)
			self.beginInsertRows(QModelIndex(), start, start + len(items) - 1)
			self._items.extend(items)
			self.endInsertRows()
	def data(self, index, role):
		if not index.isValid():
			return QVariant()
		row = index.row()
		if row < self.rowCount():
			if role == ItemRole:
				return self._items[row]
			elif role == AccessibleTextRole:
				return self._items[row].title
		return QVariant()

ItemRole = UserRole

class QuicksearchItemDelegate(QStyledItemDelegate):
	def __init__(self, parent, css):
		super().__init__(parent)
		self._css = css
	def paint(self, painter, option, index):
		self._get_renderer(option, index).render(painter)
	def sizeHint(self, option, index):
		return self._get_renderer(option, index).sizeHint()
	def _get_renderer(self, option, index):
		item = index.data(ItemRole)
		self.initStyleOption(option, index)
		return QuicksearchItemRenderer(item, option, self._css)

class QuicksearchItemRenderer:
	def __init__(self, item, option, css):
		# Convert to str(...) in case the (fman API) user didn't pass a string:
		self._title = str(item.title)
		self._hint = str(item.hint)
		self._description = str(item.description)

		self._highlight = item.highlight
		self._option = option
		self._css = css
		self._widget = option.widget
		style = self._widget.style() if self._widget else QApplication.style()
		self._proxy = style.proxy()
	def render(self, painter):
		painter.save()
		painter.setClipRect(self._option.rect)
		self._draw_background(painter)
		self._draw_title(painter)
		self._draw_hint(painter)
		self._draw_description(painter)
		painter.restore()
	def sizeHint(self):
		width, height = self._layout_title()[1:]
		height += self._css['border-top-width_px'] + \
				  self._padding_top + \
				  self._css['border-bottom-width_px']
		if self._description:
			w, h = self._layout_description()[1:]
			width = max(width, w)
			height += h
		width += self._padding_left + self._padding_right
		return QSize(int(width), int(height))
	def _draw_background(self, painter):
		self._proxy.drawPrimitive(
			QStyle.PE_PanelItemViewItem, self._option, painter, self._widget
		)
	def _draw_title(self, painter):
		layout = self._layout_title()[0]
		highlight_formats = self._get_highlight_formats()
		painter.setPen(self._css['title']['color'])
		pos = self._option.rect.topLeft() \
			  + QPoint(int(self._padding_left), int(self._padding_top))
		layout.draw(painter, pos, highlight_formats)
	def _draw_hint(self, painter):
		if not self._hint:
			return
		font = QFont(self._option.font)
		font.setPointSize(int(self._css['hint']['font-size_pts']))
		painter.setFont(font)
		painter.setPen(self._css['hint']['color'])
		rect = self._get_title_rect()
		painter.drawText(rect, AlignRight | AlignVCenter, self._hint)
	def _draw_description(self, painter):
		if not self._description:
			return
		layout = self._layout_description()[0]
		painter.setPen(self._css['description']['color'])
		title_rect = self._get_title_rect()
		layout.draw(painter, QPointF(title_rect.left(), title_rect.bottom()))
	def _layout_title(self):
		font = QFont(self._option.font)
		font.setPointSize(int(self._css['title']['font-size_pts']))
		return self._layout_text(self._title, font)
	def _layout_description(self):
		font = QFont(self._option.font)
		font.setPointSize(int(self._css['description']['font-size_pts']))
		return self._layout_text(self._description, font)
	def _get_title_rect(self):
		x = self._option.rect.x() + self._padding_left
		y = self._option.rect.y() + self._padding_top
		height = self._layout_title()[2]
		padding_width = self._padding_left + self._padding_right
		width = self._option.rect.width() - padding_width
		return QRectF(x, y, width, height)
	def _layout_text(self, text, font):
		layout = QTextLayout(text, font)
		width = height = 0
		layout.beginLayout()
		while True:
			line = layout.createLine()
			if not line.isValid():
				break
			# This call is required or else we get 0 in `line.height()` below:
			line.setNumColumns(len(text))
			line.setPosition(QPointF(0, height))
			width = max(width, line.naturalTextWidth())
			height += line.height()
		layout.endLayout()
		return layout, width, height
	def _get_highlight_formats(self):
		result = []
		for highlight_start, length in self._get_highlight_ranges():
			rng = QTextLayout.FormatRange()
			rng.start = highlight_start
			rng.length = length
			fmt = QTextCharFormat()
			fmt.setFont(self._option.font)
			fmt.setFontPointSize(self._css['title']['font-size_pts'])
			fmt.setForeground(QBrush(self._css['title']['highlight']['color']))
			rng.format = fmt
			result.append(rng)
		return result
	def _get_highlight_ranges(self):
		"""
		Say we want to highlight chars [2, 3]. The easiest way would be to
		pass [FormatRange(start=2, length=1), FormatRange(start=3, length=1)] to
		Qt. Unfortunately, this doesn't work - char 3 isn't highlighted. We need
		to pass [(start=2, length=2)] instead. This function computes it.
		"""
		if not self._highlight:
			return []
		result = [(self._highlight[0], 1)]
		for highlight in self._highlight[1:]:
			start, length = result[-1]
			if start + length == highlight:
				result[-1] = (start, length + 1)
			else:
				result.append((highlight, 1))
		return result
	@property
	def _padding_top(self):
		return self._css['padding-top_px']
	@property
	def _padding_left(self):
		return self._css['padding-left_px']
	@property
	def _padding_right(self):
		return self._css['padding-right_px']