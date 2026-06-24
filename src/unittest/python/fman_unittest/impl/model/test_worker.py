from fman.impl.model.worker import Worker, WorkItem
from threading import Event
from time import sleep
from unittest import TestCase

class WorkerTest(TestCase):
	def test_priority_ordering(self):
		results = []
		started = Event()
		gate = Event()
		done = Event()
		def block():
			started.set()
			gate.wait()
		def record(val):
			results.append(val)
			if len(results) == 3:
				done.set()
		worker = Worker()
		worker.start()
		worker.submit(1, block)
		started.wait()
		worker.submit(3, record, 'low')
		worker.submit(1, record, 'high')
		worker.submit(2, record, 'mid')
		gate.set()
		done.wait(timeout=2)
		worker.shutdown()
		self.assertEqual(['high', 'mid', 'low'], results)
	def test_shutdown_completes(self):
		worker = Worker()
		worker.start()
		worker.shutdown()
		self.assertFalse(worker._thread.is_alive())
	def test_submit_after_shutdown_ignored(self):
		results = []
		worker = Worker()
		worker.start()
		worker.shutdown()
		worker.submit(1, lambda: results.append(1))
		self.assertEqual([], results)
	def test_shutdown_before_start(self):
		worker = Worker()
		worker.shutdown()
	def test_exception_does_not_stop_worker(self):
		results = []
		done = Event()
		def record_and_signal():
			results.append('ok')
			done.set()
		worker = Worker()
		worker.start()
		worker.submit(1, self._raise_error)
		worker.submit(2, record_and_signal)
		done.wait(timeout=2)
		worker.shutdown()
		self.assertEqual(['ok'], results)
	def test_priority_must_be_positive(self):
		worker = Worker()
		with self.assertRaises(ValueError):
			worker.submit(0, lambda: None)
	def _raise_error(self):
		raise RuntimeError('test')

class WorkItemTest(TestCase):
	def test_is_shutdown_zero_priority(self):
		item = WorkItem(0, lambda: None)
		self.assertTrue(item.is_shutdown())
	def test_is_not_shutdown(self):
		item = WorkItem(1, lambda: None)
		self.assertFalse(item.is_shutdown())
	def test_ordering(self):
		low = WorkItem(1, lambda: None)
		high = WorkItem(5, lambda: None)
		self.assertLess(low, high)
	def test_run_captures_exception(self):
		captured = []
		import sys
		original = sys.excepthook
		sys.excepthook = lambda *args: captured.append(args[1])
		try:
			item = WorkItem(1, self._raise)
			item.run()
		finally:
			sys.excepthook = original
		self.assertEqual(1, len(captured))
		self.assertIsInstance(captured[0], ValueError)
	def _raise(self):
		raise ValueError('test')
