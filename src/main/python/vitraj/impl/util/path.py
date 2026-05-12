from fbs_runtime.platform import is_windows
from os.path import splitdrive, normpath, expanduser, realpath
from pathlib import PurePosixPath

import re

def make_absolute(file_path, cwd):
	if normpath(file_path) == '.':
		return cwd
	file_path = expanduser(file_path)
	file_path = _add_backslash_to_drive_if_missing(file_path)
	return realpath(file_path)

def _add_backslash_to_drive_if_missing(file_path): # Copied from Core plugin
	"""
	Normalize "C:" -> "C:\". Required for some path functions on Windows.
	"""
	if is_windows() and file_path:
		drive_or_unc, path = splitdrive(file_path)
		is_drive = drive_or_unc.endswith(':')
		if is_drive and file_path == drive_or_unc:
			return file_path + '\\'
	return file_path

def parent(path): # Copied from Core plugin
	if path == '/':
		return ''
	result = str(PurePosixPath(path).parent) if path else ''
	return '' if result == '.' else result

def normalize(path_):
	# Resolve a/./b and a//b:
	path_ = str(PurePosixPath(path_))
	if path_ == '.':
		path_ = ''
	# Resolve a/../b
	path_ = re.subn(r'(^|/)([^/]+)/\.\.(?:$|/)', r'\1', path_)[0]
	return path_.rstrip('/')