from vitraj.fs import FileSystem, cached
from vitraj.impl.util import filenotfounderror
from vitraj.impl.util.path import normalize

class StubFileSystem(FileSystem):

	scheme = 'stub://'

	def __init__(self, items):
		super().__init__()
		self._items = items
	def exists(self, path):
		return normalize(path) in self._items
	@cached # Mirror a typical implementation
	def is_dir(self, existing_path):
		path_resolved = normalize(existing_path)
		try:
			item = self._items[path_resolved]
		except KeyError:
			raise filenotfounderror(existing_path)
		return item.get('is_dir', False)
	@cached # Mirror a typical implementation
	def size_bytes(self, path):
		return self._items[normalize(path)].get('size', 1)
	@cached # Mirror a typical implementation
	def modified_datetime(self, path):
		return self._items[normalize(path)].get('mtime', 1473339041.0)
	def touch(self, path):
		file_existed = self.exists(path)
		self._items[normalize(path)] = {}
		if not file_existed:
			self.notify_file_added(path)