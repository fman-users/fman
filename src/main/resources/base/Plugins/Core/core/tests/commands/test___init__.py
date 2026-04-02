from core.commands import History, Move, _from_human_readable, \
	get_dest_suggestion, _find_extension_start, _get_shortcuts_for_command
from core.tests import StubUI
from core.util import filenotfounderror
from vitraj import OK, YES, NO, PLATFORM
from vitraj.url import join, as_human_readable, as_url, dirname
from unittest import TestCase

import os
import os.path

class FindExtensionStartTest(TestCase):
	def test_no_extension(self):
		self.assertIsNone(_find_extension_start('File'))
	def test_normal_extension(self):
		self.assertEqual(4, _find_extension_start('test.zip'))
	def test_tar_xz(self):
		self.assertEqual(7, _find_extension_start('archive.tar.xz'))
	def test_tar_gz(self):
		self.assertEqual(7, _find_extension_start('archive.tar.gz'))

class ConfirmTreeOperationTest(TestCase):

	class FileSystem:
		def __init__(self, files, case_sensitive=PLATFORM == 'Linux'):
			self._files = files
			self._case_sensitive = case_sensitive

		def exists(self, url):
			try:
				self._get(url)
			except KeyError:
				return False
			return True

		def is_dir(self, url):
			try:
				file_info = self._get(url)
			except KeyError:
				raise filenotfounderror(url) from None
			return file_info['is_dir']

		def samefile(self, url1, url2):
			if not self._case_sensitive:
				url1 = url1.lower()
				url2 = url2.lower()
			return url1 == url2

		def _get(self, url):
			dict_ = self._files
			if not self._case_sensitive:
				dict_ = {k.lower(): v for k, v in self._files.items()}
				url = url.lower()
			return dict_[url]

	def test_no_files(self):
		self._expect_alert(('No file is selected!',), answer=OK)
		self._check([], None)
	def test_one_file(self):
		dest_path = as_human_readable(join(self._dest, 'a.txt'))
		sel_start = dest_path.rindex(os.sep) + 1
		self._expect_prompt(
			('Move "a.txt" to', dest_path, sel_start, sel_start + 1),
			(dest_path, True)
		)
		self._check([self._a_txt], (self._dest, 'a.txt'))
	def test_one_dir(self):
		dest_path = as_human_readable(self._dest)
		self._expect_prompt(
			('Move "a" to', dest_path, 0, None), (dest_path, True)
		)
		self._check([self._a], (self._dest, None))
	def test_rename_dir_to_uppercase(self):
		dest_path = as_human_readable(self._src)
		self._expect_prompt(
			('Move "a" to', dest_path, 0, None), ('A', True)
		)
		self._check([self._a], (self._src, 'A'), dest_dir=self._src)
	def test_two_files(self):
		dest_path = as_human_readable(self._dest)
		self._expect_prompt(
			('Move 2 files to', dest_path, 0, None), (dest_path, True)
		)
		self._check([self._a_txt, self._b_txt], (self._dest, None))
	def test_into_subfolder(self):
		dest_path = as_human_readable(join(self._dest, 'a.txt'))
		sel_start = dest_path.rindex(os.sep) + 1
		self._expect_prompt(
			('Move "a.txt" to', dest_path, sel_start, sel_start + 1),
			('a', True)
		)
		self._check([self._a_txt], (self._a, None))
	def test_overwrite_single_file(self):
		dest_url = join(self._dest, 'a.txt')
		self._fs._files[dest_url] = {'is_dir': False}
		dest_path = as_human_readable(dest_url)
		sel_start = dest_path.rindex(os.sep) + 1
		self._expect_prompt(
			('Move "a.txt" to', dest_path, sel_start, sel_start + 1),
			(dest_path, True)
		)
		self._check([self._a_txt], (self._dest, 'a.txt'))
	def test_multiple_files_over_one(self):
		dest_url = join(self._dest, 'a.txt')
		self._fs._files[dest_url] = {'is_dir': False}
		dest_path = as_human_readable(dest_url)
		self._expect_prompt(
			('Move 2 files to', as_human_readable(self._dest), 0, None),
			(dest_path, True)
		)
		self._expect_alert(
			('You cannot move multiple files to a single file!',), answer=OK
		)
		self._check([self._a_txt, self._b_txt], None)
	def test_multiple_into_self(self):
		dest_path = as_human_readable(self._a)
		self._expect_prompt(
			('Move 2 files to', dest_path, 0, None), (dest_path, True)
		)
		self._expect_alert(('You cannot move a file to itself!',), answer=OK)
		self._check([self._a_txt, self._a], None, dest_dir=self._a)
	def test_renamed_destination(self):
		dest_path = as_human_readable(join(self._dest, 'a.txt'))
		sel_start = dest_path.rindex(os.sep) + 1
		self._expect_prompt(
			('Move "a.txt" to', dest_path, sel_start, sel_start + 1),
			(as_human_readable(join(self._dest, 'z.txt')), True)
		)
		self._check([self._a_txt], (self._dest, 'z.txt'))
	def test_multiple_files_nonexistent_dest(self):
		dest_url = join(self._dest, 'dir')
		dest_path = as_human_readable(dest_url)
		self._expect_prompt(
			('Move 2 files to', as_human_readable(self._dest), 0, None),
			(dest_path, True)
		)
		self._expect_alert(
			('%s does not exist. Do you want to create it as a directory and '
			 'move the files there?' % dest_path, YES | NO, YES),
			answer=YES
		)
		self._check([self._a_txt, self._b_txt], (dest_url, None))
	def test_file_system_root(self):
		dest_path = as_human_readable(join(self._root, 'a.txt'))
		sel_start = dest_path.rindex(os.sep) + 1
		self._expect_prompt(
			('Move "a.txt" to', dest_path, sel_start, sel_start + 1),
			(dest_path, True)
		)
		self._check([self._a_txt], (self._root, 'a.txt'), dest_dir=self._root)
	def test_different_scheme(self):
		dest_path = as_human_readable(join(self._dest, 'a.txt'))
		sel_start = dest_path.rindex(os.sep) + 1
		self._expect_prompt(
			('Move "a.txt" to', dest_path, sel_start, sel_start + 1),
			(dest_path, True)
		)
		src_url = 'zip:///dest.zip/a.txt'
		src_dir = dirname(src_url)
		self._check([src_url], (self._dest, 'a.txt'), src_dir=src_dir)
	def _expect_alert(self, args, answer):
		self._ui.expect_alert(args, answer)
	def _expect_prompt(self, args, answer):
		self._ui.expect_prompt(args, answer)
	def _check(self, files, expected_result, src_dir=None, dest_dir=None):
		if src_dir is None:
			src_dir = self._src
		if dest_dir is None:
			dest_dir = self._dest
		actual_result = Move._confirm_tree_operation(
			files, dest_dir, src_dir, self._ui, self._fs
		)
		self._ui.verify_expected_dialogs_were_shown()
		self.assertEqual(expected_result, actual_result)
	def setUp(self):
		super().setUp()
		self._ui = StubUI(self)
		self._root = as_url('C:\\' if PLATFORM == 'Windows' else '/')
		self._src = join(self._root, 'src')
		self._dest = join(self._root, 'dest')
		self._a = join(self._root, 'src/a')
		self._a_txt = join(self._root, 'src/a.txt')
		self._b_txt = join(self._root, 'src/b.txt')
		self._fs = self.FileSystem({
			self._src: {'is_dir': True},
			self._dest: {'is_dir': True},
			self._a: {'is_dir': True},
			self._a_txt: {'is_dir': False},
			self._b_txt: {'is_dir': False},
		})

