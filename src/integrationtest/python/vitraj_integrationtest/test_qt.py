"""
This module contains all tests that require a QApplication to run.

In an ideal world, tests that require a QApplication would start it in setUp(),
and stop it in tearDown(). Unfortunately, this does not work: A process can
only start one QApplication. Further attempts segfault.

The purpose of this module is to work around the above limitation. It manages
the QApplication lifecycle for tests that require it. To achieve this,
setUpModule() and tearDownModule() are used to start / stop the app exactly once
for the entire process. Unfortunately, this requires us to define all affected
tests here, in this module.

A subtle but important point is that the QApp managed by this module runs in
a separate thread, which is not the main thread of the process. This normally
makes Qt print a warning. We suppress it with a custom QtMessageHandler.
"""

from concurrent.futures import ThreadPoolExecutor
from fbs_runtime.platform import is_mac
from vitraj.impl.util.qt.thread import run_in_thread
from vitraj_integrationtest.impl.model.test___init__ import \
	SortedFileSystemModelAT
from vitraj_integrationtest.impl.util.qt.test_thread import RunInThreadAT
from PyQt5.QtCore import pyqtSignal, Qt, qInstallMessageHandler
from PyQt5.QtWidgets import QApplication
from threading import Event
from unittest import TestCase, skipIf

def _reason_to_skip():
	if is_mac():
		return 'macOS does not allow running Qt in non-main thread'

@skipIf(_reason_to_skip(), _reason_to_skip())
class QtIT(TestCase):
	def run_in_app(self, f, *args, **kwargs):
		return _QtApp.run(f, *args, **kwargs)

class SortedFileSystemModelIT(SortedFileSystemModelAT, QtIT):
	pass

class RunInThreadIT(RunInThreadAT, QtIT):
	pass

def setUpModule():
	if not _reason_to_skip():
		_QtApp.start()

def tearDownModule():
	if not _reason_to_skip():
		_QtApp.shutdown()

class _QtApp:
	@classmethod
	def start(cls):
		qInstallMessageHandler(cls._qt_message_handler)
		started = Event()
		cls._executor = ThreadPoolExecutor(max_workers=1)
		cls._executor.submit(cls._start_app, started.set)
		started.wait()
	@classmethod
	def run(cls, f, *args, **kwargs):
		return run_in_thread(cls._app.thread)(f)(*args, **kwargs)
	@classmethod
	def shutdown(cls):
		cls.run(cls._app.exit)
		cls._executor.shutdown(wait=True)
	@classmethod
	def _start_app(cls, callback):
		cls._app = _Application([])
		cls._app.running.connect(callback, Qt.QueuedConnection)
		cls._app.running.emit()
		cls._app.exec_()
	@classmethod
	def _qt_message_handler(cls, msg_type, context, msg):
		if msg == 'WARNING: QApplication was not created in the main() thread.':
			return
		# Would like to call Qt's original message handler here, but there
		# doesn't seem to be a way in PyQt to get a reference to it. So just
		# print():
		print(msg)
	_app = None
	_executor = None

# It is tempting to use the more "basic" QCoreApplication here instead of
# QApplication. But this produces segmentation faults when we try to instantiate
# QPixmaps. So use the more "complete" QApplication:
class _Application(QApplication):
	running = pyqtSignal()