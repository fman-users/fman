from vitraj.impl.util import filenotfounderror
from vitraj.url import splitscheme
from functools import lru_cache
from pathlib import Path, PurePosixPath
from PyQt5.QtCore import QFileInfo
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QFileIconProvider

import logging
import sys

_LOG = logging.getLogger(__name__)

class IconProvider:
	def __init__(self, qt_icon_provider, fs, cache_dir):
		self._qt_icon_provider = qt_icon_provider
		self._fs = fs
		self._folder_icon = self._get_qt_icon(cache_dir)
		self._cache_dir = cache_dir
		self._cache = {
			f.suffix: self._get_qt_icon(f)
			for f in Path(cache_dir).glob('file*')
		}
	def get_icon(self, url):
		scheme, path = splitscheme(url)
		if scheme == 'file://':
			return self._get_qt_icon(path)
		url = self._fs.resolve(url)
		scheme, path = splitscheme(url)
		if scheme == 'file://':
			return self._get_qt_icon(path)
		if self._fs.is_dir(url):
			return self._folder_icon
		suffix = PurePosixPath(path).suffix
		if suffix not in self._cache:
			surrogate = Path(self._cache_dir, 'file' + suffix)
			with surrogate.open('w') as f:
				# At least Gnome doesn't display a proper icon unless the file
				# has some contents. So give it some:
				f.write('fman')
			self._cache[suffix] = self._get_qt_icon(surrogate)
		return self._cache[suffix]
	def _get_qt_icon(self, path):
		if not isinstance(path, str):
			path = str(path)
		return self._qt_icon_provider.icon(QFileInfo(path))

class GnomeFileIconProvider(QFileIconProvider):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		try:
			self.Gtk, self.Gio, self.GLib = self._init_pgi()
		except (ImportError, ValueError) as e:
			raise GnomeNotAvailable() from e
		else:
			# Access - and save - this constant here, in the main thread.
			# When we access it from other threads, we would otherwise sometimes
			# get "TypeError: query_info() argument 'flags'(2): Expected
			# 'FileQueryInfoFlags' but got 'FileQueryInfoFlags'".
			self._NOFOLLOW_SYMLINKS = \
				self.Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS
	def _init_pgi(self):
		import pgi
		pgi.install_as_gi()
		import gi
		gi.require_version('Gtk', '3.0')
		try:
			from gi.repository import Gtk, Gio, GLib
		except AttributeError as e:
			if e.args == (
				"'GLib' module has not attribute 'uri_list_extract_uris'",
			):
				# This happens when we run fman from source.
				sys.modules['pgi.overrides.GObject'] = None
				from gi.repository import Gtk, Gio, GLib
			else:
				raise
		# This is required when we use pgi in a PyInstaller-frozen app. See:
		# https://github.com/lazka/pgi/issues/38
		Gtk.init(sys.argv)
		return Gtk, Gio, GLib
	def icon(self, arg):
		result = None
		if isinstance(arg, QFileInfo):
			result = self._icon(arg.absoluteFilePath())
		return result or super().icon(arg)
	def _icon(self, file_path):
		try:
			file_info = self._query_gio_info(
				file_path, 'standard::icon', self._NOFOLLOW_SYMLINKS, None
			)
		except FileNotFoundError:
			raise
		except Exception:
			_LOG.exception("Could not obtain icon for %s", file_path)
		else:
			if file_info:
				icon = file_info.get_icon()
				if icon:
					icon_names = icon.get_names()
					if icon_names:
						return self._load_gtk_icon(icon_names[0])
	def _query_gio_info(self, file_path, *args):
		gio_file = self.Gio.file_new_for_path(file_path)
		try:
			return gio_file.query_info(*args)
		except self.GLib.GError as e:
			if e.message and e.message.endswith('No such file or directory'):
				raise filenotfounderror(file_path)
			else:
				raise
	@lru_cache()
	def _load_gtk_icon(self, name, size=32):
		theme = self.Gtk.IconTheme.get_default()
		if theme:
			icon = theme.lookup_icon(name, size, 0)
			if icon:
				return QIcon(icon.get_filename())

class GnomeNotAvailable(RuntimeError):
	pass