class GetDestSuggestionTest(TestCase):
	def test_file(self):
		file_path = os.path.join(self._root, 'file.txt')
		selection_start = file_path.rindex(os.sep) + 1
		selection_end = selection_start + len('file')
		self.assertEqual(
			(file_path, selection_start, selection_end),
			get_dest_suggestion(as_url(file_path))
		)
	def test_dir(self):
		dir_path = os.path.join(self._root, 'dir')
		selection_start = dir_path.rindex(os.sep) + 1
		selection_end = None
		self.assertEqual(
			(dir_path, selection_start, selection_end),
			get_dest_suggestion(as_url(dir_path))
		)
	def setUp(self):
		super().setUp()
		self._root = 'C:\\' if PLATFORM == 'Windows' else '/'

class FromHumanReadableTest(TestCase):
	def test_no_src_dir(self):
		path = __file__
		dir_url = as_url(os.path.dirname(path))
		self.assertEqual(
			as_url(path),
			_from_human_readable(path, dir_url, None)
		)

class GetShortcutsForCommandTest(TestCase):
	def test_no_shortcut(self):
		self._check([{'keys': ['Enter'], 'command': 'open'}], 'copy', [])
	def test_simple(self):
		self._check([{'keys': ['Enter'], 'command': 'open'}], 'open', ['Enter'])
	def test_two_shortcuts(self):
		self._check(
			[{'keys': ['Enter'], 'command': 'open'},
			 {'keys': ['Down'], 'command': 'open'}],
			'open', ['Enter', 'Down']
		)
	def test_shortcut_only_displayed_for_one_command(self):
		bindings = [
			{'keys': ['Enter'], 'command': 'open'},
			{'keys': ['Enter'], 'command': 'alternative'}
		]
		self._check(bindings, 'open', ['Enter'])
		self._check(bindings, 'alternative', [])
	def _check(self, key_bindings, command, expected_shortcuts):
		actual = list(_get_shortcuts_for_command(key_bindings, command))
		self.assertEqual(expected_shortcuts, actual)

class HistoryTest(TestCase):
	def test_empty_back(self):
		with self.assertRaises(ValueError):
			self._go_back()
	def test_empty_forward(self):
		with self.assertRaises(ValueError):
			self._go_forward()
	def test_single_back(self):
		self._go_to('single item')
		with self.assertRaises(ValueError):
			self._go_back()
	def test_single_forward(self):
		self._go_to('single item')
		with self.assertRaises(ValueError):
			self._go_forward()
	def test_go_back_forward(self):
		self._go_to('a', 'b', 'c')
		self.assertEqual('b', self._go_back())
		self.assertEqual('a', self._go_back())
		self.assertEqual('b', self._go_forward())
		self.assertEqual('c', self._go_forward())
	def test_go_to_after_back(self):
		self._go_to('a', 'b')
		self.assertEqual('a', self._go_back())
		self._go_to('c')
		self.assertEqual(['a', 'c'], self._history._paths)
	def setUp(self):
		super().setUp()
		self._history = History()
	def _go_back(self):
		path = self._history.go_back()
		self._history.path_changed(path)
		return path
	def _go_forward(self):
		path = self._history.go_forward()
		self._history.path_changed(path)
		return path
	def _go_to(self, *paths):
		for path in paths:
			self._history.path_changed(path)