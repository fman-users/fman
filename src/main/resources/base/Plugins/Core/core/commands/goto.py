from core.commands.util import get_user, is_hidden
from core.quicksearch_matchers import path_starts_with, basename_starts_with, \
	contains_substring, contains_chars
from vitraj import DirectoryPaneCommand, show_quicksearch, PLATFORM, load_json, \
	DirectoryPaneListener, QuicksearchItem
from vitraj.fs import exists, resolve
from vitraj.url import as_url, splitscheme, as_human_readable
from itertools import islice, chain
from os.path import expanduser, islink, isabs, normpath
from pathlib import Path, PurePath
from random import shuffle
from time import time

import os
import re
import sys

__all__ = ['GoTo', 'GoToListener']

class GoTo(DirectoryPaneCommand):
	def __call__(self, query=''):
		visited_paths = self._get_visited_paths()
		get_items = SuggestLocations(visited_paths)
		result = show_quicksearch(get_items, self._get_tab_completion, query)
		if result:
			url = self._get_target_location(*result)
			if exists(url):
				# Use OpenDirectory because it handles errors gracefully:
				self.pane.run_command('open_directory', {'url': url})
			else:
				path = as_human_readable(url)
				_remove_from_visited_paths(visited_paths, path)
	def _get_target_location(self, query, suggested_dir):
		if suggested_dir:
			# The suggested_dir is for instance set when the user clicks on it
			# with the mouse. If set, it always takes precedence. So return it:
			return as_url(suggested_dir)
		url = as_url(expanduser(query.rstrip()))
		if PLATFORM == 'Windows' and re.match(r'\\[^\\]', query):
			# Resolve '\Some\dir' to 'C:\Some\dir'.
			try:
				url = resolve(url)
			except OSError:
				pass
		return url
	def _get_tab_completion(self, query, curr_item):
		if curr_item:
			result = curr_item.title
			if not result.endswith(os.sep):
				result += os.sep
			return result
	def _get_visited_paths(self):
		# TODO: Rename to Visited Locations.json?
		result = load_json('Visited Paths.json', default={})
		# Check for length 2 because the directories in which fman opens are
		# already in Visited Paths:
		if len(result) <= 2:
			result.update({
				path: 0 for path in self._get_default_paths()
			})
		return result
	def _get_default_paths(self, exclude={'/proc', '/run', '/sys'}):
		home_dir = expanduser('~')
		result = set(self._get_nonhidden_subdirs(home_dir))
		# Add directories in C:\ on Windows, or / on Unix:
		try:
			children = Path(PurePath(sys.executable).anchor).iterdir()
		except OSError:
			pass
		else:
			for child in children:
				if str(child) in exclude:
					continue
				try:
					if child.is_dir():
						try:
							next(iter(child.iterdir()))
						except StopIteration:
							pass
						else:
							result.add(str(child))
				except OSError:
					pass
		if PLATFORM == 'Linux':
			media_user = os.path.join('/media', get_user())
			if os.path.exists(media_user):
				result.add(media_user)
			# We need to add more suggestions on Linux, because unlike Windows
			# and Mac, we (currently) do not integrate with the OS's native
			# search functionality:
			result.update(islice(self._traverse_by_mtime(home_dir), 500))
			result.update(
				islice(self._traverse_by_mtime('/', exclude=exclude), 500)
			)
		return result
	def _get_nonhidden_subdirs(self, dir_path):
		for file_name in os.listdir(dir_path):
			file_path = os.path.join(dir_path, file_name)
			if os.path.isdir(file_path) and not is_hidden(file_path):
				yield os.path.join(dir_path, file_name)
	def _traverse_by_mtime(self, dir_path, exclude=None):
		if exclude is None:
			exclude = set()
		to_visit = [(os.stat(dir_path), dir_path)]
		already_yielded = set()
		while to_visit:
			stat, parent = to_visit.pop()
			if parent in exclude:
				continue
			yield parent
			try:
				parent_contents = os.listdir(parent)
			except OSError:
				continue
			for file_name in parent_contents:
				if file_name.startswith('.'):
					continue
				file_path = os.path.join(parent, file_name)
				try:
					if not os.path.isdir(file_path) or islink(file_path):
						continue
				except OSError:
					continue
				try:
					stat = os.stat(file_path)
				except OSError:
					pass
				else:
					already_yielded.add(stat.st_ino)
					to_visit.append((stat, file_path))
			to_visit.sort(key=lambda tpl: tpl[0].st_mtime)

