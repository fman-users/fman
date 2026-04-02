from vitraj.impl.util.qt import DisplayRole, EditRole, ToolTipRole, DecorationRole
from PyQt5.QtCore import QAbstractTableModel, QModelIndex, QVariant
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QTableView

class UniformRowHeights(QTableView):
	"""
	Performance improvement.
	"""
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._row_height = None
	def sizeHintForRow(self, row):
		model = self.model()
		if row < 0 or row >= model.rowCount():
			# Mirror super implementation.
			return -1
		return self.get_row_height()
	def get_row_height(self):
		if self._row_height is None:
			self._row_height = max(self._get_cell_heights())
		return self._row_height
	def changeEvent(self, event):
		# This for instance happens when the style sheet changed. It may affect
		# the calculated row height. So invalidate:
		self._row_height = None
		super().changeEvent(event)
	def dataChanged(self, top, bottom, roles):
		if top != bottom or not top.isValid(): # As in super().dataChanged(...)
			visible = self.get_visible_row_range()
			# Performance improvement: QTableView's default implementation
			# issues a full repaint for any multi-cell change. Avoid this if
			# the affected rows aren't even visible.
			# We use `top.row() >= ...` instead of just `>` because
			# `visible.stop` is exclusive, while `top.row()` is inclusive.
			if top.row() >= visible.stop or bottom.row() < visible.start:
				# Without _any_ call to super().dataChanged(...), there are
				# delays when opening a directory with many files and scrolling
				# page-down a few times. Maybe this is because the associated
				# row updates are swallowed? Either way, do call
				# dataChanged(...) but with a single cell to not trigger Qt's
				# full repaint:
				super().dataChanged(top, top, roles)
				return
		super().dataChanged(top, bottom, roles)
	def get_visible_row_range(self):
		header = self.verticalHeader()
		start = self._get_row_at(0)
		if start == -1:
			start = 0
		stop = self._get_row_at(header.viewport().height()) + 1
		if stop == 0:
			stop = self.model().rowCount()
		return range(start, stop)
	def _get_row_at(self, y):
		"""
		The implementation of this method has gone through several iterations:

		First, QHeaderView#logicalIndexAt(...) was used.

		To improve performance, QHeaderView#visualIndexAt(...) was then used
		instead because (at least at the time of this writing) we don't have
		hidden rows. This was roughly twice as fast as logicalIndexAt(...) and
		saved a few hundred ms.

		The present iteration is faster still: Displaying 5000 files and
		scrolling page down four times cost 3 seconds. With the current
		implementation (which seems to provide the same results), this is down
		to 0.00s. At the same time, this implementation should(!) return exactly
		the same results as QHeaderView#visualIndexAt(...).
		"""
		header = self.verticalHeader()
		if not header.count():
			# Mimic header.visualIndexAt(y):
			return -1
		else:
			y_abs = y + header.offset()
			row_height = self.get_row_height()
			total_height = self.model().rowCount() * row_height
			if y_abs >= total_height:
				# Mimic header.visualIndexAt(y):
				return -1
			else:
				return y_abs // row_height
	def _get_cell_heights(self, row=0):
		self.ensurePolished()
		option = self.viewOptions()
		model = self.model()
		dummy_model = DummyModel(
			model.rowCount(), model.columnCount(), option.decorationSize
		)
		for column in range(model.columnCount()):
			index = dummy_model.index(row, column)
			delegate = self.itemDelegate(index)
			if delegate:
				yield delegate.sizeHint(option, index).height()

class DummyModel(QAbstractTableModel):
	"""
	The purpose of this model is to let UniformRowHeights "fake" table rows
	without requiring access to the actual data.
	"""
	def __init__(self, num_rows, num_cols, decoration_size):
		super().__init__()
		self._num_rows = num_rows
		self._num_cols = num_cols
		self.decoration_size = decoration_size
	def rowCount(self, parent=QModelIndex()):
		if parent.isValid():
			# According to the Qt docs for QAbstractItemModel#rowCount(...):
			# "When implementing a table based model, rowCount() should
			#  return 0 when the parent is valid."
			return 0
		return self._num_rows
	def columnCount(self, parent=QModelIndex()):
		if parent.isValid():
			# According to the Qt docs for QAbstractItemModel#columnCount(...):
			# "When implementing a table based model, columnCount() should
			#  return 0 when the parent is valid."
			return 0
		return self._num_cols
	def data(self, index, role=DisplayRole):
		if role in (DisplayRole, EditRole, ToolTipRole):
			return QVariant('')
		elif role == DecorationRole:
			return QPixmap(self.decoration_size)
		return QVariant()
