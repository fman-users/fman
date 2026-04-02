from fbs_runtime.platform import is_windows, is_mac
from vitraj import OK
from vitraj.impl.model import SortedFileSystemModel
from vitraj.impl.quicksearch import Quicksearch
from vitraj.impl.util.qt import disable_window_animations_mac, Key_Escape, \
	NoFocus, Key_Backspace, DisplayRole
from vitraj.impl.util.qt.thread import run_in_main_thread
from vitraj.impl.view.location_bar import LocationBar
from vitraj.impl.view import FileListView, Layout, set_selection
from vitraj.url import as_human_readable, basename
from PyQt5.QtCore import pyqtSignal, QTimer, Qt, QEvent, QSize
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QWidget, QMainWindow, QSplitter, QStatusBar, \
	QMessageBox, QInputDialog, QLineEdit, QFileDialog, QLabel, QDialog, \
	QHBoxLayout, QPushButton, QVBoxLayout, QSplitterHandle, QApplication, \
	QFrame, QAction, QSizePolicy, QProgressDialog, QProgressBar
from random import randint, randrange

import re

class Application(QApplication):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._main_window = None
		self.applicationStateChanged.connect(self._on_state_changed)
	def set_main_window(self, main_window):
		self._main_window = main_window
		# Ensure all other windows are closed as well when the main window
		# is closed. (This in particular closes windows opened by plugins.)
		main_window.closed.connect(self.quit)
	@run_in_main_thread
	def exit(self, returnCode=0):
		if self._main_window is not None:
			self._main_window.close()
		super().exit(returnCode)
	@run_in_main_thread
	def set_style_sheet(self, stylesheet):
		self.setStyleSheet(stylesheet)
	def _on_state_changed(self, new_state):
		if new_state == Qt.ApplicationActive:
			for pane in self._main_window.get_panes():
				pane.reload()

