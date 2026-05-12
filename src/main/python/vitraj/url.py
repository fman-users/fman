from fbs_runtime.platform import is_windows
from vitraj.impl.util.path import parent
from pathlib import PurePath

import vitraj.impl.util.path
import posixpath
import re

def splitscheme(url):
	separator = '://'
	try:
		split_point = url.index(separator) + len(separator)
	except ValueError:
		raise ValueError('Not a valid URL: %r' % url) from None
	return url[:split_point], url[split_point:]

def as_url(local_file_path, scheme='file://'):
	# We purposely don't use Path#as_uri here because it escapes the URL.
	# For instance: Path('/a b').as_uri() returns 'file:///a%20b'. The entire
	# code base would get unnecessarily complicated if it had to escape URL
	# characters like %20 all the time. So we do not escape URLs and return
	# "file:///a b" instead:
	path = PurePath(local_file_path).as_posix()
	if path == '.':
		# This for instance happens when local_file_path == ''.
		path = ''
	result = scheme + path
	# On Windows, PurePath(\\server\folder).as_posix() ends with a slash.
	# Get rid of it:
	return re.sub(r'([^/])/$', r'\1', result)

def as_human_readable(url):
	scheme, path = splitscheme(url)
	if scheme != 'file://':
		return url
	if not is_windows():
		return path
	if re.fullmatch('[a-zA-Z]:', path):
		return path + '\\'
	return path.replace('/', '\\')

def dirname(url):
	scheme, path = splitscheme(url)
	return scheme + parent(path)

def basename(url):
	path = splitscheme(url)[1]
	return path.rsplit('/', 1)[-1]

def join(url, *paths):
	scheme, result_path = splitscheme(url)
	for path in paths:
		if path:
			if result_path and not result_path.endswith('/'):
				result_path += '/'
			result_path += path
	return scheme + result_path

def relpath(dst, src):
	dst_scheme, dst_path = splitscheme(dst)
	src_scheme, src_path = splitscheme(src)
	if src_scheme != dst_scheme:
		raise ValueError(
			"Cannot construct a relative path across different URL schemes "
			"(%s -> %s)" % (src_scheme, dst_scheme)
		)
	return posixpath.relpath(dst_path, start=src_path)

def normalize(url):
	scheme, path = splitscheme(url)
	return scheme + vitraj.impl.util.path.normalize(path)