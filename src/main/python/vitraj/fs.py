from vitraj import Task
from vitraj.impl.fs_cache import Cache
from vitraj.impl.util import Event
from vitraj.impl.util.path import parent
from vitraj.url import basename, normalize
from functools import wraps
from threading import Lock

def exists(url):
	return _get_mother_fs().exists(url)

def touch(url):
	_get_mother_fs().touch(url)

def mkdir(url):
	_get_mother_fs().mkdir(url)

def makedirs(url, exist_ok=False):
	_get_mother_fs().makedirs(url, exist_ok=exist_ok)

def is_dir(existing_url):
	return _get_mother_fs().is_dir(existing_url)

def move(src_url, dst_url):
	_get_mother_fs().move(src_url, dst_url)

def prepare_move(src_url, dst_url):
	return _get_mother_fs().prepare_move(src_url, dst_url)

def move_to_trash(url):
	_get_mother_fs().move_to_trash(url)

def prepare_trash(url):
	return _get_mother_fs().prepare_trash(url)

def delete(url):
	_get_mother_fs().delete(url)

def prepare_delete(url):
	return _get_mother_fs().prepare_delete(url)

def samefile(url1, url2):
	return _get_mother_fs().samefile(url1, url2)

def copy(src_url, dst_url):
	_get_mother_fs().copy(src_url, dst_url)

def prepare_copy(src_url, dst_url):
	return _get_mother_fs().prepare_copy(src_url, dst_url)

def iterdir(url):
	return _get_mother_fs().iterdir(url)

def query(url, fs_method_name):
	return _get_mother_fs().query(url, fs_method_name)

def resolve(url):
	return _get_mother_fs().resolve(url)

def notify_file_added(url):
	_get_mother_fs().notify_file_added(url)

def notify_file_changed(url):
	_get_mother_fs().notify_file_changed(url)

def notify_file_removed(url):
	_get_mother_fs().notify_file_removed(url)

class FileSystem:

	scheme = ''

	def __init__(self):
		self.cache = Cache()
		self._file_added = Event()
		self._file_removed = Event()
		self._file_changed_callbacks = {}
		self._file_changed_callbacks_lock = Lock()
	def get_default_columns(self, path):
		return 'core.Name',
	def name(self, path):
		"""
		Displayed by the Name column.
		"""
		return path.rsplit('/', 1)[-1]
	def is_dir(self, existing_path):
		"""
		N.B.: Should raise FileNotFoundError if the given path does not exist.
		This is unlike Python's isdir(...), which returns False.
		"""
		return False
	def exists(self, path):
		try:
			self.is_dir(path)
		except FileNotFoundError:
			return False
		return True
	def resolve(self, path):
		if not self.exists(path):
			raise FileNotFoundError(self.scheme + path)
		return normalize(self.scheme + path)
	def watch(self, path):
		pass
	def unwatch(self, path):
		pass
	def notify_file_added(self, path):
		self._file_added.trigger(self.scheme + path)
	def notify_file_removed(self, path):
		self._file_removed.trigger(self.scheme + path)
	def notify_file_changed(self, path):
		for callback in self._file_changed_callbacks.get(path, []):
			callback(self.scheme + path)
	def samefile(self, path1, path2):
		return self.resolve(path1) == self.resolve(path2)
	def makedirs(self, path, exist_ok=True):
		# Copied / adapted from pathlib.Path#mkdir(...).
		try:
			self.mkdir(path)
		except FileExistsError:
			if not exist_ok or not self.is_dir(path):
				raise
		except FileNotFoundError:
			self.makedirs(parent(path))
			self.mkdir(path)
	def mkdir(self, path):
		"""
		Should raise FileExistsError if `path` already exists. If `path` is in
		a directory that does not yet exist, should raise a FileNotFoundError.
		"""
		raise self._operation_not_implemented()
	def delete(self, path):
		raise self._operation_not_implemented()
	def prepare_delete(self, path):
		if self.delete.__func__ is FileSystem.delete:
			# Does not implement #delete(...):
			raise self._operation_not_implemented()
		return [Task(
			'Deleting ' + path.rsplit('/', 1)[-1],
			fn=self.delete, args=(path,), size=1
		)]
	def move_to_trash(self, path):
		raise self._operation_not_implemented()
	def prepare_trash(self, path):
		if self.move_to_trash.__func__ is FileSystem.move_to_trash:
			# Does not implement #move_to_trash(...):
			raise self._operation_not_implemented()
		return [Task(
			'Deleting ' + path.rsplit('/', 1)[-1],
			fn=self.delete, args=(path,), size=1
		)]
	def touch(self, path):
		raise self._operation_not_implemented()
	def copy(self, src_url, dst_url):
		raise self._operation_not_implemented()
	def prepare_copy(self, src_url, dst_url):
		if self.copy.__func__ is FileSystem.copy:
			# Does not implement #copy(...):
			raise self._operation_not_implemented()
		return [Task(
			'Copying ' + basename(src_url),
			fn=self.copy, args=(src_url, dst_url)
		)]
	def move(self, src_url, dst_url):
		raise self._operation_not_implemented()
	def prepare_move(self, src_url, dst_url):
		if self.move.__func__ is FileSystem.move:
			# Does not implement #move(...):
			raise self._operation_not_implemented()
		return [Task(
			'Moving ' + basename(src_url),
			fn=self.move, args=(src_url, dst_url)
		)]
	def _operation_not_implemented(self):
		message = self.__class__.__name__ + ' does not implement this function.'
		return NotImplementedError(message)
	def _add_file_changed_callback(self, path, callback):
		with self._file_changed_callbacks_lock:
			try:
				self._file_changed_callbacks[path].append(callback)
			except KeyError:
				self._file_changed_callbacks[path] = [callback]
				self.watch(path)
	def _remove_file_changed_callback(self, path, callback):
		with self._file_changed_callbacks_lock:
			try:
				path_callbacks = self._file_changed_callbacks[path]
			except KeyError:
				raise ValueError('file_changed callback is not registered') \
				      from None
			path_callbacks.remove(callback)
			if not path_callbacks:
				del self._file_changed_callbacks[path]
				self.unwatch(path)

def cached(fs_method):
	@wraps(fs_method)
	def wrapper(self, path):
		cache_key = fs_method.__name__
		return self.cache.query(path, cache_key, lambda: fs_method(self, path))
	return wrapper

class Column:
	@classmethod
	def get_qualified_name(cls): # For internal use
		return cls.__module__ + '.' + cls.__name__
	def get_str(self, url):
		raise NotImplementedError()
	def get_sort_value(self, url, is_ascending):
		"""
		This method should generally be independent of is_ascending.
		When is_ascending is False, Qt simply reverses the sort order.
		However, we may sometimes want to change the sort order in a way other
		than a simple reversal when is_ascending is False. That's why this
		method receives is_ascending as a parameter.
		"""
		return self.get_str(url).lower()
	@property
	def display_name(self):
		return self.__class__.__name__

def _get_mother_fs():
	from vitraj.impl.application_context import get_application_context
	return get_application_context().mother_fs