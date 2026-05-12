from vitraj.impl.util.qt.thread import run_in_thread, Executor
from PyQt5.QtCore import QThread
from threading import get_ident

class RunInThreadAT: # Instantiated in vitraj_integrationtest.test_qt
	def test_same_thread(self):
		@run_in_thread(QThread.currentThread)
		def f():
			return 3
		self.assertEqual(3, f())
	def test_other_thread(self):
		this_thread_id = get_ident()
		@run_in_thread(lambda: self.other_thread)
		def f():
			return get_ident()
		other_thread_id = f()
		self.assertNotEqual(this_thread_id, other_thread_id)
	def test_same_thread_raises_exc(self):
		self._test_thread_raises_exc(QThread.currentThread)
	def test_other_thread_raises_exc(self):
		self._test_thread_raises_exc(lambda: self.other_thread)
	def _test_thread_raises_exc(self, thread):
		e = Exception()
		@run_in_thread(thread)
		def raise_exc():
			raise e
		with self.assertRaises(Exception) as cm:
			raise_exc()
		self.assertIs(e, cm.exception)
	def setUp(self):
		super().setUp()
		self.other_thread = QThread()
		self.other_thread.start()
	def tearDown(self):
		self.other_thread.exit()
		self.other_thread.wait()
		Executor._INSTANCE = None
		super().tearDown()