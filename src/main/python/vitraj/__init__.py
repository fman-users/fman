from . import clipboard
from .url import dirname
from .impl.task import StubProgressDialog, ChildProgressDialog
from contextlib import contextmanager
from fbs_runtime import platform
from os import getenv
from os.path import join, expanduser
from PyQt5.QtWidgets import QMessageBox

import re

__all__ = [
	'ApplicationCommand', 'DirectoryPaneCommand', 'DirectoryPaneListener',
	'load_json', 'save_json',
	'show_alert', 'show_prompt', 'show_status_message', 'clear_status_message',
	'show_file_open_dialog',
	'show_quicksearch', 'QuicksearchItem',
	'get_application_commands', 'run_application_command',
	'get_application_command_aliases', 'load_plugin', 'unload_plugin',
	'clipboard',
	'submit_task', 'Task',
	'PLATFORM', 'FMAN_VERSION', 'DATA_DIRECTORY',
	'OK', 'CANCEL', 'YES', 'NO', 'YES_TO_ALL', 'NO_TO_ALL', 'ABORT'
]

YES = QMessageBox.Yes
NO = QMessageBox.No
YES_TO_ALL = QMessageBox.YesToAll
NO_TO_ALL = QMessageBox.NoToAll
ABORT = QMessageBox.Abort
OK = QMessageBox.Ok
CANCEL = QMessageBox.Cancel

FMAN_VERSION = ''

PLATFORM = platform.name()

if PLATFORM == 'Windows':
	DATA_DIRECTORY = join(getenv('APPDATA'), 'vitraj')
elif PLATFORM == 'Mac':
	DATA_DIRECTORY = expanduser('~/Library/Application Support/vitraj')
elif PLATFORM == 'Linux':
	DATA_DIRECTORY = expanduser('~/.config/vitraj')

class ApplicationCommand:
	def __init__(self, window):
		self.window = window
	def __call__(self, *args, **kwargs):
		raise NotImplementedError()
	@property
	def aliases(self):
		return re.sub(r'([a-z])([A-Z])', r'\1 \2', self.__class__.__name__) \
				   .lower().capitalize(),

def _set_path_onerror(e, url):
	if isinstance(e, FileNotFoundError):
		return dirname(url)
	raise

class DirectoryPane:
	def __init__(self, window, widget, command_registry):
		self.window = window
		self._widget = widget
		self._command_registry = command_registry
		self._listeners = []
		self._get_file_under_cursor_orig = self.get_file_under_cursor

	def _add_listener(self, listener):
		self._listeners.append(listener)
	def _broadcast(self, event, *args):
		for listener in self._listeners:
			getattr(listener, event)(*args)

	def get_commands(self):
		return self._command_registry.get_commands()
	def run_command(self, name, args=None):
		if args is None:
			args = {}
		while True:
			for listener in self._listeners:
				rewritten = listener.on_command(name, args)
				if rewritten:
					name, args = rewritten
					break
			else:
				break
		return self._command_registry.execute_command(name, args, self)
	def get_command_aliases(self, command_name):
		return self._command_registry.get_command_aliases(command_name)
	def is_command_visible(self, command_name):
		return self._command_registry.is_command_visible(command_name, self)

	def _add_filter(self, filter_):
		self._widget.add_filter(filter_)
	def _remove_filter(self, filter_):
		self._widget.remove_filter(filter_)

	def get_selected_files(self):
		return self._widget.get_selected_files()
	def get_file_under_cursor(self):
		return self._widget.get_file_under_cursor()
	def move_cursor_down(self, toggle_selection=False):
		self._widget.move_cursor_down(toggle_selection)
	def move_cursor_up(self, toggle_selection=False):
		self._widget.move_cursor_up(toggle_selection)
	def move_cursor_home(self, toggle_selection=False):
		self._widget.move_cursor_home(toggle_selection)
	def move_cursor_end(self, toggle_selection=False):
		self._widget.move_cursor_end(toggle_selection)
	def move_cursor_page_down(self, toggle_selection=False):
		self._widget.move_cursor_page_down(toggle_selection)
	def move_cursor_page_up(self, toggle_selection=False):
		self._widget.move_cursor_page_up(toggle_selection)
	def place_cursor_at(self, file_url):
		self._widget.place_cursor_at(file_url)
	# TODO: Rename to get_location()
	def get_path(self):
		return self._widget.get_location()
	# TODO: Rename to set_location(...)
	def set_path(self, dir_url, callback=None, onerror=_set_path_onerror):
		args = dir_url, '', True
		while True:
			for listener in self._listeners:
				rewritten = listener.before_location_change(*args)
				if rewritten and rewritten != args:
					args = rewritten
					break
			else:
				break
		self._widget.set_location(args[0], args[1], args[2], callback, onerror)
	def reload(self):
		self._widget.reload()
	def edit_name(self, file_url, selection_start=0, selection_end=None):
		self._widget.edit_name(file_url, selection_start, selection_end)
	def select_all(self):
		self._widget.select_all()
	def clear_selection(self):
		self._widget.clear_selection()
	def toggle_selection(self, file_url):
		self._widget.toggle_selection(file_url)
	def select(self, file_urls):
		self._widget.select(file_urls, ignore_errors=True)
	def deselect(self, file_urls):
		self._widget.deselect(file_urls, ignore_errors=True)
	def focus(self):
		self._widget.focus()
	def get_columns(self):
		return self._widget.get_columns()
	def set_sort_column(self, column, ascending=True):
		self._widget.set_sort_column(column, ascending)
	def get_sort_column(self):
		return self._widget.get_sort_column()
	def _has_focus(self):
		return self._widget.hasFocus()
	@contextmanager
	def _override_file_under_cursor(self, value):
		self.get_file_under_cursor = lambda: value
		yield
		self.get_file_under_cursor = self._get_file_under_cursor_orig

