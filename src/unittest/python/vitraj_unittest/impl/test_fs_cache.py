from vitraj.impl.fs_cache import Cache
from threading import Thread
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
	def setUp(self):
		super().setUp()
		self.cache = Cache()