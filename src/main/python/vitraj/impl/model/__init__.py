from vitraj.impl.model.model import Model
from vitraj.impl.model.drag_and_drop import DragAndDrop
from vitraj.impl.model.diff import ComputeDiff
from vitraj.impl.model.file_watcher import FileWatcher
from vitraj.impl.model.table import TableModel, Cell, Row
from vitraj.impl.util.qt.thread import run_in_main_thread
from vitraj.impl.util.url import is_pardir
from vitraj.url import dirname, splitscheme
from PyQt5.QtCore import pyqtSignal, QSortFilterProxyModel, Qt

import errno
import sip

class SortedFileSystemModel(QSortFilterProxyModel):

	location_changed = pyqtSignal(str)
	location_loaded = pyqtSignal(str)
	file_renamed = pyqtSignal(str, str)
	files_dropped = pyqtSignal(list, str, bool)
	sort_order_changed = pyqtSignal(int, int)
	transaction_ended = pyqtSignal()

	def __init__(self, parent, fs, null_location):
		super().__init__(parent)
		self._fs = fs
		self._null_location = null_location
		self._filters = []
		self._already_visited = set()
		self._num_rows_to_preload = 0
		self.set_location(null_location)
		self._fs.file_removed.add_callback(self._on_file_removed)
	def set_num_rows_to_preload(self, preload_rows):
		self._num_rows_to_preload = preload_rows
	def set_location(
		self, url, sort_column='', ascending=True, callback=None, onerror=None
	):
		if callback is None:
			callback = lambda: None
		if onerror is None:
			def onerror(*_):
				raise
		error_urls = {url}
		while True:
			try:
				self._set_location(url, sort_column, ascending, callback)
				break
			except Exception as e:
				url = onerror(e, url)
				if url in error_urls:
					raise
				error_urls.add(url)
	def _set_location(self, url, sort_column, ascending, callback):
		try:
			url_resolved = self._fs.resolve(url)
		except FileNotFoundError:
			raise
		except OSError as e:
			if e.errno == errno.ENOENT:
				raise
			# For example: On Windows, Path(...).resolve()'ing on a directory
			# in a Cryptomator mapped drive gives:
			# 	OSError: [WinError 1] Incorrect function
			# But we can still list the dir's contents and do everything else
			# that's required. So ignore the error and continue:
			url_resolved = url
		if splitscheme(url_resolved)[0] != splitscheme(url)[0]:
			# In general, we do not want to simply rewrite the URL to its
			# resolved form. This is for instance because we don't want to
			# rewrite C:\Windows\System32 -> ...\SysWOW64. However, if the
			# file system changes, we do need to follow the rewrite to support
			# cases such as zip:/// resolving to file:///.
			url = url_resolved
		old_model = self.sourceModel()
		if old_model:
			if url == old_model.get_location():
				callback()
				return
			old_model.shutdown()
		columns = self._fs.get_columns(url)
		sort_col_index = 0
		if sort_column:
			column_names = [col.get_qualified_name() for col in columns]
			try:
				sort_col_index = column_names.index(sort_column)
			except ValueError:
				pass
		if url in self._already_visited:
			orig_callback = callback
			def callback():
				orig_callback()
				self.reload()
		self._set_location_main(
			url, columns, sort_col_index, ascending, callback
		)
	@run_in_main_thread
	def _set_location_main(
		self, url, columns, sort_col_index, ascending, callback
	):
		old_model = self.sourceModel()
		if old_model:
			self._disconnect_signals(old_model)
		new_model = Model(
			self._fs, url, columns, sort_col_index, ascending,
			self._num_rows_to_preload, self._filters
		)
		self.setSourceModel(new_model)
		self._connect_signals(new_model)
		self._already_visited.add(url)
		self.location_changed.emit(url)
		order = Qt.AscendingOrder if ascending else Qt.DescendingOrder
		self.sort_order_changed.emit(sort_col_index, order)
		# Start model at the very end to ensure the above signals, in particular
		# location_changed, are processed beforehand. The motivation for this is
		# that the FilterBar relies on this signal to clear its filter. If we
		# start the model before the FilterBar has had a chance to do this, then
		# the model may start loading files with the wrong filter.
		new_model.start(callback)
	def setSourceModel(self, model):
		# Without this call, #sourceModel() sometimes returns None on Arch:
		sip.transferto(model, None)
		super().setSourceModel(model)
	def row_is_loaded(self, i):
		source_row = self.mapToSource(self.index(i, 0)).row()
		return self.sourceModel().row_is_loaded(source_row)
	def load_rows(self, rows, callback=None):
		source_rows = [self._map_row_to_source(row) for row in rows]
		self.sourceModel().load_rows(source_rows, callback)
	def _map_row_to_source(self, i):
		return self.mapToSource(self.index(i, 0)).row()
	def get_location(self):
		return self.sourceModel().get_location()
	def get_columns(self):
		return self.sourceModel().get_columns()
	def reload(self):
		self.sourceModel().reload()
	def sort(self, column, order=Qt.AscendingOrder):
		self.sourceModel().sort(column, order)
	def add_filter(self, filter_):
		self._filters.append(filter_)
		self.sourceModel().add_filter(filter_)
	def remove_filter(self, filter_):
		try:
			self._filters.remove(filter_)
		except ValueError:
			pass
		self.sourceModel().remove_filter(filter_)
	def url(self, index):
		return self.sourceModel().url(self.mapToSource(index))
	def find(self, url):
		return self.mapFromSource(self.sourceModel().find(url))
	def _on_file_removed(self, url):
		if is_pardir(url, self.get_location()):
			dir_ = dirname(url)
			if dir_ == url:
				self.set_location(self._null_location)
			else:
				try:
					self.set_location(dir_)
				except OSError:
					# In a perfect world, would like to only handle
					# FileNotFoundError here. But there can of course also be
					# other reasons. For example, when on a network share on
					# Windows, we may get a PermissionError trying to list a
					# parent directory we don't have access to. So catch all
					# OSErrors and in the worst case go to null://.
					self._on_file_removed(dir_)
	def _connect_signals(self, model):
		# Would prefer signal.connect(self.signal.emit) here. But PyQt doesn't
		# support it. So we need Python wrappers "_emit_...":
		model.location_loaded.connect(self._emit_location_loaded)
		model.location_disappeared.connect(self._on_file_removed)
		model.file_renamed.connect(self._emit_file_renamed)
		model.files_dropped.connect(self._emit_files_dropped)
		model.sort_order_changed.connect(self._emit_sort_order_changed)
		model.transaction_ended.add_callback(self._emit_transaction_ended)
	def _disconnect_signals(self, model):
		# Would prefer signal.disconnect(self.signal.emit) here. But PyQt
		# doesn't support it. So we need Python wrappers "_emit_...":
		model.location_loaded.disconnect(self._emit_location_loaded)
		model.location_disappeared.disconnect(self._on_file_removed)
		model.file_renamed.disconnect(self._emit_file_renamed)
		model.files_dropped.disconnect(self._emit_files_dropped)
		model.sort_order_changed.disconnect(self._emit_sort_order_changed)
		model.transaction_ended.remove_callback(self._emit_transaction_ended)
	def _emit_location_loaded(self, location):
		self.location_loaded.emit(location)
	def _emit_file_renamed(self, old, new):
		self.file_renamed.emit(old, new)
	def _emit_files_dropped(self, urls, dest, is_copy):
		self.files_dropped.emit(urls, dest, is_copy)
	def _emit_sort_order_changed(self, column, order):
		self.sort_order_changed.emit(column, order)
	def _emit_transaction_ended(self):
		self.transaction_ended.emit()
	def __str__(self):
		return '<%s: %s>' % (self.__class__.__name__, self.get_location())