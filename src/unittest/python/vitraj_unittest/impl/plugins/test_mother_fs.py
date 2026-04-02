from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from vitraj.fs import FileSystem, cached
from vitraj.impl.plugins.mother_fs import MotherFileSystem, CachedIterator
from vitraj_unittest.impl.model import StubFileSystem
from threading import Thread, Lock, Event
from time import sleep
from unittest import TestCase

class MotherFileSystemTest(TestCase):
	def test_exists(self):
		fs = StubFileSystem({
			'a': {}
		})
		mother_fs = self._create_mother_fs(fs)
		self.assertTrue(mother_fs.exists('stub://a'))
		self.assertFalse(mother_fs.exists('stub://b'))
		mother_fs.touch('stub://b')
		self.assertTrue(mother_fs.exists('stub://b'))
	def test_delete_removes_from_pardir_cache(self):
		fs = StubFileSystem({
			'a': {
				'is_dir': True, 'files': ['b']
			},
			'a/b': {}
		})
		mother_fs = self._create_mother_fs(fs)
		self.assertEqual(['b'], list(mother_fs.iterdir('stub://a')))
		mother_fs.delete('stub://a/b')
		self.assertEqual([], list(mother_fs.iterdir('stub://a')))
		self.assertFalse(mother_fs.exists('stub://a/b'))
	def test_delete_removes_children(self):
		fs = StubFileSystem({
			'': {'is_dir': True, 'files': ['a']},
			'a': {
				'is_dir': True, 'files': ['b']
			},
			'a/b': {}
		})
		mother_fs = self._create_mother_fs(fs)
		# Put in cache:
		mother_fs.is_dir('stub://a/b')
		mother_fs.delete('stub://a')
		self.assertFalse(mother_fs.exists('stub://a/b'))
	def test_move_updates_pardir(self):
		fs = StubFileSystem({
			'a': { 'is_dir': True , 'files': ['b']},
			'a/b': {},
			'c': { 'is_dir': True }
		})
		mother_fs = self._create_mother_fs(fs)
		self.assertEqual(['b'], list(mother_fs.iterdir('stub://a')))
		self.assertEqual([], list(mother_fs.iterdir('stub://c')))
		mother_fs.move('stub://a/b', 'stub://c/b')
		self.assertEqual([], list(mother_fs.iterdir('stub://a')))
		self.assertEqual(['b'], list(mother_fs.iterdir('stub://c')))
	def test_touch(self):
		fs = StubFileSystem({
			'a': { 'is_dir': True }
		})
		mother_fs = self._create_mother_fs(fs)
		self.assertEqual([], list(mother_fs.iterdir('stub://a')))
		mother_fs.touch('stub://a/b')
		self.assertEqual(['b'], list(mother_fs.iterdir('stub://a')))
	def test_mkdir(self):
		fs = StubFileSystem({
			'a': { 'is_dir': True }
		})
		mother_fs = self._create_mother_fs(fs)
		self.assertEqual([], list(mother_fs.iterdir('stub://a')))
		mother_fs.mkdir('stub://a/b')
		self.assertEqual(['b'], list(mother_fs.iterdir('stub://a')))
	def test_no_concurrent_is_dir_queries(self):
		fs = FileSystemCountingIsdirCalls()
		mother_fs = self._create_mother_fs(fs)
		def _new_thread():
			return Thread(target=mother_fs.is_dir, args=('fscic://test',))
		t1, t2 = _new_thread(), _new_thread()
		t1.start()
		t2.start()
		t1.join()
		t2.join()
		self.assertEqual(1, fs.num_is_dir_calls)
	def test_permission_error(self):
		fs = FileSystemRaisingError()
		mother_fs = self._create_mother_fs(fs)
		# Put 'foo' in cache:
		mother_fs.is_dir('fsre://foo')
		with self.assertRaises(PermissionError):
			mother_fs.iterdir('fsre://foo')
	def test_is_dir_file(self):
		fs = StubFileSystem({
			'a': {}
		})
		mother_fs = self._create_mother_fs(fs)
		self.assertFalse(mother_fs.is_dir('stub://a'))
	def test_is_dir_nonexistent(self):
		fs = StubFileSystem({})
		mother_fs = self._create_mother_fs(fs)
		url = 'stub://non-existent'
		with self.assertRaises(FileNotFoundError):
			mother_fs.is_dir(url)
		self.assertFalse(mother_fs.exists(url))
		mother_fs.mkdir(url)
		self.assertTrue(mother_fs.is_dir(url))
	def test_remove_child(self):
		fs = StubFileSystem({
			'a': {'is_dir': True}
		})
		mother_fs = self._create_mother_fs(fs)
		self.assertTrue(mother_fs.is_dir('stub://a'))
		mother_fs.remove_child(fs.scheme)
		mother_fs.add_child(fs.scheme, StubFileSystem({}))
		with self.assertRaises(FileNotFoundError):
			mother_fs.is_dir('stub://a')
	def test_mkdir_triggers_file_added(self):
		mother_fs = self._create_mother_fs(StubFileSystem({}))
		url = 'stub://test'
		with self.assertRaises(FileNotFoundError):
			# This should not put `url` in cache:
			mother_fs.is_dir(url)
		files_added = []
		def on_file_added(url_):
			files_added.append(url_)
		mother_fs.file_added.add_callback(on_file_added)
		mother_fs.mkdir(url)
		self.assertEqual([url], files_added)
	def test_relative_paths(self):
		mother_fs = self._create_mother_fs(StubFileSystem({
			'a': {'is_dir': True},
			'a/b': {'is_dir': True}
		}))
		self.assertTrue(mother_fs.is_dir('stub://a/b/..'))
		mother_fs.move('stub://a', 'stub://b')
		with self.assertRaises(FileNotFoundError):
			mother_fs.is_dir('stub://a/b/..')
		mother_fs.touch('stub://a/../c')
		self.assertTrue(mother_fs.exists('stub://c'))
		mother_fs.mkdir('stub://a/../dir')
		self.assertTrue(mother_fs.is_dir('stub://a/../dir'))
		self.assertTrue(mother_fs.is_dir('stub://dir'))
		mother_fs.move('stub://a/b', 'stub://a/../b')
		self.assertTrue(mother_fs.exists('stub://b'))
	def _create_mother_fs(self, fs):
		result = MotherFileSystem(None)
		result.add_child(fs.scheme, fs)
		return result

