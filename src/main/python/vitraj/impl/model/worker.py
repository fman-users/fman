from functools import total_ordering
from queue import PriorityQueue
from threading import Thread, Lock

import sys

class Worker:
	def __init__(self):
		self._thread = Thread(target=self._run, daemon=True)
		self._queue = PriorityQueue()
		self._shutdown = False
		self._shutdown_lock = Lock()
	def start(self):
		self._thread.start()
	def submit(self, priority, fn, *args, **kwargs):
		"""
		Lower priority means "run sooner".
		"""
		if priority < 1:
			raise ValueError('priority must be >= 1')
		with self._shutdown_lock:
			if self._shutdown:
				return
			self._queue.put(WorkItem(priority, fn, *args, *kwargs))
	def shutdown(self):
		with self._shutdown_lock:
			self._shutdown = True
			self._queue.put(WorkItem(0, lambda: None))
		self._thread.join()
	def _run(self):
		while True:
			task = self._queue.get()
			if task.is_shutdown():
				break
			task.run()
			self._queue.task_done()

@total_ordering
class WorkItem:
	def __init__(self, priority, fn, *args, **kwargs):
		self._fn = fn
		self._args = args
		self._kwargs = kwargs
		self._priority = priority
	def run(self):
		try:
			self._fn(*self._args, **self._kwargs)
		except BaseException as e:
			sys.excepthook(type(e), e, e.__traceback__)
	def is_shutdown(self):
		return not self._priority
	def __lt__(self, other):
		try:
			return self._priority < other._priority
		except AttributeError:
			return NotImplemented
	def __eq__(self, other):
		try:
			return self._fn, self._args, self._kwargs, self._priority == \
				   other._fn, other._args, other._kwargs, other._priority
		except AttributeError:
			return NotImplemented