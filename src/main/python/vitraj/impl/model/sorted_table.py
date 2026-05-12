from vitraj.impl.model.table import TableModel
from PyQt5.QtCore import Qt, pyqtSignal

class SortFilterTableModel(TableModel):

	sort_order_changed = pyqtSignal(int, int)

	def __init__(
		self, column_headers, sort_column=0, ascending=True, filters=None
	):
		super().__init__(column_headers)
		self._sort_column = sort_column
		self._sort_ascending = ascending
		self._filters = [] if filters is None else list(filters)
	def get_rows(self):
		"""
		Implement to give this class the unfiltered, unsorted rows.
		"""
		raise NotImplementedError()
	def get_sort_value(self, row, column, ascending):
		"""
		Return the sort value for the given row. N.B.: row is a Row, not int.
		"""
		raise NotImplementedError()
	def update(self):
		"""
		Call this after any change in the output of #get_rows().
		"""
		self.set_rows(self._sorted(self._filter(self.get_rows())))
	def _sorted(self, rows):
		return sorted(
			rows, key=self._get_sortval, reverse=not self._sort_ascending
		)
	def _get_sortval(self, row):
		return self.get_sort_value(row, self._sort_column, self._sort_ascending)
	def _filter(self, rows):
		return filter(self._accepts, rows)
	def _accepts(self, row):
		return all(f(row.key) for f in self._filters)
	def sort(self, column, order=Qt.AscendingOrder):
		ascending = order == Qt.AscendingOrder
		if (column, ascending) == (self._sort_column, self._sort_ascending):
			return
		self.layoutAboutToBeChanged.emit([], self.VerticalSortHint)
		self._sort_column = column
		self._sort_ascending = ascending
		new_rows = self._sorted(self._rows)
		for index in self.persistentIndexList():
			old_row = self._rows[index.row()]
			for i, row in enumerate(new_rows):
				if row.key == old_row.key:
					self.changePersistentIndex(
						index, self.index(i, index.column())
					)
					break
		self._rows.reset_to(new_rows)
		self.layoutChanged.emit([], self.VerticalSortHint)
		self.sort_order_changed.emit(column, order)
	def add_filter(self, filter_):
		self._filters.append(filter_)
		self.update()
	def remove_filter(self, filter_):
		try:
			self._filters.remove(filter_)
		except ValueError:
			pass
		self.update()