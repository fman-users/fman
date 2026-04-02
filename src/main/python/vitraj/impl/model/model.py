from vitraj.impl.model.drag_and_drop import DragAndDrop
from vitraj.impl.model.file_watcher import FileWatcher
from vitraj.impl.model.record_files import RecordFiles
from vitraj.impl.model.sorted_table import SortFilterTableModel
from vitraj.impl.model.table import Cell, Row
from vitraj.impl.model.worker import Worker
from vitraj.impl.util.qt import EditRole
from vitraj.impl.util.qt.thread import run_in_main_thread, is_in_main_thread
from vitraj.url import join, dirname
from functools import wraps, lru_cache
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QIcon, QPixmap
from threading import Event
from time import time

def transaction(priority, synchronous=False):
	def decorator(f):
		@wraps(f)
		def result(self, *args, **kwargs):
			if self._shutdown:
				return
			if synchronous:
				assert not is_in_main_thread()
				has_run = Event()
				def task():
					f(self, *args, **kwargs)
					has_run.set()
				self._worker.submit(priority, task)
				has_run.wait()
			else:
				self._worker.submit(priority, f, self, *args, **kwargs)
		return result
	return decorator

class Model(SortFilterTableModel, DragAndDrop):

	"""
	The thread safety of this class works as follows: There is one (and only
	one) worker thread that loads / computes row values in the background. Every
	changing operation is performed by it. Because there is only one thread,
	this prevents concurrent writes.

	When the worker loads / computes new data, it creates copies of the data in
	memory. Once the entire new data is loaded, @run_in_main_thread is used to
	atomically commit it to the model. This ensures that the view (which also
	runs in the main thread) does not read data that is only partially complete.

	The worker's operations are encapsulated in @transaction methods below. Each
	of these operations represents an atomic update of data.
	"""

	location_loaded = pyqtSignal(str)
	file_renamed = pyqtSignal(str, str)
	location_disappeared = pyqtSignal(str)

	def __init__(
		self, fs, location, columns, sort_column=0, ascending=True,
		num_rows_to_preload=0, filters=None
	):
		column_headers = [column.display_name for column in columns]
		super().__init__(column_headers, sort_column, ascending, filters)
		self._fs = fs
		self._location = location
		self._columns = columns
		self._num_rows_to_preload = num_rows_to_preload
		self._files = {}
		self._file_watcher = FileWatcher(fs, self)
		self._worker = Worker()
		self._shutdown = False
	def start(self, callback):
		self._worker.start()
		self._init(callback)
	@transaction(priority=1)
	def _init(self, callback):
		files = []
		try:
			file_names = iter(self._fs.iterdir(self._location))
		except FileNotFoundError:
			self.location_disappeared.emit(self._location)
			return
		while not self._shutdown:
			try:
				file_name = next(file_names)
			except FileNotFoundError:
				self.location_disappeared.emit(self._location)
				return
			except (StopIteration, OSError):
				break
			else:
				url = join(self._location, file_name)
				try:
					file_ = self._init_file(url)
				except OSError:
					continue
				files.append(file_)
		else:
			assert self._shutdown
			return
		preloaded_files = self._sorted(self._filter(files))
		for i in range(min(self._num_rows_to_preload, len(preloaded_files))):
			if self._shutdown:
				return
			try:
				preloaded_files[i] = self._load_file(preloaded_files[i].url)
			except FileNotFoundError:
				pass
		# Invoke the callback before emitting location_loaded. The reason is
		# that the default location_loaded handler places the cursor - if it has
		# not been placed yet. If the callback does place it, ugly "flickering"
		# effects happen because first the callback and then location_loaded
		# change the cursor position.
		self._on_rows_inited(files, preloaded_files, callback)
		self.location_loaded.emit(self._location)
		# Start the file watcher here, not in the main thread. This avoids a
		# deadlock: FileWatcher indirectly calls FileSystem#_add/
		# _remove_file_changed_callback(...). These are guarded by a Lock.
		# Moreover, the latter calls LocalFileSystem#unwatch(...). This is run
		# in the main thread. Now, if:
		#  1. _remove_file_changed_callback(...) obtains the lock and
		#  2. FileSystem#_add_file_changed_callback(...) is called from the main
		#     thread,
		# then _remove_... is waiting for the main thread and _add_... is
		# waiting for the lock. Deadlock.
		self._file_watcher.start()
		self._load_remaining_files()
	def _init_file(self, url):
		# Load the first column because it is used as an "anchor" when the user
		# types in arbitrary characters:
		cells = self._load_cells(url, [0])
		return File(url, _get_empty_icon(), False, cells, False)
	def _load_cells(self, url, strs_to_load=None):
		if strs_to_load is None:
			strs_to_load = range(len(self._columns))
		result = []
		for i, column in enumerate(self._columns):
			str_ = column.get_str(url) if i in strs_to_load else ''
			# Load the current sort value:
			sort_val_asc = sort_val_desc = _NOT_LOADED
			if i == self._sort_column:
				sort_value = column.get_sort_value(url, self._sort_ascending)
				if self._sort_ascending:
					sort_val_asc = sort_value
				else:
					sort_val_desc = sort_value
			result.append(Cell(str_, sort_val_asc, sort_val_desc))
		return result
	def _on_rows_inited(self, rows, preloaded_rows, callback):
		if rows:
			# Invoke the callback in the main thread. If it places the cursor,
			# this avoids flickering effects. For further details, see the
			# comment in #_on_rows_inited_main(...).
			self._on_rows_inited_main(rows, preloaded_rows, callback)
		else:
			callback()
	@run_in_main_thread
	def _on_rows_inited_main(self, rows, preloaded_rows, callback):
		self._files = {
			row.url: row for row in rows
		}
		for preloaded_row in preloaded_rows:
			self._files[preloaded_row.url] = preloaded_row
		# We have a transaction_ended listener that ensures we have a cursor.
		# It is used for example when a filter's conditions were relaxed, so
		# there are now visible files when previously there were none. However,
		# when the rows are inited, we do not want this listener to place the
		# cursor. The reason for this is that `callback` may also place the
		# cursor so we'd end up placing it twice. To avoid this, we invoke the
		# callback
		#  a) here, in the main thread and
		#  b) inside a transaction. This prevents the transaction listener from
		#     firing before the callback.
		self._begin_transaction()
		self.set_rows(preloaded_rows)
		callback()
		self._end_transaction()
	def row_is_loaded(self, rownum):
		return self._rows[rownum].is_loaded
	def load_rows(self, rownums, callback=None):
		assert is_in_main_thread()
		urls = [self._rows[i].url for i in rownums]
		self._load_files_async(urls, callback)
	@transaction(priority=2)
	def _load_files_async(self, urls, callback=None):
		self._load_files(urls, callback)
	def _load_files(self, urls, callback=None):
		files = []
		disappeared = []
		for url in urls:
			if self._shutdown:
				return
			try:
				files.append(self._load_file(url))
			except FileNotFoundError:
				disappeared.append(url)
		self._record_files(files, disappeared)
		if callback is not None:
			callback()
	def _load_file(self, url):
		try:
			is_dir = self._fs.is_dir(url)
		except FileNotFoundError:
			raise
		except OSError:
			is_dir = False
		icon = self._fs.icon(url) or _get_empty_icon()
		cells = self._load_cells(url)
		return File(url, icon, is_dir, cells, True)
	def _record_files(self, files, disappeared=None):
		# Only burden the main thread if there are actual changes:
		if files or disappeared:
			self._record_files_main(files, disappeared)
	@run_in_main_thread
	def _record_files_main(self, files, disappeared=None):
		"""
		Tells the model that the given `files` exist and the URLs given in
		`disappeared` do not exist.
		"""
		if disappeared is None:
			disappeared = []
		self._begin_transaction()
		RecordFiles(
			files, disappeared, self._files,
			self._rows, self._accepts, self._get_sortval, self._apply_diff
		)()
		self._end_transaction()
	@transaction(priority=3)
	def sort(self, column, order=Qt.AscendingOrder):
		ascending = order == Qt.AscendingOrder
		for i, row in enumerate(self._rows):
			if not self._sort_value_is_loaded(row, column, ascending):
				new_row = self._load_sort_value(row, column, ascending)
				# Here, we violate the constraint that data only be changed in
				# the main thread. But! The data we are changing here is not
				# "visible" outside this class. So it's OK.
				self._rows[i] = new_row
				self._files[row.url] = new_row
		run_in_main_thread(super().sort)(column, order)
	def _sort_value_is_loaded(self, row, column, ascending):
		try:
			self.get_sort_value(row, column, ascending)
		except RuntimeError:
			return False
		return True
	def _load_sort_value(self, row, sort_column, ascending):
		cells = []
		for i, cell in enumerate(row.cells):
			if i == sort_column:
				sort_value = self._columns[sort_column].get_sort_value(
					row.url, ascending
				)
				if ascending:
					col_val_asc = sort_value
					col_val_desc = cell.sort_value_desc
				else:
					col_val_asc = cell.sort_value_asc
					col_val_desc = sort_value
			else:
				col_val_asc = cell.sort_value_asc
				col_val_desc = cell.sort_value_desc
			cells.append(Cell(cell.str, col_val_asc, col_val_desc))
		return File(row.url, row.icon, row.is_dir, cells, row.is_loaded)
	def _accepts(self, row):
		if row.key.endswith('/..'):
			return True
		return super()._accepts(row)
	@transaction(priority=4)
	def add_filter(self, filter_):
		super().add_filter(filter_)
	@transaction(priority=4)
	def remove_filter(self, filter_):
		super().remove_filter(filter_)
	@run_in_main_thread # Because #update() is called by eg. #add_filter(...)
	def update(self):
		super().update()
	@transaction(priority=5)
	def reload(self):
		self._fs.clear_cache(self._location)
		files = []
		try:
			file_names = iter(self._fs.iterdir(self._location))
		except FileNotFoundError:
			self.location_disappeared.emit(self._location)
			return
		while not self._shutdown:
			try:
				file_name = next(file_names)
			except FileNotFoundError:
				self.location_disappeared.emit(self._location)
				return
			except (StopIteration, OSError):
				break
			else:
				url = join(self._location, file_name)
				try:
					try:
						file_before = self._files[url]
					except KeyError:
						file_ = self._init_file(url)
					else:
						if file_before.is_loaded:
							file_ = self._load_file(url)
						else:
							file_ = self._init_file(url)
				except FileNotFoundError:
					continue
				files.append(file_)
		else:
			assert self._shutdown
			return
		self._on_files_reloaded(files)
		# We may have found new files that now still need to be loaded:
		self._load_remaining_files()
	@run_in_main_thread
	def _on_files_reloaded(self, rows):
		self._files = {
			row.url: row for row in rows
		}
		self.update()
	def get_columns(self):
		return self._columns
	def get_location(self):
		return self._location
	def url(self, index):
		if not self._index_is_valid(index):
			raise ValueError("Invalid index")
		return self._rows[index.row()].url
	def find(self, url):
		try:
			rownum = self._rows.find(url)
		except KeyError:
			raise ValueError('%r is not in list' % url) from None
		return self.index(rownum, 0)
	def get_rows(self):
		return self._files.values()
	def get_sort_value(self, row, column, ascending):
		cell = row.cells[column]
		result = cell.sort_value_asc if ascending else cell.sort_value_desc
		if result is _NOT_LOADED:
			raise RuntimeError('Sort value is not loaded')
		return result
	def setData(self, index, value, role):
		if role == EditRole:
			self.file_renamed.emit(self.url(index), value)
			return True
		return super().setData(index, value, role)
	@transaction(priority=6, synchronous=True)
	def notify_file_added(self, url):
		assert dirname(url) == self._location
		self._load_files([url])
	@transaction(priority=6, synchronous=True)
	def notify_file_changed(self, url):
		assert dirname(url) == self._location
		self._fs.clear_cache(url)
		self._load_files([url])
	@transaction(priority=6, synchronous=True)
	def notify_file_renamed(self, old_url, new_url):
		assert dirname(old_url) == dirname(new_url) == self._location
		self._fs.clear_cache(old_url)
		try:
			new_file = self._load_file(new_url)
		except FileNotFoundError:
			self._record_files([], [old_url, new_url])
		else:
			self._on_file_renamed(old_url, new_file)
	@run_in_main_thread
	def _on_file_renamed(self, old_url, new_file):
		try:
			old_row = self.find(old_url).row()
		except ValueError:
			pass
		else:
			self.update_rows([new_file], old_row)
		self._record_files([new_file], [old_url])
	@transaction(priority=6, synchronous=True)
	def notify_file_removed(self, url):
		assert dirname(url) == self._location
		self._fs.clear_cache(url)
		self._record_files([], [url])
	@transaction(priority=7)
	def _load_remaining_files(self, batch_timeout=.2):
		end_time = time() + batch_timeout
		files = []
		disappeared = []
		all_loaded = False
		for row in self._rows:
			if self._shutdown:
				return
			if time() > end_time:
				break
			if row.is_loaded:
				continue
			try:
				files.append(self._load_file(row.url))
			except FileNotFoundError:
				disappeared.append(row.url)
		else:
			all_loaded = True
		self._record_files(files, disappeared)
		if not all_loaded:
			self._load_remaining_files()
	def shutdown(self):
		self._shutdown = True
		# Similarly to why we don't want to call FileWatcher#start() from the
		# main thread, we also don't want to call #shutdown() from it to avoid
		# potential deadlocks. So do it asynchronously:
		self._shutdown_async()
	@transaction(priority=1)
	def _shutdown_async(self):
		self._file_watcher.shutdown()
		self._worker.shutdown()

_NOT_LOADED = object()

class File(Row):
	def __init__(self, url, icon, is_dir, cells, is_loaded):
		super().__init__(url, icon, is_dir, cells)
		self.is_loaded = is_loaded
	@property
	def url(self):
		return self.key
	@property
	def is_dir(self):
		return self.drop_enabled

@lru_cache(maxsize=1)
@run_in_main_thread
def _get_empty_icon(size=128):
	"""
	It would be tempting to simply use `None` as an "empty" icon. But when we do
	this, Qt does not reserve the space usually taken up by the icon. (It's like
	display:none vs visibility:hidden in CSS.) This leads to ugly shifting
	effects as rows are loaded and the "empty" icon is replaced by a real one.
	To avoid this, our "empty" icon is in fact a transparent placeholder.

	The reason why this is a getter instead of a global variable is that we
	can't instantiate QPixmap at the module level. This is because QPixmap(...)
	requires a QApplication, which has not yet been instantiated at import time.
	"""
	pixmap = QPixmap(size, size)
	pixmap.fill(Qt.transparent)
	return QIcon(pixmap)