class DirectoryPaneWidget(QWidget):

	location_changed = pyqtSignal(QWidget)
	location_bar_clicked = pyqtSignal(QWidget)

	def __init__(self, fs, null_location, parent, controller):
		super().__init__(parent)
		self._location_bar = LocationBar(self)
		self._model = SortedFileSystemModel(self, fs, null_location)
		self._model.file_renamed.connect(self._on_file_renamed)
		self._model.files_dropped.connect(self._on_files_dropped)
		self._file_view = FileListView(
			self, lambda *args: controller.on_context_menu(self, *args)
		)
		self._file_view.setModel(self._model)
		self._file_view.doubleClicked.connect(self._on_doubleclicked)
		self._file_view.key_press_event_filter = self._on_key_pressed
		self.setLayout(Layout(self._location_bar, self._file_view))
		self._location_bar.setFocusProxy(self._file_view)
		self.setFocusProxy(self._file_view)
		self._controller = controller
		self._model.location_changed.connect(self._on_location_changed)
		self._model.location_loaded.connect(self._on_location_loaded)
		self._location_bar.clicked.connect(
			lambda: self.location_bar_clicked.emit(self)
		)
		self._filter_bar = FilterBar(self, self._model, self._file_view)
	def resizeEvent(self, e):
		super().resizeEvent(e)
		self._filter_bar.reposition()
	@run_in_main_thread
	def move_cursor_up(self, toggle_selection=False):
		self._file_view.move_cursor_up(toggle_selection)
	@run_in_main_thread
	def move_cursor_down(self, toggle_selection=False):
		self._file_view.move_cursor_down(toggle_selection)
	@run_in_main_thread
	def move_cursor_home(self, toggle_selection=False):
		self._file_view.move_cursor_home(toggle_selection)
	@run_in_main_thread
	def move_cursor_end(self, toggle_selection=False):
		self._file_view.move_cursor_end(toggle_selection)
	@run_in_main_thread
	def move_cursor_page_up(self, toggle_selection=False):
		self._file_view.move_cursor_page_up(toggle_selection)
	@run_in_main_thread
	def move_cursor_page_down(self, toggle_selection=False):
		self._file_view.move_cursor_page_down(toggle_selection)
	@run_in_main_thread
	def focus(self):
		self.setFocus()
	@run_in_main_thread
	def select_all(self):
		self._file_view.selectAll()
	@run_in_main_thread
	def clear_selection(self):
		self._file_view.clearSelection()
	@run_in_main_thread
	def toggle_selection(self, file_url):
		self._file_view.toggle_selection(file_url)
	@run_in_main_thread
	def select(self, file_urls, ignore_errors=False):
		self._file_view.select(file_urls, ignore_errors)
	@run_in_main_thread
	def deselect(self, file_urls, ignore_errors=False):
		self._file_view.deselect(file_urls, ignore_errors)
	@run_in_main_thread
	def get_selected_files(self):
		return self._file_view.get_selected_files()
	@run_in_main_thread
	def get_file_under_cursor(self):
		return self._file_view.get_file_under_cursor()
	@run_in_main_thread
	def get_location(self):
		return self._model.get_location()
	def set_location(
		self, url, sort_column='', ascending=True, callback=None, onerror=None
	):
		self._model.set_location(url, sort_column, ascending, callback, onerror)
	def reload(self):
		self._model.reload()
	@run_in_main_thread
	def place_cursor_at(self, file_url):
		self._file_view.place_cursor_at(file_url)
	@run_in_main_thread
	def edit_name(self, file_url, selection_start=0, selection_end=None):
		self._file_view.edit_name(file_url, selection_start, selection_end)
	@run_in_main_thread
	def add_filter(self, filter_):
		self._model.add_filter(filter_)
	@run_in_main_thread
	def remove_filter(self, filter_):
		self._model.remove_filter(filter_)
	@property
	def window(self):
		return self.parentWidget().parentWidget()
	def get_columns(self):
		return [
			column.get_qualified_name() for column in self._model.get_columns()
		]
	@run_in_main_thread
	def set_sort_column(self, column, ascending=True):
		column_index = self.get_columns().index(column)
		order = Qt.AscendingOrder if ascending else Qt.DescendingOrder
		self._file_view.sortByColumn(column_index, order)
	@run_in_main_thread
	def get_sort_column(self):
		header = self._file_view.horizontalHeader()
		column_index = header.sortIndicatorSection()
		column = self.get_columns()[column_index]
		ascending = header.sortIndicatorOrder() == Qt.AscendingOrder
		return column, ascending
	@run_in_main_thread
	def get_column_widths(self):
		return [self._file_view.columnWidth(i) for i in (0, 1)]
	@run_in_main_thread
	def set_column_widths(self, column_widths):
		num_columns = self._model.columnCount()
		if len(column_widths) != num_columns:
			raise ValueError(
				'Wrong number of columns: len(%r) != %d'
				% (column_widths, num_columns)
			)
		for i, width in enumerate(column_widths):
			self._file_view.setColumnWidth(i, width)
	def _on_doubleclicked(self, index):
		self._controller.on_doubleclicked(self, self._model.url(index))
	def _on_key_pressed(self, event):
		if self._filter_bar.isVisible() and event.key() == Key_Backspace:
			self._filter_bar.handle_keypress(event)
			return True
		if self._controller.handle_shortcut(self, event):
			return True
		if self._filter_bar.handle_keypress(event):
			return True
		if self._controller.handle_nonexistent_shortcut(self, event):
			return True
		event.ignore()
		return False
	def _on_file_renamed(self, *args):
		self._controller.on_file_renamed(self, *args)
	def _on_files_dropped(self, *args):
		self._controller.on_files_dropped(self, *args)
	def _on_location_changed(self, url):
		self._filter_bar.close()
		self._location_bar.setText(as_human_readable(url))
	def _on_location_loaded(self, url):
		if not self.get_file_under_cursor():
			self.move_cursor_home()
		self._file_view.resizeColumnsToContents()
		self.location_changed.emit(self)

