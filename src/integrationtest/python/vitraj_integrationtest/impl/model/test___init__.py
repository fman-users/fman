from contextlib import contextmanager
from fbs_runtime.platform import is_linux
from vitraj.impl.model import SortedFileSystemModel
from vitraj.impl.plugins.builtin import NullFileSystem, NullColumn
from vitraj.impl.plugins.mother_fs import MotherFileSystem
from vitraj.impl.util import filenotfounderror
from vitraj.impl.util.qt import connect_once, DisplayRole, DecorationRole
from vitraj.impl.util.qt.thread import run_in_main_thread
from vitraj.url import splitscheme
from vitraj_unittest.impl.model import StubFileSystem
from PyQt5.QtCore import Qt
from threading import Event
from time import time, sleep

import sys

class SortedFileSystemModelAT: # Instantiated in vitraj_integrationtest.test_qt

	_NUM_FILES = 100
	_NUM_VISIBLE_ROWS = 10

	def test_location_after_init(self):
		self.assertEqual('null://', self._model.get_location())
		self.assertEqual((self._null_column,), self._model.get_columns())
	def test_set_location(self):
		inited = Event()
		self._model.set_location('stub://', callback=inited.set)
		self.assertEqual('stub://', self._model.get_location())
		self._wait_for(inited)
		self._expect_column_headers(['Name', 'Size'])
		self.assertEqual(
			(self._name_column, self._size_column), self._model.get_columns()
		)
		self.assertEqual(
			['dir'] + [str(i) for i in range(self._NUM_FILES)],
			self._get_first_column(),
			'Should load at least the first column'
		)
		self._load_visible_rows()
		rows = self._get_data()[:self._NUM_VISIBLE_ROWS]
		icons = self._get_data(DecorationRole)[:self._NUM_VISIBLE_ROWS]
		self.assertEqual(('dir', ''), rows[0])
		self.assertEqual((self._folder_icon, None), icons[0])
		self.assertEqual(
			[
				(str(i), '%d B' % self._files[str(i)]['size'])
				for i in range(self._NUM_VISIBLE_ROWS - 1)
			],
			rows[1:]
		)
		self.assertEqual(
			[(self._file_icon, None)] * (self._NUM_VISIBLE_ROWS - 1), icons[1:]
		)
	def _load_visible_rows(self):
		loaded = Event()
		load_rows = run_in_main_thread(self._model.load_rows)
		load_rows(range(self._NUM_VISIBLE_ROWS), callback=loaded.set)
		self._wait_for(loaded)
	def test_remove_current_dir(self):
		self._set_location('stub://dir')
		with self._wait_for_signal(self._model.location_loaded):
			self._fs.delete('stub://dir')
		self.assertEqual('stub://', self._model.get_location())
	def test_remove_root(self):
		self._set_location('stub://dir')
		with self._wait_for_signal(self._model.location_loaded):
			self._fs.remove_child('stub://')
		self.assertEqual('null://', self._model.get_location())
	def test_reloads(self):
		self.test_set_location()
		self._set_location('stub://dir')
		self._files['0']['size'] = 87
		self._set_location('stub://')
		self._load_visible_rows()
		self._wait_until(
			lambda: self._get_data()[:2] == [('dir', ''), ('0', '87 B')],
			'Model failed to reload'
		)
	def test_sort(self):
		self.test_set_location()
		with self._wait_for_signal(self._model.sort_order_changed):
			run_in_main_thread(self._model.sort)(1)
		expected_files_sort_order = ['dir'] + sorted(
			(str(i) for i in range(self._NUM_FILES)),
			key=lambda fname: self._files[fname]['size']
		)
		self.assertEqual(expected_files_sort_order, self._get_first_column())
		self._load_visible_rows()
		self.assertEqual(
			[
				(fname, '%s B' % self._files[fname]['size'])
				for fname in expected_files_sort_order[1:self._NUM_VISIBLE_ROWS]
			],
			self._get_data()[1:self._NUM_VISIBLE_ROWS]
		)
	def test_file_added(self):
		self.test_set_location()
		self._files['new'] = {
			'is_dir': False,
			'size': 2,
			'icon': self._file_icon
		}
		self._files['']['files'].append('new')
		self._fs.file_added.trigger('stub://new')
		self.assertTrue(
			'new' in [r[0] for r in self._get_data()],
			'Should have processed new file synchronously to support use case:'
			' 1. Create file.txt'
			' 2. place cursor at file.txt. '
			'Without synchronous processing, step 2. would fail.'
		)
	def test_file_removed(self):
		self.test_set_location()
		self._stubfs.delete('0')
		self._fs.file_removed.trigger('stub://0')
		self._wait_until(
			lambda: '0' not in [r[0] for r in self._get_data()],
			'Did not pick up external removal of file'
		)
	def test_location_removed(self):
		self._set_location('stub://dir')
		self._stubfs.delete('dir')
		self._model.reload()
		self._wait_until(
			lambda: self._model.get_location() == 'stub://',
			'Did not pick up external removal of location'
		)
	def test_root_directory_changed(self):
		self.test_set_location()
		# "Delete" all files:
		self._files.clear()
		self._files.update({
			'': {'is_dir': True, 'files': ['dir'], 'icon': self._folder_icon},
			'dir': {'is_dir': True, 'files': [], 'icon': self._folder_icon}
		})
		self._stubfs.notify_file_changed('')
		self._wait_until(
			lambda: self._get_data() == [('dir', '')],
			'Did not pick up external update of root directory'
		)
	def test_file_renamed(self):
		self.test_set_location()
		self._stubfs.move('stub://0', 'stub://a')
		def rename_noticed():
			first_column = self._get_first_column()
			return 'a' in first_column and '0' not in first_column
		self._wait_until(rename_noticed, 'Did not pick up renaming of file')
	def test_file_moved_in(self):
		self.test_set_location()
		self._stubfs.move('stub://dir/subdir', 'stub://subdir')
		self._wait_until(
			lambda: 'subdir' in self._get_first_column(),
			'Did not pick up move of directory'
		)
	def test_file_moved_out(self):
		self.test_set_location()
		self._stubfs.move('stub://0', 'stub://dir/0')
		self._wait_until(
			lambda: not '0' in self._get_first_column(),
			'Did not pick up move of file into subdirectory'
		)
	def test_rename_file_different_case(self):
		self.test_set_location()
		self._stubfs.move('stub://dir', 'stub://Dir')
		def rename_noticed():
			first_column = self._get_first_column()
			return 'Dir' in first_column and 'dir' not in first_column
		self._wait_until(rename_noticed, 'Did not pick up renaming of file')
	def _set_location(self, location):
		loaded = Event()
		self._model.set_location(location, callback=loaded.set)
		self._wait_for(loaded)
	def _get_data(self, role=DisplayRole):
		result = []
		for row in range(self._model.rowCount()):
			result.append(tuple(
				self._model.data(self._index(row, col), role)
				for col in range(self._model.columnCount())
			))
		return result
	def _get_first_column(self):
		return [row[0] for row in self._get_data()]
	def _index(self, row, column=0):
		return self._model.index(row, column)
	def _expect_column_headers(self, expected):
		actual = [
			self._model.headerData(column, Qt.Horizontal)
			for column in range(self._model.columnCount())
		]
		self.assertEqual(expected, actual)
	def setUp(self):
		super().setUp()
		# N.B.: Normally we should have QIcon instances here. But they don't
		# seem to work well with ==. So use strings instead:
		folder_icon = '<folder icon>'
		file_icon = '<file icon>'
		self._files = {
			'': {'is_dir': True, 'files': ['dir'], 'icon': folder_icon},
			'dir': {'is_dir': True, 'files': ['subdir'], 'icon': folder_icon},
			'dir/subdir': {'is_dir': True, 'icon': folder_icon}
		}
		for i in range(self._NUM_FILES):
			fname = str(i)
			# Make size ordering different from ordering by name:
			size = i + (0 if i % 2 else self._NUM_FILES)
			self._files[fname] = {
				'is_dir': False, 'size': size, 'icon': file_icon
			}
			self._files['']['files'].append(fname)
		self._folder_icon = folder_icon
		self._file_icon = file_icon
		files = self._files if is_linux() else CaseInsensitiveDict(self._files)
		self._fs = MotherFileSystem(StubIconProvider(files))
		self._fs.add_child('null://', NullFileSystem())
		self._null_column = NullColumn()
		self._register_column(self._null_column)
		self._stubfs = StubFileSystem(
			files, default_columns=('core.Name', 'core.Size')
		)
		self._fs.add_child('stub://', self._stubfs)
		# Import late to avoid ImportError. The reason it occurs is that fbs's
		# `test` command adds vitraj_integrationtest to sys.path before Core.
		# That's fair; It's actually unclean for this test to depend on Core.
		# But it is also very useful as a kind of end-to-end test. So we do it.
		from core import Name, Size
		self._name_column = Name(self._fs)
		self._register_column(self._name_column)
		self._size_column = Size(self._fs)
		self._register_column(self._size_column)
		self._model = self.run_in_app(
			SortedFileSystemModel, None, self._fs, 'null://'
		)
		self._timeout = None if _is_debugger_attached() else .2
	def tearDown(self):
		self._model.sourceModel().shutdown()
		super().tearDown()
	def _register_column(self, instance):
		self._fs.register_column(instance.get_qualified_name(), instance)
	@contextmanager
	def _wait_for_signal(self, signal):
		occurred = Event()
		run_in_main_thread(connect_once)(signal, lambda *_: occurred.set())
		yield
		self._wait_for(occurred)
	def _wait_for(self, event):
		if not event.wait(self._timeout):
			self.fail('Event was not set after timeout')
	def _wait_until(self, condition, message):
		end_time = time() + (self._timeout or sys.float_info.max)
		while time() < end_time:
			if condition():
				break
			if self._get_data()[:2] == [('dir', ''), ('0', '87 B')]:
				break
			sleep(.1)
		else:
			self.fail(message)

def _is_debugger_attached():
	return bool(sys.gettrace())

class StubIconProvider:
	def __init__(self, files):
		self._files = files
	def get_icon(self, url):
		path = splitscheme(url)[1]
		try:
			return self._files[path].get('icon', None)
		except KeyError:
			raise filenotfounderror(url)

class CaseInsensitiveDict:
	def __init__(self, items):
		self._items = items
	def __getitem__(self, key):
		for k, v in self._items.items():
			if k.lower() == key.lower():
				return v
		raise KeyError(key)
	def	__setitem__(self, key, value):
		for k, v in self._items.items():
			if k.lower() == key.lower():
				self._items[k] = value
				return
		self._items[key] = value
	def __contains__(self, item):
		try:
			self[item]
		except KeyError:
			return False
		return True
	def pop(self, key):
		for k, v in self._items.items():
			if k.lower() == key.lower():
				return self._items.pop(key)
		raise KeyError(key)
	def items(self):
		return self._items.items()
	def clear(self):
		self._items.clear()
	def update(self, other):
		for k, v in other.items():
			self[k] = v