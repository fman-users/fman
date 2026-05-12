from vitraj import DirectoryPaneCommand, show_alert
from vitraj.fs import resolve
from vitraj.url import splitscheme, as_human_readable, basename, dirname
from pywintypes import com_error
from win32com.shell.shell import SHILCreateFromPath, SHGetDesktopFolder, \
	IID_IShellFolder, IID_IContextMenu
from win32com.shell.shellcon import CMF_EXPLORE

import ctypes.wintypes
import re
import win32gui

class ShowExplorerProperties(DirectoryPaneCommand):

	aliases = 'Properties',

	def __call__(self):
		scheme = splitscheme(self.pane.get_path())[0]
		if scheme not in ('file://', 'drives://', 'network://'):
			show_alert(
				'Sorry, showing the properties of %s files is not '
				'yet supported.' % scheme
			)
		else:
			action = self._get_action()
			if action:
				action()
	def _get_action(self):
		file_under_cursor = self.pane.get_file_under_cursor()
		selected_files = self.pane.get_selected_files()
		chosen_files = selected_files or \
		               ([file_under_cursor] if file_under_cursor else [])
		location = self.pane.get_path()
		scheme, path = splitscheme(location)
		if scheme == 'file://':
			if file_under_cursor is None:
				# Either we're in an empty folder, or the user
				# right-clicked inside a directory.
				if self._is_drive(path):
					return lambda: _show_drive_properties(path)
				else:
					dir_ = as_human_readable(dirname(location))
					filenames = [basename(location)]
			else:
				dir_ = as_human_readable(location)
				filenames = [basename(f) for f in chosen_files]
			return lambda: _show_file_properties(dir_, filenames)
		elif scheme == 'drives://':
			if file_under_cursor is None:
				# This usually happens when the user right-clicked in the drive
				# overview (but not _on_ a drive).
				return None
			drive = splitscheme(file_under_cursor)[1]
			if self._is_drive(drive):
				return lambda: _show_drive_properties(drive)
		elif scheme == 'network://':
			# We check `path` because when it's empty, we're at the
			# overview of network locations. Servers don't have a Properties
			# dialog. So we can't do anything there.
			if path:
				for f in chosen_files:
					try:
						f_fileurl = resolve(f)
					except OSError:
						continue
					if splitscheme(f_fileurl)[0] != 'file://':
						# Sanity check. We don't actually expect this.
						continue
					dir_ = as_human_readable(dirname(f_fileurl))
					break
				else:
					return
				filenames = [basename(f) for f in chosen_files]
				return lambda: _show_file_properties(dir_, filenames)
	def is_visible(self):
		return bool(self._get_action())
	def _is_drive(self, path):
		return re.match('^[A-Z]:$', path)

def _show_file_properties(dir_, filenames):
	# Note: If you ever want to extend this method so it can handle files in
	# multiple directories, take a look at SHMultiFileProperties and [1].
	# [1]: https://stackoverflow.com/a/34551988/1839209.
	folder = SHILCreateFromPath(dir_, 0)[0]
	desktop = SHGetDesktopFolder()
	shell_folder = desktop.BindToObject(folder, None, IID_IShellFolder)
	children = []
	for filename in filenames:
		try:
			pidl = shell_folder.ParseDisplayName(None, None, filename)[1]
		except com_error:
			pass
		else:
			children.append(pidl)
	cm = shell_folder.GetUIObjectOf(None, children, IID_IContextMenu, 0)[1]
	if not cm:
		return
	hMenu = win32gui.CreatePopupMenu()
	cm.QueryContextMenu(hMenu, 0, 1, 0x7FFF, CMF_EXPLORE)
	cm.InvokeCommand((0, None, 'properties', '', '', 1, 0, None))
	cm.QueryContextMenu(hMenu, 0, 1, 0x7FFF, CMF_EXPLORE)

def _show_drive_properties(drive_nobackslash):
	sei = SHELLEXECUTEINFO()
	sei.cbSize = ctypes.sizeof(sei)
	sei.fMask = _SEE_MASK_NOCLOSEPROCESS | _SEE_MASK_INVOKEIDLIST
	sei.lpVerb = "properties"
	sei.lpFile = drive_nobackslash + '\\'
	sei.nShow = 1
	ShellExecuteEx(ctypes.byref(sei))

_SEE_MASK_NOCLOSEPROCESS = 0x00000040
_SEE_MASK_INVOKEIDLIST = 0x0000000C

class SHELLEXECUTEINFO(ctypes.Structure):
	_fields_ = (
		("cbSize", ctypes.wintypes.DWORD),
		("fMask", ctypes.c_ulong),
		("hwnd", ctypes.wintypes.HANDLE),
		("lpVerb", ctypes.c_wchar_p),
		("lpFile", ctypes.c_wchar_p),
		("lpParameters", ctypes.c_char_p),
		("lpDirectory", ctypes.c_char_p),
		("nShow", ctypes.c_int),
		("hInstApp", ctypes.wintypes.HINSTANCE),
		("lpIDList", ctypes.c_void_p),
		("lpClass", ctypes.c_char_p),
		("hKeyClass", ctypes.wintypes.HKEY),
		("dwHotKey", ctypes.wintypes.DWORD),
		("hIconOrMonitor", ctypes.wintypes.HANDLE),
		("hProcess", ctypes.wintypes.HANDLE),
	)

ShellExecuteEx = ctypes.windll.shell32.ShellExecuteExW
ShellExecuteEx.restype = ctypes.wintypes.BOOL