class FilterBar(QFrame):
	def __init__(self, parent, model, file_view):
		super().__init__(parent)
		self._model = model
		self._file_view = file_view
		self.setVisible(False)
		self._input = QLineEdit()
		self._input.textChanged.connect(self._on_text_changed)
		self.setFrameShape(QFrame.Box)
		self.setFrameShadow(QFrame.Raised)
		layout = QVBoxLayout()
		layout.addWidget(self._input)
		layout.setContentsMargins(0, 0, 0, 0)
		self.setLayout(layout)
		self.setFocusPolicy(NoFocus)
		self._input.setFocusPolicy(NoFocus)
		self._filter_re = re.compile('', re.I)
		self._model.add_filter(self._accepts)
		file_view.verticalScrollBar().rangeChanged.connect(
			self._on_scroll_range_changed
		)
	def handle_keypress(self, event):
		if event.key() == Key_Escape:
			self.close()
			return True
		query_before = self._input.text()
		self._input.keyPressEvent(event)
		query = self._input.text()
		result = query != query_before
		# Prevent Arrow-Left/-Right from changing the cursor position:
		self._input.setCursorPosition(len(query))
		self.setVisible(bool(query))
		if result:
			self._select_row_with_prefix(query)
		return result
	def _select_row_with_prefix(self, query):
		query_lower = query.lower()
		m = self._model
		def has_required_prefix(index):
			return m.data(index, DisplayRole).lower().startswith(query_lower)
		curr = self._file_view.currentIndex()
		if curr.isValid() and has_required_prefix(curr):
			# We're already at a row with the required prefix. Nothing to do.
			return
		for i in range(m.rowCount()):
			idx = m.index(i, 0)
			if has_required_prefix(idx):
				self._file_view.setCurrentIndex(idx)
				break
	def close(self):
		self.hide()
		self._input.setText('')
	def reposition(self, scroll_bar_visible=None):
		padding = QSize(5, 5)
		pos = self.parent().size() - self.size() - padding
		scroll_bar = self._file_view.verticalScrollBar()
		if scroll_bar_visible is None:
			scroll_bar_visible = scroll_bar.isVisible()
		if scroll_bar_visible:
			pos -= QSize(scroll_bar.width(), 0)
		self.move(pos.width(), pos.height())
	def _on_scroll_range_changed(self, min_, max_):
		self.reposition(scroll_bar_visible=min_ or max_)
	def _on_text_changed(self, text):
		text_re = '.*'.join(map(re.escape, text.split('*')))
		self._filter_re = re.compile(text_re, re.I)
		self._model.sourceModel().update()
	def _accepts(self, url):
		return bool(self._filter_re.search(basename(url)))

class PanelManager:
	"""Manages panel lifecycle for the splitter-swap pattern.

	Centralizes the activate/deactivate logic used by Settings, Theme Editor,
	and File Preview plugins. Only one panel can be active per source pane.
	Activating a new panel auto-deactivates the previous one.
	"""

	def __init__(self):
		self._active = {}
		self._in_transition = set()

	def activate(self, pane, panel_widget, panel_id):
		if pane in self._in_transition:
			return False
		panes = pane.window.get_panes()
		if len(panes) < 2:
			return False
		# Auto-deactivate any existing panel for this pane
		if pane in self._active:
			self.deactivate(pane)
		self._in_transition.add(pane)
		this_index = panes.index(pane)
		other_index = 1 - this_index
		other_pane = panes[other_index]
		target_widget = other_pane._widget
		splitter_obj = target_widget.parentWidget()
		splitter_index = splitter_obj.indexOf(target_widget)
		sizes = splitter_obj.sizes()

		target_widget.hide()
		splitter_obj.insertWidget(splitter_index, panel_widget)
		new_sizes = list(sizes)
		new_sizes.insert(splitter_index, sizes[splitter_index])
		new_sizes[splitter_index + 1] = 0
		splitter_obj.setSizes(new_sizes)

		self._active[pane] = {
			'panel_id': panel_id,
			'widget': panel_widget,
			'target_widget': target_widget,
			'splitter_sizes': sizes,
		}
		self._in_transition.discard(pane)
		return True

	def deactivate(self, pane):
		state = self._active.pop(pane, None)
		if not state:
			return None
		self._in_transition.add(pane)
		target_widget = state['target_widget']
		panel_widget = state['widget']
		splitter = panel_widget.parentWidget()
		sizes = state['splitter_sizes']
		panel_widget.hide()
		target_widget.show()
		panel_widget.setParent(None)
		panel_widget.deleteLater()
		if splitter and sizes:
			splitter.setSizes(sizes)
		self._in_transition.discard(pane)
		return state['panel_id']

	def get_active(self, pane):
		state = self._active.get(pane)
		if state:
			return state['panel_id'], state['widget']
		return None

	def is_active(self, pane, panel_id=None):
		state = self._active.get(pane)
		if not state:
			return False
		if panel_id is not None:
			return state['panel_id'] == panel_id
		return True

	def is_in_transition(self, pane):
		return pane in self._in_transition