class GoToListener(DirectoryPaneListener):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.is_first_path_change = True
	def on_path_changed(self):
		if self.is_first_path_change:
			# on_path_changed() is also called when fman starts. Since this is
			# not a user-initiated path change, we don't want to count it:
			self.is_first_path_change = False
			return
		url = self.pane.get_path()
		scheme, path = splitscheme(url)
		if scheme != 'file://':
			return
		visited_paths = \
			load_json('Visited Paths.json', default={}, save_on_quit=True)
		# Ensure we're using backslashes \ on Windows:
		path = as_human_readable(url)
		visited_paths[path] = visited_paths.get(path, 0) + 1
		if len(visited_paths) > 500:
			_shrink_visited_paths(visited_paths, 250)
		else:
			# Spend a little time cleaning up outdated paths. This method is
			# called asynchronously, so no problem performing some work here.
			_remove_nonexistent(visited_paths, timeout_secs=0.01)

def _shrink_visited_paths(vps, size):
	paths_per_count = {}
	for p, count in vps.items():
		paths_per_count.setdefault(count, []).append(p)
	count_paths = sorted(paths_per_count.items())
	# Remove least frequently visited paths until we reach the desired size:
	while len(vps) > size:
		count, paths = count_paths[0]
		del vps[paths.pop()]
		if not paths:
			count_paths = count_paths[1:]
	# Re-scale those paths that are left. This gives more recent paths a chance
	# to rise to the top. Eg. {'a': 1000, 'b': 1} -> {'a': 2, 'b': 1}.
	for i, (count, paths) in enumerate(count_paths):
		for p in paths:
			vps[p] = i + 1

def _remove_nonexistent(vps, timeout_secs):
	# Randomly check visited paths for existence, until the timeout expires.
	# Choose all elts. with equal probability. It's tempting to be more clever
	# and use the visit counts somehow. But it's not clear this will be better:
	# Higher counts may indicate that a directory is "stable" and doesn't change
	# often. On the other hand, they also appear in search results more often,
	# hence incur a higher "penalty" when we get it wrong. So keep it simple.
	end_time = time() + timeout_secs
	paths = list(vps)
	shuffle(paths)
	for path in paths:
		if time() >= end_time:
			break
		try:
			is_dir = os.path.isdir(path)
		except OSError:
			continue
		if not is_dir:
			_remove_from_visited_paths(vps, path)

def _remove_from_visited_paths(vps, path):
	for p in list(vps):
		if p == path or p.startswith(path + os.sep):
			try:
				del vps[p]
			except KeyError:
				pass

def unexpand_user(path, expanduser_=expanduser):
	home_dir = expanduser_('~')
	if path.startswith(home_dir):
		path = '~' + path[len(home_dir):]
	return path

