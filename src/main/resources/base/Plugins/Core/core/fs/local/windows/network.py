from core.util import filenotfounderror
from vitraj.fs import FileSystem
from vitraj.url import as_url
from win32wnet import WNetOpenEnum, WNetEnumResource, error as WNetError, \
	NETRESOURCE, WNetGetResourceInformation

RESOURCE_GLOBALNET = 0x00000002
RESOURCETYPE_DISK = 0x00000001

class NetworkFileSystem(FileSystem):

	scheme = 'network://'

	def resolve(self, path):
		if '/' in path:
			return as_url(r'\\' + path.replace('/', '\\'))
		return super().resolve(path)
	def exists(self, path):
		if not path:
			return True
		nr = NETRESOURCE()
		nr.lpRemoteName = r'\\' + path.replace('/', '\\')
		try:
			WNetGetResourceInformation(nr)
		except WNetError:
			return False
		return True
	def is_dir(self, existing_path):
		if self.exists(existing_path):
			return True
		raise filenotfounderror(existing_path)
	def iterdir(self, path):
		if path:
			handle = NETRESOURCE()
			handle.lpRemoteName = r'\\' + path.replace('/', '\\')
			try:
				WNetGetResourceInformation(handle)
			except WNetError:
				raise filenotfounderror(path)
		else:
			handle = None
		for subpath in self._iter_handle(handle):
			if '/' in subpath:
				head, tail = subpath.rsplit('/', 1)
				if head == path:
					yield tail
			elif not path:
				yield subpath
	def _iter_handle(self, handle, already_visited=None):
		if already_visited is None:
			already_visited = set()
		try:
			enum = \
				WNetOpenEnum(RESOURCE_GLOBALNET, RESOURCETYPE_DISK, 0, handle)
		except WNetError:
			pass
		else:
			try:
				items = iter(WNetEnumResource(enum, 0))
				while True:
					try:
						item = next(items)
					except (StopIteration, WNetError):
						break
					else:
						path = item.lpRemoteName
						if path.startswith(r'\\'):
							yield path[2:].replace('\\', '/').rstrip('/')
						if path not in already_visited:
							already_visited.add(path)
							yield from self._iter_handle(item, already_visited)
			finally:
				enum.Close()