class MainWindow(QMainWindow):

	shown = pyqtSignal()
	closed = pyqtSignal()
	before_dialog = pyqtSignal(QDialog)

	def __init__(
		self, app, help_menu_actions, theme, progress_bar_palette, fs,
		null_location
	):
		super().__init__()
		self._controller = None
		self._app = app
		self._theme = theme
		self._progress_bar_palette = progress_bar_palette
		self._fs = fs
		self._null_location = null_location
		self._panes = []
		self._panel_manager = PanelManager()
		self._splitter = Splitter(self)
		self.setCentralWidget(self._splitter)
		self._status_bar = QStatusBar(self)
		self._status_bar_text = QLabel(self._status_bar)
		self._status_bar_text.setOpenExternalLinks(True)
		self._status_bar.addWidget(self._status_bar_text)
		self._status_bar.setSizeGripEnabled(False)
		self.setStatusBar(self._status_bar)
		self._timer = QTimer(self)
		self._timer.timeout.connect(self.clear_status_message)
		self._timer.setSingleShot(True)
		self._dialog = None
		self._init_help_menu(help_menu_actions)
	def set_controller(self, controller):
		self._controller = controller
	def _init_help_menu(self, help_menu_actions):
		if not help_menu_actions:
			return
		help_menu_text = 'Help'
		if is_mac():
				# On OS X, any menu named "Help" has the "Spotlight search for
				# Help" bar displayed in it. We don't need or want this. Add an
				# invisible character to fool OS X into not treating it as
				# "Help" (' ' doesn't work):
				help_menu_text += '\u2063'
		help_menu = self.menuBar().addMenu(help_menu_text)
		actions = []
		for action_name, shortcut, handler in help_menu_actions:
			action = QAction(action_name, help_menu)
			action.triggered.connect(handler)
			help_menu.addAction(action)
			actions.append(action)
		# On at least Mac, pressing a shortcut from a menu briefly highlights
		# the menu. We don't want this - especially for the Command Palette.
		# We therefore only enable the shortcuts when the menu is open:
		def enable_shortcuts():
			for i, (_, shortcut, _) in enumerate(help_menu_actions):
				if shortcut:
					actions[i].setShortcut(QKeySequence(shortcut))
		help_menu.aboutToShow.connect(enable_shortcuts)
		def disable_shortcuts():
			for action in actions:
				action.setShortcut(QKeySequence())
		help_menu.aboutToHide.connect(disable_shortcuts)
	@run_in_main_thread
	def show_alert(
		self, text, buttons=OK, default_button=OK, allow_escape=True
	):
		alert = MessageBox(self, allow_escape)
		# API users might pass arbitrary objects as text when trying to
		# debug, eg. exception instances. Convert to str(...) to allow for
		# this:
		alert.setText(str(text))
		alert.setStandardButtons(buttons)
		alert.setDefaultButton(default_button)
		return self.exec_dialog(alert)
	@run_in_main_thread
	def show_file_open_dialog(self, caption, dir_path, filter_text):
		# Let API users pass arbitrary objects by converting with str(...):
		return QFileDialog.getOpenFileName(
			self, str(caption), str(dir_path), str(filter_text)
		)[0]
	@run_in_main_thread
	def show_prompt(
		self, text, default='', selection_start=0, selection_end=None
	):
		# Let API users pass arbitrary objects by converting str(text):
		text_str = str(text)
		dialog = Prompt(
			self, 'vitraj', text_str, default, selection_start, selection_end
		)
		dialog.setTextValue(default)
		result = self.exec_dialog(dialog)
		if result:
			return dialog.textValue(), True
		return '', False
	@run_in_main_thread
	def show_quicksearch(
		self, get_items, get_tab_completion=None, query='', item=0
	):
		css = self._theme.get_quicksearch_item_css()
		dialog = Quicksearch(
			self, self._app, css, get_items, get_tab_completion, query, item
		)
		result = self.exec_dialog(dialog)
		return result
	@run_in_main_thread
	def create_progress_dialog(self, title, task_size):
		return ProgressDialog(
			self, title, task_size, self._progress_bar_palette
		)
	@run_in_main_thread
	def exec_dialog(self, dialog):
		self._dialog = dialog
		self.before_dialog.emit(dialog)
		dialog.moveToThread(self._app.thread())
		dialog.setParent(self)
		if is_mac():
			disable_window_animations_mac(dialog)
		result = dialog.exec()
		self._dialog = None
		return result
	@run_in_main_thread
	def show_status_message(self, text, timeout_secs=None):
		self._status_bar_text.setText(text)
		if timeout_secs:
			self._timer.start(int(timeout_secs * 1000))
		else:
			self._timer.stop()
	@run_in_main_thread
	def clear_status_message(self):
		self.show_status_message('Ready.')
	@run_in_main_thread
	def add_pane(self):
		result = DirectoryPaneWidget(
			self._fs, self._null_location, self._splitter, self._controller
		)
		self._panes.append(result)
		self._splitter.addWidget(result)
		return result
	def get_panes(self):
		return self._panes
	@run_in_main_thread
	def activate_panel(self, pane, panel_widget, panel_id):
		return self._panel_manager.activate(pane, panel_widget, panel_id)
	@run_in_main_thread
	def deactivate_panel(self, pane):
		return self._panel_manager.deactivate(pane)
	def get_active_panel(self, pane):
		return self._panel_manager.get_active(pane)
	def is_panel_active(self, pane, panel_id=None):
		return self._panel_manager.is_active(pane, panel_id)
	@run_in_main_thread
	def minimize(self):
		self.setWindowState(Qt.WindowMinimized)
	def showEvent(self, *args):
		super().showEvent(*args)
		# singleShot after 50 ms (not 0) ensures that the window is already
		# fully visible. Any alerts we show in response to .shown are then
		# placed correctly over the center of the window.
		QTimer(self).singleShot(50, self.shown.emit)
	def closeEvent(self, _):
		self.closed.emit()
	@run_in_main_thread
	def show_overlay(self, overlay):
		overlay.resize(overlay.sizeHint())
		self._position_overlay(overlay)
		overlay.show()
	def _position_overlay(self, overlay):
		if self._dialog is None:
			pos_x = (self.width() - overlay.width()) / 2
			pos_y = (self.height() - overlay.height()) / 2
		else:
			dialog_pos = self._dialog.pos()
			pos_x = dialog_pos.x() - self.pos().x() + self._dialog.width() + 30
			pos_y = dialog_pos.y() - self.pos().y() + self._dialog.height() + 30
			right_margin = self.width() - pos_x - overlay.width()
			if right_margin / self.width() < 0.1:
				pos_x = 0.9 * self.width() - overlay.width()
		overlay.move(pos_x, pos_y)
	def saveState(self, version=0):
		self_state = super().saveState(version)
		splitter_state = self._splitter.saveState()
		return self_state + splitter_state + bytes([len(self_state)])
	def restoreState(self, state, version=0):
		self_state_len = state[-1]
		if not super().restoreState(state[0:self_state_len], version):
			return False
		self._splitter.restoreState(state[self_state_len:-1])
		return True
	def focusNextPrevChild(self, next):
		# Returning False here lets us receive Tab in keyPressEvent(...).
		# This in turn lets us define our own key binding for the Tab key.
		return False

