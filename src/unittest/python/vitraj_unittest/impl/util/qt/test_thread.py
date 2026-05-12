from vitraj.impl.util.qt.thread import Task
from unittest import TestCase

class TaskTest(TestCase):
	def test_simple_run(self):
		args = (1,)
		kwargs = {'optional': True}
		def f(*args, **kwargs):
			return args, kwargs
		task = Task(f, args, kwargs)
		task()
		self.assertEqual((args, kwargs), task.result)
	def test_raising_exception(self):
		exception = Exception()
		def raise_exception():
			raise exception
		task = Task(raise_exception, (), {})
		task()
		with self.assertRaises(Exception) as cm:
			task.result
		self.assertIs(exception, cm.exception)