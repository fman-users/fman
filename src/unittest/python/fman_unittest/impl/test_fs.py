from fman.fs import FileSystem
from threading import Thread, Barrier, Lock
from unittest import TestCase

class NotifyFileChangedTest(TestCase):
	def test_callback_called(self):
		fs = FileSystem()
		results = []
		fs._file_changed_callbacks['test'] = [lambda url: results.append(url)]
		fs.notify_file_changed('test')
		self.assertEqual([fs.scheme + 'test'], results)
	def test_no_callbacks_for_path(self):
		fs = FileSystem()
		fs.notify_file_changed('nonexistent')
	def test_callback_removal_during_notify(self):
		fs = FileSystem()
		results = []
		callbacks = []
		def remove_self(url):
			with fs._file_changed_callbacks_lock:
				callbacks.remove(remove_self)
			results.append('removed')
		def second(url):
			results.append('second')
		callbacks.extend([remove_self, second])
		fs._file_changed_callbacks['test'] = callbacks
		fs.notify_file_changed('test')
		self.assertEqual(['removed', 'second'], results)
	def test_thread_safety(self):
		fs = FileSystem()
		call_count = 0
		count_lock = Lock()
		def counter(url):
			nonlocal call_count
			with count_lock:
				call_count += 1
		fs._file_changed_callbacks['test'] = [counter]
		barrier = Barrier(10)
		def notify():
			barrier.wait()
			fs.notify_file_changed('test')
		threads = [Thread(target=notify) for _ in range(10)]
		for t in threads:
			t.start()
		for t in threads:
			t.join()
		self.assertEqual(10, call_count)
