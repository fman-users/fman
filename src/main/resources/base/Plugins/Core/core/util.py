from vitraj.url import dirname
from os import listdir, strerror
from os.path import join
from pathlib import PurePosixPath

import errno
import vitraj.fs

def strformat_dict_values(dict_, replacements):
	result = {}
	def replace(value):
		if isinstance(value, str):
			return value.format(**replacements)
		return value
	for key, value in dict_.items():
		if isinstance(value, list):
			value = list(map(replace, value))
		else:
			value = replace(value)
		result[key] = value
	return result

def listdir_absolute(dir_path):
	return [join(dir_path, file_name) for file_name in listdir(dir_path)]

def filenotfounderror(path):
	# The correct way of instantiating FileNotFoundError in a way that respects
	# the parent class (OSError)'s arguments:
	return FileNotFoundError(errno.ENOENT, strerror(errno.ENOENT), path)

def parent(path):
	if path == '/':
		return ''
	result = str(PurePosixPath(path).parent) if path else ''
	return '' if result == '.' else result

def is_parent(dir_url, file_url, fs=vitraj.fs):
	for parent_url in _iter_parents(file_url):
		try:
			if fs.samefile(parent_url, dir_url):
				return True
		except FileNotFoundError:
			continue
	return False

def _iter_parents(url):
	while True:
		yield url
		new_url = dirname(url)
		if new_url == url:
			break
		url = new_url