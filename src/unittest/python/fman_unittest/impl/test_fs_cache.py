from fman.impl.fs_cache import Cache, CacheItem
from collections import defaultdict
from threading import Thread, Barrier, RLock
from time import sleep
from unittest import TestCase

class CacheTest(TestCase):
	def test_get_nonexistent(self):
		with self.assertRaises(KeyError):
			self.cache.get('nonexistent', 'attr')
	def test_put_get(self):
		self.cache.put('C:/test.txt', 'is_dir', False)
		self.assertIs(False, self.cache.get('C:/test.txt', 'is_dir'))
	def test_query_caches(self):
		self.cache.query('/tmp/list.txt', 'size_bytes', lambda: 13)
		self.assertEqual(13, self.cache.get('/tmp/list.txt', 'size_bytes'))
	def test_query_uses_cached_value(self):
		self.cache.put('C:/test.txt', 'is_dir', False)
		def fail():
			self.fail('Should not be called')
		self.assertIs(False, self.cache.query('C:/test.txt', 'is_dir', fail))
	def test_clear(self):
		path = '/Users/michael/a and b.txt'
		attr = 'size_bytes'
		self.cache.put(path, attr, 19)
		self.cache.clear(path)
		with self.assertRaises(KeyError):
			self.cache.get(path, attr)
	def test_clear_empty_path(self):
		path = 'C:/Users/michael/a and b.txt'
		attr = 'size_bytes'
		self.cache.put(path, attr, 19)
		self.cache.clear('')
		with self.assertRaises(KeyError):
			self.cache.get(path, attr)
	def test_query_locks(self):
		calls = []
		def compute_value():
			calls.append(1)
			sleep(.01)
			return True
		do_query = lambda: self.cache.query('', 'is_dir', compute_value)
		thread_1 = Thread(target=do_query)
		thread_2 = Thread(target=do_query)
		thread_1.start()
		thread_2.start()
		thread_1.join()
		thread_2.join()
		self.assertEqual(1, len(calls))
	def test_query_reentrant_rlock(self):
		outer_called = []
		def compute_outer():
			outer_called.append(1)
			self.cache.query('nested', 'attr', lambda: 'inner')
			return 'outer'
		result = self.cache.query('top', 'val', compute_outer)
		self.assertEqual('outer', result)
		self.assertEqual('inner', self.cache.get('nested', 'attr'))
	def test_concurrent_put_and_clear(self):
		errors = []
		barrier = Barrier(2)
		def writer():
			barrier.wait()
			for i in range(100):
				try:
					self.cache.put('path/%d' % i, 'attr', i)
				except Exception as e:
					errors.append(e)
		def clearer():
			barrier.wait()
			for _ in range(100):
				try:
					self.cache.clear('')
				except Exception as e:
					errors.append(e)
		t1 = Thread(target=writer)
		t2 = Thread(target=clearer)
		t1.start()
		t2.start()
		t1.join()
		t2.join()
		self.assertEqual([], errors)
	def test_concurrent_query_different_paths(self):
		results = {}
		barrier = Barrier(2)
		def query_path(path, value):
			barrier.wait()
			results[path] = self.cache.query(path, 'attr', lambda: value)
		t1 = Thread(target=query_path, args=('a', 1))
		t2 = Thread(target=query_path, args=('b', 2))
		t1.start()
		t2.start()
		t1.join()
		t2.join()
		self.assertEqual(1, results['a'])
		self.assertEqual(2, results['b'])
	def test_clear_attr(self):
		self.cache.put('path', 'keep', 'yes')
		self.cache.put('path', 'remove', 'no')
		self.cache.clear_attr('path', 'remove')
		self.assertEqual('yes', self.cache.get('path', 'keep'))
		with self.assertRaises(KeyError):
			self.cache.get('path', 'remove')
	def test_clear_attr_nonexistent_path(self):
		self.cache.clear_attr('nonexistent', 'attr')
	def test_clear_attr_nonexistent_attr(self):
		self.cache.put('path', 'exists', 1)
		self.cache.clear_attr('path', 'nope')
		self.assertEqual(1, self.cache.get('path', 'exists'))
	def test_clear_attr_allows_recompute(self):
		self.cache.query('p', 'a', lambda: 'first')
		self.assertEqual('first', self.cache.get('p', 'a'))
		self.cache.clear_attr('p', 'a')
		self.cache.query('p', 'a', lambda: 'second')
		self.assertEqual('second', self.cache.get('p', 'a'))
	def test_clear_nonexistent_path(self):
		self.cache.clear('nonexistent/path')
	def test_nested_path_put_get(self):
		self.cache.put('a/b/c', 'val', 42)
		self.assertEqual(42, self.cache.get('a/b/c', 'val'))
	def test_clear_parent_clears_children(self):
		self.cache.put('a/b', 'val', 1)
		self.cache.clear('a')
		with self.assertRaises(KeyError):
			self.cache.get('a/b', 'val')
	def setUp(self):
		super().setUp()
		self.cache = Cache()

class CacheItemTest(TestCase):
	def test_attr_locks_are_reentrant(self):
		item = CacheItem()
		item.query('test', lambda: 'val')
		lock = item._attr_locks['test']
		lock.acquire()
		acquired = lock.acquire(blocking=False)
		self.assertTrue(acquired)
		lock.release()
		lock.release()
	def test_update_child_creates_path(self):
		item = CacheItem()
		child = item.update_child('a/b/c')
		child.put('key', 'val')
		self.assertEqual('val', item.get_child('a/b/c').get('key'))
	def test_delete_child_nested(self):
		item = CacheItem()
		item.update_child('a/b').put('k', 'v')
		item.delete_child('a/b')
		with self.assertRaises(KeyError):
			item.get_child('a/b')
	def test_get_child_nonexistent(self):
		item = CacheItem()
		with self.assertRaises(KeyError):
			item.get_child('nope')