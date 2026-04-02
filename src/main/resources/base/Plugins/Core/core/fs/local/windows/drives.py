from core.fs.local.windows.network import NetworkFileSystem
from core.util import filenotfounderror
from ctypes import windll
from vitraj.fs import FileSystem, Column
from vitraj.url import as_url, splitscheme

import ctypes
import string

class DrivesFileSystem(FileSystem):

	scheme = 'drives://'

	NETWORK = 'Network...'

	def get_default_columns(self, path):
		return DriveName.__module__ + '.' + DriveName.__name__,
	def resolve(self, path):
		if not path:
			# Showing the list of all drives:
			return self.scheme
		if path in self._get_drives():
			return as_url(path + '\\')
		if path == self.NETWORK:
			return NetworkFileSystem.scheme
		raise filenotfounderror(path)
	def iterdir(self, path):
		if path:
			raise filenotfounderror(path)
		return self._get_drives() + [self.NETWORK]
	def is_dir(self, existing_path):
		if self.exists(existing_path):
			return True
		raise filenotfounderror(existing_path)
	def exists(self, path):
		return not path or path in self._get_drives() or path == self.NETWORK
	def _get_drives(self):
		result = []
		bitmask = windll.kernel32.GetLogicalDrives()
		for letter in string.ascii_uppercase:
			if bitmask & 1:
				result.append(letter + ':')
			bitmask >>= 1
		return result

class DriveName(Column):

	display_name = 'Name'

	def get_str(self, url):
		scheme, path = splitscheme(url)
		if scheme != 'drives://':
			raise ValueError('Unsupported URL: %r' % url)
		if path == DrivesFileSystem.NETWORK:
			return path
		result = path
		try:
			vol_name = self._get_volume_name(path + '\\')
		except WindowsError:
			pass
		else:
			if vol_name:
				result += ' ' + vol_name
		return result
	def get_sort_value(self, url, is_ascending):
		path = splitscheme(url)[1]
		# Always show "Network..." at the bottom/top:
		return path == DrivesFileSystem.NETWORK, self.get_str(url).lower()
	def _get_volume_name(self, volume_path):
		kernel32 = windll.kernel32
		buffer = ctypes.create_unicode_buffer(1024)
		if not kernel32.GetVolumeInformationW(
			ctypes.c_wchar_p(volume_path), buffer, ctypes.sizeof(buffer),
			None, None, None, None, 0
		):
			raise ctypes.WinError()
		return buffer.value