class Window:
	def __init__(self, widget, panecmd_registry):
		self._widget = widget
		self._panecmd_registry = panecmd_registry
		self._panes = []
	def get_panes(self):
		return self._panes
	def minimize(self):
		self._widget.minimize()
	def add_pane(self):
		pane_widget = self._widget.add_pane()
		pane = DirectoryPane(self, pane_widget, self._panecmd_registry)
		self._panes.append(pane)
		_get_controller().register_pane(pane_widget, pane)
		return pane
	def activate_panel(self, pane, panel_widget, panel_id):
		return self._widget.activate_panel(pane, panel_widget, panel_id)
	def deactivate_panel(self, pane):
		return self._widget.deactivate_panel(pane)
	def get_active_panel(self, pane):
		return self._widget.get_active_panel(pane)
	def is_panel_active(self, pane, panel_id=None):
		return self._widget.is_panel_active(pane, panel_id)

class DirectoryPaneCommand:
	def __init__(self, pane):
		self.pane = pane
	def __call__(self, *args, **kwargs):
		raise NotImplementedError()
	def is_visible(self):
		return True
	def get_chosen_files(self):
		selected_files = self.pane.get_selected_files()
		if selected_files:
			return selected_files
		file_under_cursor = self.pane.get_file_under_cursor()
		if file_under_cursor:
			return [file_under_cursor]
		return []

class DirectoryPaneListener:
	def __init__(self, pane):
		self.pane = pane
	def on_doubleclicked(self, file_url):
		pass
	def on_name_edited(self, file_url, new_name):
		pass
	# TODO: Rename to after_location_change()
	def on_path_changed(self):
		pass
	def before_location_change(self, url, sort_column='', ascending=True):
		pass
	def on_files_dropped(self, file_urls, dest_dir, is_copy_not_move):
		pass
	def on_command(self, command_name, args):
		pass
	def on_location_bar_clicked(self):
		pass

def load_json(name, default=None, save_on_quit=False):
	return _get_plugin_support().load_json(name, default, save_on_quit)

def save_json(name, value=None):
	return _get_plugin_support().save_json(name, value)

def show_alert(text, buttons=OK, default_button=OK):
	return _get_ui().show_alert(text, buttons, default_button)

def show_prompt(text, default='', selection_start=0, selection_end=None):
	return _get_ui().show_prompt(text, default, selection_start, selection_end)

def show_status_message(text, timeout_secs=None):
	return _get_ui().show_status_message(text, timeout_secs)

def clear_status_message():
	return _get_ui().clear_status_message()

def show_file_open_dialog(caption, dir_path, filter_text=''):
	return _get_ui().show_file_open_dialog(caption, dir_path, filter_text)

def show_quicksearch(get_items, get_tab_completion=None, query='', item=0):
	return _get_ui().show_quicksearch(
		get_items, get_tab_completion, query, item
	)

class QuicksearchItem:
	def __init__(
		self, value, title=None, highlight=None, hint='', description=''
	):
		if title is None:
			title = value
		if highlight is None:
			highlight = []
		self.value = value
		self.title = title
		self.highlight = highlight
		self.hint = hint
		self.description = description
	def __repr__(self):
		return '<%s: %s>' % (self.__class__.__name__, self.title)

def get_application_commands():
	return _get_plugin_support().get_application_commands()

def run_application_command(name, args=None):
	if args is None:
		args = {}
	return _get_plugin_support().run_application_command(name, args)

def get_application_command_aliases(command_name):
	return _get_plugin_support().get_application_command_aliases(command_name)

def load_plugin(plugin_path):
	return _get_plugin_support().load_plugin(plugin_path)

def unload_plugin(plugin_path):
	"""
	Raises ValueError if the plugin was not loaded.
	"""
	_get_plugin_support().unload_plugin(plugin_path)

class Task:

	class Canceled(KeyboardInterrupt):
		pass

	def __init__(self, title, size=0, fn=lambda: None, args=(), kwargs=None):
		if kwargs is None:
			kwargs = {}
		self._title = title
		self._fn = fn
		self._args = args
		self._kwargs = kwargs
		self._size = size
		self._dialog = StubProgressDialog()
	def __call__(self):
		self._fn(*self._args, **self._kwargs)
	def get_title(self):
		return self._title
	def set_text(self, text):
		self._dialog.set_text(text)
	def set_size(self, size):
		self._size = size
		self._dialog.set_task_size(size)
	def get_size(self):
		return self._size
	def set_progress(self, progress):
		self._dialog.set_progress(progress)
	def get_progress(self):
		return self._dialog.get_progress()
	def check_canceled(self):
		if self._dialog.was_canceled():
			raise self.Canceled()
	def run(self, subtask):
		self.set_text(subtask.get_title())
		subtask._dialog = ChildProgressDialog(self._dialog)
		subtask()
		# Some tasks, especially those with size 1, may not "complete" their
		# progress at the end. Do it for them:
		subtask.set_progress(subtask.get_size())
	def show_alert(self, *args, **kwargs):
		return self._dialog.show_alert(*args, **kwargs)
	def __str__(self):
		return self._title

def submit_task(task):
	dialog = _get_ui().create_progress_dialog(task.get_title(), task.get_size())
	dialog_before = task._dialog
	task._dialog = dialog
	try:
		task()
	except Task.Canceled:
		pass
	finally:
		dialog.cancel()
		task._dialog = dialog_before

def _get_plugin_support():
	return _get_app_ctxt().plugin_support

def _get_controller():
	return _get_app_ctxt().controller

def _get_ui():
	return _get_app_ctxt().main_window

def _get_app_ctxt():
	from vitraj.impl.application_context import get_application_context
	return get_application_context()