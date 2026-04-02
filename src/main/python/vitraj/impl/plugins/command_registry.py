from contextlib import contextmanager
from vitraj.impl.plugins.plugin import ReportExceptions
from threading import Thread, get_ident
from weakref import WeakKeyDictionary

import re

class CommandRegistry:
	def __init__(self, main_thread_id=None):
		if main_thread_id is None:
			main_thread_id = get_ident()
		self._main_thread = main_thread_id
	def _run_outside_main_thread(self, f, args):
		if get_ident() == self._main_thread:
			Thread(target=f, args=args, daemon=True).start()
		else:
			f(*args)

class ApplicationCommandRegistry(CommandRegistry):
	"""
	Assumed to be instantiated in main thread - see CommandRegistry#__init__().
	"""
	def __init__(self, window, error_handler, callback):
		super().__init__()
		self._window = window
		self._error_handler = error_handler
		self._callback = callback
		self._commands = {}
	def register_command(self, name, cls):
		try:
			command = cls(self._window)
		except Exception:
			self._error_handler.report(
				'Could not instantiate command %r.' % cls.__name__
			)
			command = lambda *_, **__: None
		self._commands[name] = command
	def unregister_command(self, name):
		try:
			del self._commands[name]
		except KeyError:
			# fman's API requires us to raise ValueError, not KeyError:
			raise ValueError('Command %r is not registered' % name) from None
	def get_commands(self):
		return set(self._commands)
	def execute_command(self, name, args=None):
		if args is None:
			args = {}
		command = self._commands[name]
		self._run_outside_main_thread(self._execute_command, (command, args))
	def get_command_aliases(self, name):
		command = self._commands[name]
		try:
			return command.aliases
		except AttributeError:
			return _get_default_aliases(command.__class__)
	def is_command_visible(self, name):
		command = self._commands[name]
		return command.is_visible()
	def _execute_command(self, command, args):
		class_name = command.__class__.__name__
		self._callback.before_command(class_name)
		msg_on_err = 'Command %r raised error.' % class_name
		try:
			with ReportExceptions(self._error_handler, msg_on_err):
				command(**args)
		except Exception:
			pass
		else:
			self._callback.after_command(class_name)

class PaneCommandRegistry(CommandRegistry):

	"""
	Assumed to be instantiated in main thread - see CommandRegistry#__init__().
	"""

	_DEFAULT = object()

	def __init__(self, error_handler, callback):
		super().__init__()
		self._error_handler = error_handler
		self._callback = callback
		self._command_classes = {}
		self._command_instances = WeakKeyDictionary()
	def register_command(self, name, cls):
		self._command_classes[name] = cls
	def unregister_command(self, name):
		try:
			del self._command_classes[name]
		except KeyError:
			# fman's API requires us to raise ValueError, not KeyError:
			raise ValueError('Command %r is not registered' % name) from None
		for commands in self._command_instances.values():
			try:
				del commands[name]
			except KeyError:
				pass
	def get_commands(self):
		return set(self._command_classes)
	def execute_command(self, name, args, pane, file_under_cursor=_DEFAULT):
		command = self._get_command(pane, name)
		if command is None:
			# Command could not be instantiated.
			return
		thread_args = (command, args, pane, file_under_cursor)
		self._run_outside_main_thread(self._execute_command, thread_args)
	def get_command_aliases(self, name):
		command_class = self._command_classes[name]
		try:
			return command_class.aliases
		except AttributeError:
			return _get_default_aliases(command_class)
	def is_command_visible(self, name, pane, file_under_cursor=_DEFAULT):
		command = self._get_command(pane, name)
		if command is None:
			# Command could not be instantiated.
			return None
		with self._set_context(pane, file_under_cursor):
			return command.is_visible()
	def _execute_command(self, command, args, pane, file_under_cursor):
		class_name = command.__class__.__name__
		self._callback.before_command(class_name)
		with self._set_context(pane, file_under_cursor):
			msg_on_err = 'Command %r raised error.' % class_name
			try:
				with ReportExceptions(self._error_handler, msg_on_err):
					command(**args)
			except Exception:
				pass
			else:
				self._callback.after_command(class_name)
	def _get_command(self, pane, name):
		try:
			commands = self._command_instances[pane]
		except KeyError:
			commands = self._command_instances[pane] = {}
		try:
			return commands[name]
		except KeyError:
			cmd_class = self._command_classes[name]
			try:
				result = cmd_class(pane)
			except Exception:
				self._error_handler.report(
					'Could not instantiate command %r.' % cmd_class.__name__
				)
				result = None
			commands[name] = result
			return result
	@contextmanager
	def _set_context(self, pane, file_under_cursor=_DEFAULT):
		if file_under_cursor is not self._DEFAULT:
			cm = pane._override_file_under_cursor(file_under_cursor)
			cm.__enter__()
		yield
		if file_under_cursor is not self._DEFAULT:
			cm.__exit__(None, None, None)

def _get_default_aliases(cmd_class):
	return re.sub(r'([a-z])([A-Z])', r'\1 \2', cmd_class.__name__)\
			   .lower().capitalize(),