from vitraj.impl.html_style import highlight, underline
from vitraj.impl.widgets import Overlay
from vitraj.impl.util.qt import connect_once
from vitraj.impl.util.qt.thread import run_in_main_thread

import re

class TourController:
	def __init__(self):
		self._tour = None
	def start(self, tour, step=0):
		if self._tour:
			self._tour.close_current_step()
		self._tour = tour
		self._tour.start(step)

class Tour:
	def __init__(self, name, main_window, pane, app, command_callback, metrics):
		self._name = name
		self._main_window = main_window
		self._pane = pane
		self._app = app
		self._command_callback = command_callback
		self._metrics = metrics
		self._curr_step_index = -1
		self._curr_step = None
		self._steps = self._get_steps()
	def _get_steps(self):
		raise NotImplementedError()
	@property
	def _pane_widget(self):
		return self._pane._widget
	def start(self, step=0):
		self._curr_step_index = step - 1
		self._next_step()
	def reject(self):
		self._track('AbortedTour', step=self._curr_step_index)
		self.close_current_step()
		self.on_close()
	def complete(self):
		self._track('CompletedTour', step=self._curr_step_index)
		self.close_current_step()
		self.on_close()
	def on_close(self):
		# Can be implemented by subclasses.
		pass
	def close_current_step(self):
		if not self._curr_step:
			return
		self._curr_step.close()
		self._command_callback.remove_listener(self._curr_step)
		self._disconnect_location_changed()
		self._curr_step = None
	def _next_step(self, delta=1):
		self._curr_step_index += delta
		self._track_current_step()
		self._show_current_screen()
	def _format_next_step_paragraph(self, *values):
		step_paras = self._steps[self._curr_step_index + 1]._paragraphs
		for i, value in enumerate(values):
			step_paras[i] %= value
	def _skip_steps(self, num_steps):
		return lambda: self._next_step(num_steps + 1)
	def _track_current_step(self):
		self._track('StartedTourStep', step=self._curr_step_index)
	def _show_current_screen(self):
		if self._curr_step:
			self.close_current_step()
		self._curr_step = self._steps[self._curr_step_index]
		self._command_callback.add_listener(self._curr_step)
		self._connect_location_changed()
		self._curr_step.show(self._main_window)
	@run_in_main_thread # <- Unclear why, but method has no effect without this.
	def _connect_location_changed(self):
		self._pane_widget.location_changed.connect(
			self._curr_step.on_location_changed
		)
	@run_in_main_thread # We connected in main thread, so also disconnect there.
	def _disconnect_location_changed(self):
		self._pane_widget.location_changed.disconnect(
			self._curr_step.on_location_changed
		)
	def _after_dialog_shown(self, callback):
		return AfterDialogShown(self._main_window, callback)
	def _track(self, event, **kwargs):
		kwargs['tour'] = self._name
		self._metrics.track(event, kwargs)

class AfterDialogShown:
	def __init__(self, main_window, callback):
		self._main_window = main_window
		self._callback = callback
	@run_in_main_thread
	def __call__(self):
		connect_once(self._main_window.before_dialog, self._before_dialog)
	def _before_dialog(self, dialog):
		connect_once(dialog.shown, self._callback)

class TourStep:
	def __init__(self, title, paragraphs, command_actions=None, buttons=None):
		self._title = title
		self._paragraphs = paragraphs
		self._buttons = buttons or []
		self._command_actions = command_actions or {}
		self._screen = None
	@run_in_main_thread
	def show(self, parent):
		self._screen = Overlay(parent, self._get_html(), self._buttons)
		parent.show_overlay(self._screen)
	@run_in_main_thread
	def close(self):
		if self._screen:
			self._screen.close()
		self._screen = None
	def before_command(self, name):
		try:
			action = self._command_actions['before'][name]
		except KeyError:
			pass
		else:
			action()
	def after_command(self, name):
		try:
			action = self._command_actions['after'][name]
		except KeyError:
			pass
		else:
			action()
	def on_location_changed(self, _):
		try:
			action = self._command_actions['on']['location_changed']
		except KeyError:
			pass
		else:
			action()
	def _get_html(self):
		return self._get_title_html() + self._get_body_html()
	def _get_title_html(self):
		if not self._title:
			return ''
		return "<center style='line-height: 130%'>" \
					"<h2 style='color: #bbbbbb;'>" + self._title + "</h2>" \
				"</center>"
	def _get_body_html(self):
		result = ''
		is_list = False
		for line in self._paragraphs:
			if line.startswith('* '):
				line = '<li style="line-height: 150%%;">%s</li>' % \
					   line[2:]
				if not is_list:
					line = '<ul>' + line
					is_list = True
			else:
				line = '<p style="line-height: 115%%;">%s</p>' % line
				if is_list:
					line = '</ul>' + line
					is_list = False
			line = re.subn(r'\*([^*]+)\*', highlight(r'\1'), line)[0]
			line = re.subn(r'_([^_]+)_', underline(r'\1'), line)[0]
			result += line
		return result