class FileSystemCountingIsdirCalls(FileSystem):

	scheme = 'fscic://'

	def __init__(self):
		super().__init__()
		self.num_is_dir_calls = 0
		self._num_is_dir_calls_lock = Lock()
	@cached # prevents execution by multiple threads at the same time
	def is_dir(self, _):
		with self._num_is_dir_calls_lock:
			self.num_is_dir_calls += 1
		# Give other threads a chance to run:
		sleep(.1)
		return True

class FileSystemRaisingError(FileSystem):

	scheme = 'fsre://'

	def is_dir(self, path):
		return True
	def iterdir(self, path):
		raise PermissionError(path)

class CachedIteratorTest(TestCase):
	def test_simple(self):
		# For the sake of illustration, see what happens normally:
		iterable = self._generate(1, 2, 3)
		self.assertEqual([1, 2, 3], list(iterable))
		self.assertEqual([], list(iterable))
		# Now compare the above to what happens with CachedIterable:
		iterable = CachedIterator(self._generate(1, 2, 3))
		self.assertEqual([1, 2, 3], list(iterable))
		self.assertEqual([1, 2, 3], list(iterable))
	def test_remove_after_cached(self):
		iterable = CachedIterator(self._generate(1, 2, 3))
		iterator = iter(iterable)
		self.assertEqual(1, next(iterator))
		iterable.remove(1)
		self.assertEqual(2, next(iterator))
		self.assertEqual(3, next(iterator))
		self.assertEqual([2, 3], list(iterable))
	def test_remove_before_cached(self):
		iterable = CachedIterator(self._generate(1, 2, 3))
		iterator = iter(iterable)
		self.assertEqual(1, next(iterator))
		iterable.remove(2)
		self.assertEqual(3, next(iterator))
		with self.assertRaises(StopIteration):
			next(iterator)
		self.assertEqual([1, 3], list(iterable))
	def test_add_before_exhausted(self):
		iterable = CachedIterator(self._generate(1, 2))
		iterator = iter(iterable)
		self.assertEqual(1, next(iterator))
		iterable.append(3)
		# We don't care if the order is [2, 3] or [3, 2] - but there should only
		# be one each:
		self.assertEqual(Counter([2, 3]), Counter(iterator))
		# We don't care about the exact order of [1, 2, 3] but each elt. should
		# only be returned once:
		self.assertEqual(Counter([1, 2, 3]), Counter(iterable))
		self.assertEqual(Counter([1, 2, 3]), Counter(iterable))
	def test_add_after_exhausted(self):
		iterable = CachedIterator(self._generate(1, 2))
		self.assertEqual([1, 2], list(iterable))
		iterable.append(3)
		self.assertEqual([1, 2, 3], list(iterable))
		self.assertEqual([1, 2, 3], list(iterable))
	def test_add_duplicate(self):
		iterable = CachedIterator(self._generate(1, 2))
		iterable.append(2)
		# We don't care about the exact order of [1, 2] but each elt. should
		# only be returned once:
		self.assertEqual(Counter([1, 2]), Counter(iterable))
		self.assertEqual(Counter([1, 2]), Counter(iterable))
	def test_add_duplicate_after_exhausted(self):
		iterable = CachedIterator(self._generate(1, 2))
		self.assertEqual([1, 2], list(iterable))
		iterable.append(2)
		self.assertEqual([1, 2], list(iterable))
	def test_concurrent_read(self):
		items = [1, 2]
		iterable = CachedIterator(self._generate_slowly(*items))
		thread_started = Event()
		executor = ThreadPoolExecutor()
		try:
			future = \
				executor.submit(self._consume, thread_started, iterable)
			try:
				thread_started.wait()
				self.assertEqual(items, list(iterable))
			finally:
				# Wait for the thread to complete and re-raise any exceptions:
				self.assertEqual(items, future.result())
		finally:
			executor.shutdown()
	def test_add_remove(self):
		"""
		Suppose each next(...) call below is in one thread and .remove(...) and
		.append(...) are in another. This test ensures that the next(...) thread
		never receives duplicate values.
		"""
		iterable = CachedIterator(self._generate(1))
		iterator = iter(iterable)
		self.assertEqual(1, next(iterator))
		iterable.remove(1)
		iterable.append(1)
		with self.assertRaises(StopIteration, msg='Should not return 1 again.'):
			next(iterator)
	def test_add_remove_out_of_order(self):
		iterable = CachedIterator(self._generate(1, 2))
		iterator = iter(iterable)
		iterable.remove(2)
		iterable.remove(1)
		with self.assertRaises(StopIteration):
			next(iterator)
	def _generate(self, *args):
		yield from args
	def _generate_slowly(self, *args):
		for arg in args:
			sleep(.1)
			yield arg
	def _consume(self, started, iterable):
		started.set()
		return list(iterable)