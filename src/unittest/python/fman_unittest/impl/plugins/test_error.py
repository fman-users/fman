from fman.impl.plugins.error import format_traceback, walk_tb_with_filtering, \
	TracebackExceptionWithTbFilter, PluginErrorHandler
from unittest import TestCase

import os

class FormatTracebackTest(TestCase):
	def test_excludes_frames_from_dir(self):
		exc = self._make_exception()
		result = format_traceback(exc, exclude_dirs=[os.path.dirname(__file__)])
		self.assertNotIn('test_error.py', result)
	def test_includes_frames_outside_dir(self):
		exc = self._make_exception()
		result = format_traceback(exc, exclude_dirs=['/nonexistent'])
		self.assertIn('_make_exception', result)
	def test_empty_exclude_dirs(self):
		exc = self._make_exception()
		result = format_traceback(exc, exclude_dirs=[])
		self.assertIn('ValueError', result)
	def _make_exception(self):
		try:
			raise ValueError('test error')
		except ValueError as e:
			return e

class WalkTbWithFilteringTest(TestCase):
	def test_no_filter_yields_all(self):
		exc = self._make_exception()
		frames = list(walk_tb_with_filtering(exc.__traceback__))
		self.assertGreaterEqual(len(frames), 1)
	def test_filter_excludes_frames(self):
		exc = self._make_exception()
		frames = list(walk_tb_with_filtering(exc.__traceback__, lambda tb: False))
		self.assertEqual([], frames)
	def test_filter_none_yields_all(self):
		exc = self._make_exception()
		all_frames = list(walk_tb_with_filtering(exc.__traceback__))
		none_frames = list(walk_tb_with_filtering(exc.__traceback__, None))
		self.assertEqual(len(all_frames), len(none_frames))
	def _make_exception(self):
		try:
			raise RuntimeError('test')
		except RuntimeError as e:
			return e

class TracebackExceptionWithTbFilterTest(TestCase):
	def test_from_exception(self):
		exc = self._make_chained_exception()
		te = TracebackExceptionWithTbFilter.from_exception(exc)
		formatted = ''.join(te.format())
		self.assertIn('RuntimeError', formatted)
	def test_with_cause(self):
		exc = self._make_chained_exception()
		te = TracebackExceptionWithTbFilter.from_exception(exc)
		formatted = ''.join(te.format())
		self.assertIn('ValueError', formatted)
		self.assertIn('RuntimeError', formatted)
	def test_with_tb_filter(self):
		exc = self._make_chained_exception()
		te = TracebackExceptionWithTbFilter.from_exception(
			exc, tb_filter=lambda tb: True
		)
		formatted = ''.join(te.format())
		self.assertIn('RuntimeError', formatted)
	def test_filter_all_frames(self):
		exc = self._make_chained_exception()
		te = TracebackExceptionWithTbFilter.from_exception(
			exc, tb_filter=lambda tb: False
		)
		formatted = ''.join(te.format())
		self.assertIn('RuntimeError', formatted)
		self.assertNotIn('File', formatted)
	def test_context_suppressed_when_all_frames_hidden(self):
		exc = self._make_chained_exception()
		te = TracebackExceptionWithTbFilter.from_exception(
			exc, tb_filter=lambda tb: False
		)
		self.assertTrue(te.__suppress_context__)
	def _make_chained_exception(self):
		try:
			try:
				raise ValueError('cause')
			except ValueError:
				raise RuntimeError('effect')
		except RuntimeError as e:
			return e

class PluginErrorHandlerTest(TestCase):
	def test_report_stores_pending_without_window(self):
		handler = self._make_handler()
		handler.report('test message', exc=False)
		self.assertEqual(['test message'], handler._pending_error_messages)
	def test_report_shows_on_window(self):
		handler = self._make_handler()
		window = StubMainWindow()
		handler.on_main_window_shown(window)
		handler.report('hello', exc=False)
		self.assertEqual(['hello'], window.alerts)
	def test_pending_messages_shown_on_window(self):
		handler = self._make_handler()
		handler.report('pending', exc=False)
		window = StubMainWindow()
		handler.on_main_window_shown(window)
		self.assertEqual(['pending'], window.alerts)
	def test_add_remove_dir(self):
		handler = self._make_handler()
		handler.add_dir('/plugins/Foo')
		handler.add_dir('/plugins/Bar')
		handler.remove_dir('/plugins/Foo')
		self.assertEqual(['/plugins/Bar'], handler._plugin_dirs)
	def _make_handler(self):
		return PluginErrorHandler(StubApp())

class StubApp:
	def exit(self, code=0):
		pass

class StubMainWindow:
	def __init__(self):
		self.alerts = []
	def show_alert(self, message):
		self.alerts.append(message)
