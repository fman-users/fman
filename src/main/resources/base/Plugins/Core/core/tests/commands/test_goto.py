from core.commands.goto import _shrink_visited_paths, SuggestLocations
from core.util import filenotfounderror
from vitraj import PLATFORM
from os.path import normpath
from unittest import TestCase, skipIf

import os

class ShrinkVisiblePathsTest(TestCase):
	def test_basic(self):
		vps = {'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5}
		_shrink_visited_paths(vps, 3)
		self.assertEqual({'c': 1, 'd': 2, 'e': 3}, vps)
	def test_multiple_similar(self):
		vps = {'a': 1, 'b': 1, 'c': 3, 'd': 3, 'e': 5}
		_shrink_visited_paths(vps, 3)
		self.assertEqual({'c': 1, 'd': 1, 'e': 2}, vps)

class SuggestLocationsTest(TestCase):

	class StubLocalFileSystem:
		def __init__(self, files, home_dir):
			self.files = files
			self.home_dir = home_dir
		def isdir(self, path):
			if PLATFORM == 'Windows' and path.endswith(' '):
				# Strange behaviour on Windows: isdir('X ') returns True if X
				# (without space) exists.
				path = path.rstrip(' ')
			try:
				self._get_dir(path)
			except KeyError:
				return False
			return True
		def _get_dir(self, path):
			if not path:
				raise KeyError(path)
			path = normpath(path)
			parts = path.split(os.sep) if path != os.sep else ['']
			if len(parts) > 1 and parts[-1] == '':
				parts = parts[:-1]
			curr = self.files
			for part in parts:
				for file_name, items in curr.items():
					if self._normcase(file_name) == self._normcase(part):
						curr = items
						break
				else:
					raise KeyError(part)
			return curr
		def expanduser(self, path):
			return path.replace('~', self.home_dir)
		def listdir(self, path):
			try:
				return sorted(list(self._get_dir(path)))
			except KeyError as e:
				raise filenotfounderror(path) from e
		def resolve(self, path):
			is_case_sensitive = PLATFORM == 'Linux'
			if is_case_sensitive:
				return path
			dir_ = os.path.dirname(path)
			if dir_ == path:
				# We're at the root of the file system.
				return path
			dir_ = self.resolve(dir_)
			try:
				dir_contents = self.listdir(dir_)
			except OSError:
				matching_names = []
			else:
				matching_names = [
					f for f in dir_contents
					if f.lower() == os.path.basename(path).lower()
				]
			if not matching_names:
				return path
			return os.path.join(dir_, matching_names[0])
		def samefile(self, f1, f2):
			return self._get_dir(f1) == self._get_dir(f2)
		def find_folders_starting_with(self, prefix):
			return list(
				self._find_folders_recursive(self.files, prefix.lower()))
		def _find_folders_recursive(self, files, prefix):
			for f, subfiles in files.items():
				if f.lower().startswith(prefix):
					yield f
				for sub_f in self._find_folders_recursive(subfiles, prefix):
					# We don't use join(...) here because of the case f=''. We
					# want '/sub_f' but join(f, sub_f) would give just 'sub_f'.
					yield f + os.sep + sub_f
		def _normcase(self, path):
			return path if PLATFORM == 'Linux' else path.lower()

	def test_empty_suggests_recent_locations(self):
		expected_paths = [
			'~/Dropbox/Work', '~/Dropbox', '~/Downloads', '~/Dropbox/Private',
			'~/s-u-b-s-t-r', '~/My-substr', '~'
		]
		self._check_query_returns(
			'', expected_paths, [[]] * len(expected_paths)
		)
	def test_basename_matches(self):
		self._check_query_returns(
			'dow', ['~/Downloads', '~/Dropbox/Work'], [[2, 3, 4], [2, 4, 10]]
		)
	def test_exact_match_takes_precedence(self):
		expected_paths = [
			'~', '~/Dropbox', '~/Downloads', '~/s-u-b-s-t-r', '~/My-substr',
			'~/.hidden', '~/Unvisited'
		]
		self._check_query_returns(
			'~', expected_paths, [[0]] * len(expected_paths)
		)
	def test_prefix_match(self):
		self._check_query_returns('~/dow', ['~/Downloads'], [[0, 1, 2, 3, 4]])
	def test_existing_path(self):
		self._check_query_returns(
			'~/Unvisited', ['~/Unvisited', '~/Unvisited/Dir']
		)
	@skipIf(PLATFORM == 'Linux', 'Case-insensitive file systems only')
	def test_existing_path_wrong_case(self):
		self._check_query_returns(
			'~/unvisited', ['~/Unvisited', '~/Unvisited/Dir']
		)
	def test_enter_path_slash(self):
		highlight = list(range(len('~/Unvisited')))
		self._check_query_returns(
			'~/Unvisited/', ['~/Unvisited', '~/Unvisited/Dir'],
			[highlight, highlight]
		)
	def test_trailing_space(self):
		self._check_query_returns('~/Downloads ', [])
	def test_hidden(self):
		self._check_query_returns('~/.', ['~/.hidden'])
	def test_filesystem_search(self):
		# No visited paths:
		self.instance = SuggestLocations({}, self.fs)
		# Should still find Downloads by prefix:
		self._check_query_returns('dow', ['~/Downloads'], [[2, 3, 4]])
	def test_home_dir_expanded(self):
		self._check_query_returns(
			os.path.dirname(self.home_dir),
			[os.path.dirname(self.home_dir), self.home_dir]
		)
	def test_substring(self):
		# Should return My-substr before ~/s-u-b-s-t-r even though the latter
		# has a higher count:
		self._check_query_returns(
			'sub', ['~/My-substr', '~/s-u-b-s-t-r'], [[5, 6, 7], [2, 4, 6]]
		)
	def setUp(self):
		root = 'C:' if PLATFORM == 'Windows' else ''
		files = {
			root: {
				'Users': {
					'michael': {
						'.hidden': {},
						'Downloads': {},
						'Dropbox': {
							'Work': {}, 'Private': {}
						},
						'Unvisited': {
							'Dir': {}
						},
						'My-substr': {},
						's-u-b-s-t-r': {},
					}
				}
			},
			'.': {}
		}
		if PLATFORM == 'Windows':
			self.home_dir = r'C:\Users\michael'
		else:
			self.home_dir = '/Users/michael'
		self.fs = self.StubLocalFileSystem(files, home_dir=self.home_dir)
		visited_paths = {
			self._replace_pathsep(self.fs.expanduser(k)): v
			for k, v in [
				('~', 1),
				('~/Downloads', 5),
				('~/Dropbox', 6),
				('~/Dropbox/Work', 7),
				('~/Dropbox/Private', 4),
				('~/My-substr', 2),
				('~/s-u-b-s-t-r', 3) # Note: Higher count than My-substr
			]
		}
		self.instance = SuggestLocations(visited_paths, self.fs)
	def _check_query_returns(self, query, paths, highlights=None):
		query = self._replace_pathsep(query)
		paths = list(map(self._replace_pathsep, paths))
		if highlights is None:
			highlights = [self._full_range(query)] * len(paths)
		result = list(self.instance(query))
		self.assertEqual(paths, [item.title for item in result])
		self.assertEqual(highlights, [item.highlight for item in result])
	def _replace_pathsep(self, path):
		return path.replace('/', os.sep)
	def _full_range(self, string):
		return list(range(len(string)))