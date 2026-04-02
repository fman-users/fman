from vitraj.impl.util import Event, filenotfounderror
from vitraj.url import splitscheme, basename, dirname
from io import UnsupportedOperation
from threading import Lock

class MotherFileSystem:
	def __init__(self, icon_provider):
		super().__init__()
		self.file_added = Event()
		self.file_removed = Event()
		self._children = {}
		# Keep track of children being deleted so file_removed listeners can
		# call remove_file_changed_callback(...):
		self._children_being_deleted = {}
		self._icon_provider = icon_provider
		self._columns = {}
	def add_child(self, scheme, child):
		child._file_added.add_callback(self._on_file_added)
		child._file_removed.add_callback(self._on_file_removed)
		self._children[scheme] = child
	def remove_child(self, scheme):
		child = self._children.pop(scheme)
		child._file_removed.remove_callback(self._on_file_removed)
		child._file_added.remove_callback(self._on_file_added)
		self._children_being_deleted[scheme] = child
		self.file_removed.trigger(scheme)
		del self._children_being_deleted[scheme]
	def register_column(self, column_name, column):
		self._columns[column_name] = column
	def unregister_column(self, column_name):
		del self._columns[column_name]
	def get_registered_column_names(self):
		return list(self._columns)
	def get_columns(self, url):
		child, path = self._split(url)
		child_get_cols = child.get_default_columns
		column_names = child_get_cols(path)
		try:
			return tuple(self._columns[name] for name in column_names)
		except KeyError as e:
			available_columns = ', '.join(map(repr, self._columns))
			fn_descr = child_get_cols.__qualname__.replace('.', '#') + '(...)'
			message = '%s returned a column that does not exist: %r. ' \
					  'Should have been one of %s.' % \
					  (fn_descr, e.args[0], available_columns)
			raise KeyError(message) from None
	def exists(self, url):
		child, path = self._split(url)
		return child.exists(path)
	def iterdir(self, url):
		child, path = self._split(url)
		def compute_value():
			iterator = getattr(child, 'iterdir')(path)
			if hasattr(iterator, '__next__'):
				iterator = CachedIterator(iterator)
			return iterator
		return child.cache.query(path, 'iterdir', compute_value)
	def query(self, url, fs_method_name):
		child, path = self._split(url)
		return getattr(child, fs_method_name)(path)
	def is_dir(self, existing_url):
		return self.query(existing_url, 'is_dir')
	def icon(self, url):
		child, path = self._split(url)
		compute_icon = lambda: self._icon_provider.get_icon(url)
		return child.cache.query(path, 'icon', compute_icon)
	def touch(self, url):
		child, path = self._split(url)
		child.touch(path)
	def mkdir(self, url):
		child, path = self._split(url)
		child.mkdir(path)
	def makedirs(self, url, exist_ok=True):
		child, path = self._split(url)
		child.makedirs(path, exist_ok=exist_ok)
	def move(self, src_url, dst_url):
		"""
		:param dst_url: must be the final destination url, not just the parent
		                directory.
		"""
		src_fs, src_path = self._split(src_url)
		dst_fs, dst_path = self._split(dst_url)
		try:
			src_fs.move(src_url, dst_url)
		except (UnsupportedOperation, NotImplementedError):
			if src_fs == dst_fs:
				raise
			else:
				# Maybe the destination FS can handle the operation:
				dst_fs.move(src_url, dst_url)
	def prepare_move(self, src_url, dst_url):
		src_fs, src_path = self._split(src_url)
		dst_fs, dst_path = self._split(dst_url)
		try:
			return src_fs.prepare_move(src_url, dst_url)
		except (UnsupportedOperation, NotImplementedError):
			if src_fs == dst_fs:
				raise
			else:
				# Maybe the destination FS can handle the operation:
				try:
					return dst_fs.prepare_move(src_url, dst_url)
				except Exception as e:
					# Don't show previous UnsupportedOperation in traceback.
					raise e from None
	def move_to_trash(self, url):
		child, path = self._split(url)
		child.move_to_trash(path)
	def prepare_trash(self, url):
		child, path = self._split(url)
		return child.prepare_trash(path)
	def delete(self, url):
		child, path = self._split(url)
		child.delete(path)
	def prepare_delete(self, url):
		child, path = self._split(url)
		return child.prepare_delete(path)
	def resolve(self, url):
		child, path = self._split(url)
		return child.resolve(path)
	def samefile(self, url1, url2):
		fs_1, path_1 = self._split(self.resolve(url1))
		fs_2, path_2 = self._split(self.resolve(url2))
		return fs_1 == fs_2 and fs_1.samefile(path_1, path_2)
	def copy(self, src_url, dst_url):
		src_fs, src_path = self._split(src_url)
		dst_fs, dst_path = self._split(dst_url)
		try:
			src_fs.copy(src_url, dst_url)
		except (UnsupportedOperation, NotImplementedError):
			if src_fs == dst_fs:
				raise
			else:
				# Maybe the destination FS can handle the operation:
				try:
					dst_fs.copy(src_url, dst_url)
				except Exception as e:
					# Don't show previous UnsupportedOperation in traceback.
					raise e from None
	def prepare_copy(self, src_url, dst_url):
		src_fs, src_path = self._split(src_url)
		dst_fs, dst_path = self._split(dst_url)
		try:
			return src_fs.prepare_copy(src_url, dst_url)
		except (UnsupportedOperation, NotImplementedError):
			if src_fs == dst_fs:
				raise
			else:
				# Maybe the destination FS can handle the operation:
				try:
					return dst_fs.prepare_copy(src_url, dst_url)
				except Exception as e:
					# Don't show previous UnsupportedOperation in traceback.
					raise e from None
	def add_file_changed_callback(self, url, callback):
		child, path = self._split(url)
		child._add_file_changed_callback(path, callback)
	def remove_file_changed_callback(self, url, callback):
		scheme, path = splitscheme(url)
		try:
			child = self._children[scheme]
		except KeyError:
			try:
				child = self._children_being_deleted[scheme]
			except KeyError:
				raise filenotfounderror(url)
		child._remove_file_changed_callback(path, callback)
	def clear_cache(self, url):
		child, path = self._split(url)
		child.cache.clear(path)
	def notify_file_added(self, url):
		child, path = self._split(url)
		child.notify_file_added(path)
	def notify_file_changed(self, url):
		child, path = self._split(url)
		child.notify_file_changed(path)
	def notify_file_removed(self, url):
		child, path = self._split(url)
		child.notify_file_removed(path)
	def _on_file_added(self, url):
		self._add_to_parent(url)
		self.file_added.trigger(url)
	def _on_file_removed(self, url):
		self._remove(url)
		self.file_removed.trigger(url)
	def _split(self, url):
		scheme, path = splitscheme(url)
		try:
			child = self._children[scheme]
		except KeyError:
			raise filenotfounderror(url)
		return child, path
	def _remove(self, url):
		child, path = self._split(url)
		child.cache.clear(path)
		parent_path = splitscheme(dirname(url))[1]
		try:
			parent_files = child.cache.get(parent_path, 'iterdir')
		except KeyError:
			pass
		else:
			try:
				parent_files.remove(basename(url))
			except ValueError:
				pass
	def _add_to_parent(self, url):
		parent = dirname(url)
		child, parent_path = self._split(parent)
		try:
			parent_files = child.cache.get(parent_path, 'iterdir')
		except KeyError:
			pass
		else:
			parent_files.append(basename(url))

class CachedIterator:
	def __init__(self, source):
		self._source = source
		self._lock = Lock()
		self._items = []
		self._item_counts = {}
	def remove(self, item):
		with self._lock:
			self._record(item, delta=-1)
	def append(self, item):
		# N.B.: Behaves like set#add(...), not like list#append(...)!
		with self._lock:
			self._record(item)
	def __iter__(self):
		return _CachedIterator(self)
	def get_next(self, pointer):
		with self._lock:
			for pointer in range(pointer, len(self._items)):
				item = self._items[pointer]
				if self._item_counts[item] > 0:
					return pointer + 1, item
			while True:
				value = next(self._source) # Eventually raises StopIteration
				if self._record(value):
					return len(self._items), value
	def _record(self, value, delta=1):
		try:
			self._item_counts[value] += delta
			return False
		except KeyError:
			self._items.append(value)
			self._item_counts[value] = delta
			return True

class _CachedIterator:
	def __init__(self, parent):
		self._parent = parent
		self._pointer = 0
	def __iter__(self):
		return self
	def __next__(self):
		self._pointer, result = self._parent.get_next(self._pointer)
		return result