class MessageBox(QMessageBox):

	shown = pyqtSignal()

	def __init__(self, parent, allow_escape=True):
		super().__init__(parent)
		self._allow_escape = allow_escape
	def setStandardButtons(self, buttons):
		super().setStandardButtons(buttons)
		if is_mac():
			# The shortcut keys don't work out of the box on Mac, even though
			# they are displayed by our theme. (The standard macOS theme does
			# not display them.) The code below ensures that they work.
			# We do have to perform these steps _here_ because self.button(...)
			# returns None when called from the constructor.
			for button, shortcut in (
				(self.Yes, Qt.Key_Y), (self.No, Qt.Key_N),
				(self.YesToAll, Qt.Key_A), (self.NoToAll, Qt.Key_O)
			):
				if buttons & button:
					self.button(button).setShortcut(
						QKeySequence(Qt.CTRL + shortcut)
					)
	def keyPressEvent(self, event):
		if self._allow_escape or event.key() != Key_Escape:
			super().keyPressEvent(event)
	def showEvent(self, event):
		super().showEvent(event)
		self.shown.emit()

class Prompt(QInputDialog):
	"""
	Most of the code in this otherwise simple class solves the following
	problem: Say we want the user to enter a file path, and we want to
	pre-select the default file's base name without the extension. The file path
	is likely too long to be contained in the text field. We want to see:

		/path/to/my/file.txt
			 |      ----   |

	where --- is the selection and |   | are the visible borders of the text
	field. Instead, by default we see:

		/path/to/my/file.txt
		  |         ----|

	In other words, "file" is highlighted but the ".txt" suffix is cut off.

	QInputDialog and thus this class use QLineEdit for text input. That class
	internally uses a `hscroll` parameter to indicate the horizontal scroll
	position which distinguishes the two figures above. The problem is,
	`hscroll` is not settable from the outside. In fact, it is only set by
	QLineEdit::paintEvent(...). We thus perform the initial paintEvent(...)
	twice: First with the cursor at the end and then with the cursor / selection
	at the correct position. This sets `hscroll` to the required value.
	"""

	shown = pyqtSignal()

	def __init__(
		self, parent, title, text, default='', selection_start=0,
		selection_end=None
	):
		super().__init__(parent)
		self.setWindowTitle(title)
		self.setLabelText(text)
		self._selection_start = selection_start
		self._selection_end = selection_end
		if default:
			self.setTextValue(default)
		self.setTextEchoMode(QLineEdit.Normal)
		self._request_immediate_repaint = False
		self._is_second_paint = False
	def setVisible(self, visible):
		"""
		Unfortunately, our double call to paintEvent(...) leads to flickering
		effects on slower systems. The super() implementation of this function
		selects the text edit's entire text. This makes the flickering effect
		especially noticeable. To alleviate this, we only place the cursor at
		the end of the text field (via .end(...)). This still has the desired
		effect of getting Qt to not cut off the rightmost characters of the text
		field, yet has less visual effect.
		"""
		if visible:
			self.labelText() # Call private ensureLayout() of the superclass
			self._get_line_edit().end(False)
			self._request_immediate_repaint = True
		QDialog.setVisible(self, visible)
	def paintEvent(self, e):
		if self._request_immediate_repaint:
			self._request_immediate_repaint = False
			# Request the second paint:
			self.update()
			self._is_second_paint = True
		elif self._is_second_paint:
			self._is_second_paint = False
			self._set_cursor_and_selection()
	def showEvent(self, event):
		super().showEvent(event)
		self.shown.emit()
	def _set_cursor_and_selection(self):
		line_edit = self._get_line_edit()
		set_selection(line_edit, self._selection_start, self._selection_end)
	def _get_line_edit(self):
		for child in self.children():
			if isinstance(child, QLineEdit):
				return child
		raise AssertionError('Should not reach here')