class SuggestLocations:

	_MATCHERS = (
		path_starts_with, basename_starts_with, contains_substring,
		contains_chars
	)

	class LocalFileSystem:
		def isdir(self, path):
			return os.path.isdir(path)
		def expanduser(self, path):
			return expanduser(path)
		def listdir(self, path):
			return os.listdir(path)
		def resolve(self, path):
			return str(Path(path).resolve())
		def samefile(self, f1, f2):
			return os.path.samefile(f1, f2)
		_core_services_ns = None
		def _get_core_services_ns(self):
			if self.__class__._core_services_ns is None:
				from objc import loadBundle
				ns = {}
				loadBundle(
					'CoreServices.framework', ns,
					bundle_identifier='com.apple.CoreServices'
				)
				self.__class__._core_services_ns = ns
			return self.__class__._core_services_ns
		def find_folders_starting_with(self, pattern, timeout_secs=0.02):
			if PLATFORM == 'Mac':
				ns = self._get_core_services_ns()
				pred = ns['NSPredicate'].predicateWithFormat_argumentArray_(
					"kMDItemContentType == 'public.folder' && "
					"kMDItemFSName BEGINSWITH[c] %@", [pattern]
				)
				query = ns['NSMetadataQuery'].alloc().init()
				query.setPredicate_(pred)
				query.setSearchScopes_(ns['NSArray'].arrayWithObject_('/'))
				query.startQuery()
				ns['NSRunLoop'].currentRunLoop().runUntilDate_(
					ns['NSDate'].dateWithTimeIntervalSinceNow_(timeout_secs)
				)
				query.stopQuery()
				for item in query.results():
					yield item.valueForAttribute_("kMDItemPath")
			elif PLATFORM == 'Windows':
				import adodbapi
				from pythoncom import com_error
				try:
					conn = adodbapi.connect(
						"Provider=Search.CollatorDSO;"
						"Extended Properties='Application=Windows';"
					)
					cursor = conn.cursor()

					# adodbapi claims to support "paramstyles", which would let us
					# pass parameters as an extra arg to .execute(...), without
					# having to worry about escaping them. Alas, adodbapi raises an
					# error when this feature is used. We thus have to escape the
					# param ourselves:
					def escape(param):
						return re.subn(r'([%_\[\]\^])', r'[\1]', param)[0]

					cursor.execute(
						"SELECT TOP 5 System.ItemPathDisplay FROM SYSTEMINDEX "
						"WHERE "
						"System.ItemType = 'Directory' AND "
						"System.ItemNameDisplay LIKE %r "
						"ORDER BY System.ItemPathDisplay"
						% (escape(pattern) + '%')
					)
					for row in iter(cursor.fetchone, None):
						value = row['System.ItemPathDisplay']
						# Seems to be None sometimes:
						if value:
							yield value
				except (adodbapi.Error, com_error):
					pass

	def __init__(self, visited_paths, file_system=None):
		if file_system is None:
			# Encapsulating filesystem-related functionality in a separate field
			# allows us to use a different implementation for testing.
			file_system = self.LocalFileSystem()
		self.visited_paths = visited_paths
		self.fs = file_system
	def __call__(self, query):
		possible_dirs = self._gather_dirs(query)
		return self._filter_matching(possible_dirs, query)
	def _gather_dirs(self, query):
		path = self._normalize_query(query)
		if isabs(path):
			if self._is_existing_dir(path):
				try:
					dir_ = self.fs.resolve(path)
				except OSError:
					dir_ = path
				return [dir_] + self._gather_subdirs(dir_)
			else:
				parent_path = os.path.dirname(path)
				if self._is_existing_dir(parent_path):
					try:
						parent = self.fs.resolve(parent_path)
					except OSError:
						pass
					else:
						return self._gather_subdirs(parent)
		result = set(self.visited_paths)
		if len(query) > 2:
			"""Compensate for directories not yet in self.visited_paths:"""
			fs_folders = islice(self.fs.find_folders_starting_with(query), 100)
			result.update(self._sorted(fs_folders)[:10])
		return self._sorted(result)
	def _normalize_query(self, query):
		result = normpath(self.fs.expanduser(query))
		if PLATFORM == 'Windows':
			# Windows completely ignores trailing spaces in directory names at
			# all times. Make our implementation reflect this:
			result = result.rstrip(' ')
			# Handle the case where the user has entered a drive such as 'E:'
			# without the trailing backslash:
			if re.match(r'^[A-Z]:$', result):
				result += '\\'
		return result
	def _sorted(self, dirs):
		return sorted(dirs, key=lambda dir_: (
			-self.visited_paths.get(dir_, 0), len(dir_), dir_.lower()
		))
	def _is_existing_dir(self, path):
		try:
			return self.fs.isdir(path)
		except OSError:
			return False
	def _filter_matching(self, dirs, query):
		use_tilde = \
			not query.startswith(os.path.dirname(self.fs.expanduser('~')))
		result = [[] for _ in self._MATCHERS]
		for dir_ in dirs:
			title = self._unexpand_user(dir_) if use_tilde else dir_
			for i, matcher in enumerate(self._MATCHERS):
				match = matcher(title.lower(), query.lower())
				if match is not None:
					result[i].append(QuicksearchItem(
						dir_, title, highlight=match
					))
					break
		return list(chain.from_iterable(result))
	def _gather_subdirs(self, dir_):
		result = []
		try:
			dir_contents = self.fs.listdir(dir_)
		except OSError:
			pass
		else:
			for name in dir_contents:
				file_path = os.path.join(dir_, name)
				try:
					if self.fs.isdir(file_path):
						result.append(file_path)
				except OSError:
					pass
		return self._sorted(result)
	def _unexpand_user(self, path):
		return unexpand_user(path, self.fs.expanduser)