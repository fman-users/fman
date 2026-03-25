from fbs_runtime.application_context import is_frozen
from fbs_runtime.excepthook import ExceptionHandler
from fman.impl.theme import ThemeError
from fman.impl.util import is_below_dir
from os.path import dirname, basename
from traceback import StackSummary, _some_str, extract_tb, TracebackException, \
	print_exception

import fman
import sys

class PluginErrorHandler(ExceptionHandler):
	def __init__(self, app):
		self._app = app
		self._main_window = None
		self._pending_error_messages = []
		self._plugin_dirs = []
	def add_dir(self, plugin_dir):
		self._plugin_dirs.append(plugin_dir)
	def remove_dir(self, plugin_dir):
		self._plugin_dirs.remove(plugin_dir)
	def handle(self, exc_type, exc_value, enriched_tb):
		causing_plugin = self._get_plugin_causing_error(enriched_tb)
		if causing_plugin and basename(causing_plugin) != 'Core':
			self.report('Plugin %r raised an error.' % basename(causing_plugin))
			return True
	def _get_plugin_causing_error(self, traceback):
		for frame in extract_tb(traceback):
			for plugin_dir in self._plugin_dirs:
				if is_below_dir(frame.filename, plugin_dir):
					return plugin_dir
	def report(self, message, exc=None):
		if exc is None:
			exc = sys.exc_info()[1]
		if exc:
			if not is_frozen():
				# The steps further below only show a pruned stack trace. During
				# development, it's useful if we also see the full stack trace:
				print_exception(type(exc), exc, exc.__traceback__)
			message += '\n\n' + self._get_plugin_traceback(exc)
		if self._main_window:
			self._main_window.show_alert(message)
		else:
			self._pending_error_messages.append(message)
	def handle_system_exit(self, code=0):
		self._app.exit(code)
	def on_main_window_shown(self, main_window):
		self._main_window = main_window
		if self._pending_error_messages:
			self._main_window.show_alert(self._pending_error_messages[0])
	def _get_plugin_traceback(self, exc):
		if isinstance(exc, ThemeError):
			return exc.description
		return format_traceback(exc, exclude_dirs=[dirname(fman.__file__)])

def format_traceback(exc, exclude_dirs):
	def tb_filter(tb):
		tb_file = extract_tb(tb)[0][0]
		for dir_ in exclude_dirs:
			if is_below_dir(tb_file, dir_):
				return False
		return True
	traceback_ = \
		TracebackExceptionWithTbFilter.from_exception(exc, tb_filter=tb_filter)
	return ''.join(traceback_.format())

class TracebackExceptionWithTbFilter(TracebackException):
	"""
	Copied and adapted from Python's `TracebackException`. Adds one
	additional constructor arg: `tb_filter`, a boolean predicate that determines
	which traceback entries should be included.
	"""
	@classmethod
	def from_exception(cls, exc, *args, **kwargs):
		return cls(type(exc), exc, exc.__traceback__, *args, **kwargs)
	def __init__(
		self, exc_type, exc_value, exc_traceback, *, limit=None,
		lookup_lines=True, capture_locals=False, _seen=None,
		tb_filter=None
	):
		if _seen is None:
			_seen = set()
		_seen.add(exc_value)
		if (exc_value and exc_value.__cause__ is not None
			and exc_value.__cause__ not in _seen):
			# This differs from stdlib's implementation:
			cause = TracebackExceptionWithTbFilter(
				type(exc_value.__cause__),
				exc_value.__cause__,
				exc_value.__cause__.__traceback__,
				limit=limit,
				lookup_lines=False,
				capture_locals=capture_locals,
				_seen=_seen,
				tb_filter=tb_filter
			)
		else:
			cause = None
		if (exc_value and exc_value.__context__ is not None
			and exc_value.__context__ not in _seen):
			# This differs from stdlib's implementation:
			context = TracebackExceptionWithTbFilter(
				type(exc_value.__context__),
				exc_value.__context__,
				exc_value.__context__.__traceback__,
				limit=limit,
				lookup_lines=False,
				capture_locals=capture_locals,
				_seen=_seen,
				tb_filter=tb_filter
			)
		else:
			context = None
		self.exc_traceback = exc_traceback
		self.__cause__ = cause
		self.__context__ = context
		# This differs from stdlib's implementation:
		self.stack = StackSummary.extract(
			walk_tb_with_filtering(exc_traceback, tb_filter), limit=limit,
			lookup_lines=lookup_lines, capture_locals=capture_locals
		)
		# This differs from stdlib's implementation:
		if exc_value:
			# Hide context when all its frames are hidden:
			self.__suppress_context__ = exc_value.__suppress_context__ or \
										(context and not context.stack.format())
		else:
			self.__suppress_context__ = False
		self.exc_type = exc_type
		self._str = _some_str(exc_value)
		if exc_type and issubclass(exc_type, SyntaxError):
			self.filename = exc_value.filename
			self.lineno = str(exc_value.lineno)
			self.text = exc_value.text
			self.offset = exc_value.offset
			self.msg = exc_value.msg
		if lookup_lines:
			self._load_lines()

def walk_tb_with_filtering(tb, tb_filter=None):
	while tb is not None:
		if tb_filter is None or tb_filter(tb):
			yield tb.tb_frame, tb.tb_lineno
		tb = tb.tb_next