class Splitter(QSplitter):
	def createHandle(self):
		result = QSplitterHandle(self.orientation(), self)
		result.installEventFilter(self)
		return result
	def eventFilter(self, splitter_handle, event):
		if event.type() == QEvent.MouseButtonDblClick:
			self._distribute_handles_evenly(splitter_handle.width())
			return True
		return False
	def _distribute_handles_evenly(self, handle_width):
		width_increment = self.width() // self.count()
		for i in range(1, self.count()):
			self.moveSplitter(i * width_increment - handle_width // 2, i)

class SplashScreen(QDialog):
	def __init__(self, parent, app, license_expired, user_email):
		super().__init__(parent, Qt.CustomizeWindowHint | Qt.WindowTitleHint)
		self.app = app
		self.setWindowTitle('vitraj')

		button_texts = ('A', 'B', 'C')
		button_to_press_i = randint(0, len(button_texts) - 1)
		button_to_press = button_texts[button_to_press_i]

		layout = QVBoxLayout()
		layout.setContentsMargins(20, 20, 20, 20)

		label = QLabel(self)
		label.setText(
			self._get_label_text(button_to_press, license_expired, user_email)
		)
		label.setOpenExternalLinks(True)
		layout.addWidget(label)

		button_container = QWidget(self)
		button_layout = QHBoxLayout()
		for i, button_text in enumerate(button_texts):
			button = QPushButton(button_text, button_container)
			button.setFocusPolicy(Qt.NoFocus)
			action = self.accept if i == button_to_press_i else self.reject
			button.clicked.connect(action)
			button_layout.addWidget(button)
		button_container.setLayout(button_layout)
		layout.addWidget(button_container)

		self.setLayout(layout)
		self.finished.connect(self._finished)
	def _get_label_text(self, button_to_press, license_expired, email):
		p_style = 'line-height: 115%;'
		if is_windows():
			p_style += ' margin-left: 2px; text-indent: -2px;'
		result = \
			"<center style='line-height: 130%'>" \
				"<h2>Welcome to vitraj!</h2>" \
			"</center>"
		if license_expired:
			paragraphs = [
				'<span style="color: red;">'
					'Your license is not valid for this version of vitraj.'
				'</span>'
				'<br/>'
				'For more information, please '
				'<a href="https://fman.io/account/login?email=' + email + '">'
					'log in to fman.io'
				'</a>.',
				"To continue without a license, press button %s."
				% button_to_press
			]
		else:
			# Make buy link more enticing on (roughly) every 10th run:
			if randrange(10):
				buy_link_style = ""
			else:
				buy_link_style = " style='color: #00ff00;'"
			paragraphs = [
				"To remove this annoying popup, please "
				"<a href='https://fman.io/buy?s=f'" + buy_link_style + ">"
					"obtain a license"
				"</a>."
				"<br/>"
				"It only takes a minute and you'll never be bothered again!",
				"To continue without a license for now, press button %s."
				% button_to_press
			]
		result += ''.join(
			"<p style='" + p_style + "'>" + p + "</p>" for p in paragraphs
		)
		return result
	def keyPressEvent(self, event):
		if event.matches(QKeySequence.Quit):
			self.app.exit(0)
		else:
			event.ignore()
	def _finished(self, result):
		if result != self.Accepted:
			self.app.exit(0)

class Overlay(QFrame):
	def __init__(self, parent, html, buttons=None):
		super().__init__(parent)

		self.setFrameShape(QFrame.Box)
		self.setFrameShadow(QFrame.Raised)
		self.setFocusPolicy(Qt.NoFocus)

		layout = QVBoxLayout()
		layout.setContentsMargins(20, 20, 20, 20)

		self.label = QLabel(self)
		self.label.setWordWrap(True)
		self.label.setText(html)

		# The following two lines prevent the label from being "cut off" at the
		# bottom under some circumstances:
		layout.setSizeConstraint(layout.SetMinAndMaxSize)
		self.label.setSizePolicy(
			QSizePolicy.MinimumExpanding, QSizePolicy.Minimum
		)

		layout.addWidget(self.label)

		if buttons:
			button_container = QWidget(self)
			button_layout = QHBoxLayout()
			for button_label, action in buttons:
				button = QPushButton(button_label, button_container)
				button.clicked.connect(lambda *_, action=action: action())
				# Prevent button from stealing focus from the directory pane:
				button.setFocusPolicy(Qt.NoFocus)
				button_layout.addWidget(button)
			button_container.setLayout(button_layout)
			layout.addWidget(button_container)

		self.setLayout(layout)
	def close(self):
		self.setParent(None)

class ProgressDialog(QProgressDialog):

	"""
	Instead of using @run_in_main_thread on #set_text(...) and
	#set_progress(...), this class uses #_update_timer to only update the GUI
	every 100ms. This avoids the unnecessary overhead of syncing with the main
	thread for every status update, and thus improves performance.
	"""

	_MAX_C_INT = 2147483647
	_MINIMUM_DURATION_MS = 1000
	_UPDATE_INTERVAL_MS = 100

	@run_in_main_thread
	def __init__(self, parent, title, size, progress_bar_palette):
		# Would like the dialog to be non-resizable on all platforms, but only
		# Windows supports it as a flag. On other platforms, we use
		# setFixedSize(...). See #resizeEvent(...) below.
		args = (Qt.MSWindowsFixedSizeDialogHint,) if is_windows() else ()
		super().__init__(parent, *args)
		self._title = title
		self._size = self.maximum()
		self._text = ''
		self._progress = 0
		self._was_canceled = False
		self.findChild(QProgressBar).setPalette(progress_bar_palette)
		self.setMinimumDuration(self._MINIMUM_DURATION_MS)
		self.setAutoReset(False)
		self.setWindowTitle(title)
		self.set_task_size(size)
		self.canceled.disconnect(super().cancel)
		self.canceled.connect(self.request_cancel)
		self._update_timer = QTimer(self)
		self._update_timer.timeout.connect(self._update)
		# Ensure the progress dialog appears in 1 sec starting *now*:
		self.setValue(0)
	def set_text(self, text):
		self._text = text
	@run_in_main_thread
	def set_task_size(self, size):
		self._size = size
		self.setMaximum(min(size, self._MAX_C_INT))
	def set_progress(self, progress):
		self._progress = progress
	def get_progress(self):
		return self._progress
	def reject(self):
		# Called when the user presses the "Close window" button.
		self.request_cancel()
	@run_in_main_thread
	def cancel(self):
		super().cancel()
	@run_in_main_thread
	def request_cancel(self):
		self.set_text('Canceling...')
		cancel_button = self.findChild(QPushButton)
		cancel_button.setEnabled(False)
		self._was_canceled = True
	@run_in_main_thread
	def show_alert(self, *args, **kwargs):
		# Prevent the progress dialog from popping up while the alert is shown:
		self.setMinimumDuration(self._MAX_C_INT)
		try:
			return self.parent().show_alert(*args, **kwargs)
		finally:
			self.setMinimumDuration(self._MINIMUM_DURATION_MS)
	def was_canceled(self):
		return self._was_canceled
	def showEvent(self, e):
		self._update()
		self._update_timer.start(self._UPDATE_INTERVAL_MS)
		super().showEvent(e)
	def closeEvent(self, e):
		self._update_timer.stop()
		super().closeEvent(e)
	def resizeEvent(self, e):
		super().resizeEvent(e)
		# Prevent the dialog from being resizable:
		if not is_windows():
			self.setFixedSize(self.size())
	def _update(self):
		if self.wasCanceled():
			return
		self.setLabelText(self._text)
		self._set_value(self._progress)
	def _set_value(self, progress):
		if self._size > self._MAX_C_INT:
			# QProgressDialog#setValue(...) can only handle ints. If `progress`
			# is too large, we need to scale it down. If we didn't do this and
			# pass a larger number, it would overflow to a negative value.
			progress = self._MAX_C_INT * progress // self._size
		self.setValue(progress)