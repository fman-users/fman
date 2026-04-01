from fman import DirectoryPaneCommand, DirectoryPaneListener, load_json, \
	save_json, show_status_message, PLATFORM
from fman.impl.util.qt.thread import run_in_main_thread
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, \
	QScrollArea, QSizePolicy, QFrame, QPushButton, QCheckBox, \
	QSpinBox, QLineEdit, QFileDialog

import os


_SETTINGS_EXIT_COMMANDS = frozenset(('switch_panes', 'go_to'))


# --- Settings Panel Widget ---

class SettingsPanel(QWidget):

	def __init__(self, pane, parent=None):
		super().__init__(parent)
		self._pane = pane
		self._save_timer = QTimer(self)
		self._save_timer.setSingleShot(True)
		self._save_timer.setInterval(500)
		self._save_timer.timeout.connect(self._flush_font_size)
		self._pending_font_size = None
		self._init_ui()

	def _init_ui(self):
		self.setMinimumWidth(0)
		self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

		outer = QVBoxLayout()
		outer.setContentsMargins(0, 0, 0, 0)
		outer.setSpacing(0)

		# Header
		header = QLabel('Settings')
		header.setStyleSheet(
			'QLabel { padding: 8px 12px; font-weight: bold; font-size: 14px; '
			'color: white; }'
		)
		outer.addWidget(header)

		# Scrollable content
		scroll = QScrollArea()
		scroll.setWidgetResizable(True)
		scroll.setFrameShape(QFrame.NoFrame)
		scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

		content = QWidget()
		self._layout = QVBoxLayout()
		self._layout.setContentsMargins(12, 8, 12, 12)
		self._layout.setSpacing(6)

		self._build_display_section()
		self._build_file_list_section()
		self._build_tools_section()

		self._layout.addStretch()
		content.setLayout(self._layout)
		scroll.setWidget(content)
		outer.addWidget(scroll)
		self.setLayout(outer)

	def refresh(self):
		pane_info = _get_pane_info(self._pane)
		self._hidden_files_cb.blockSignals(True)
		self._hidden_files_cb.setChecked(
			pane_info.get('show_hidden_files', False)
		)
		self._hidden_files_cb.blockSignals(False)
		self._parent_dir_cb.blockSignals(True)
		self._parent_dir_cb.setChecked(
			pane_info.get('show_parent_dir_entry', False)
		)
		self._parent_dir_cb.blockSignals(False)

	def _add_section_header(self, title):
		label = QLabel(title)
		label.setStyleSheet(
			'QLabel { color: #a6e22e; font-weight: bold; font-size: 12px; '
			'padding-top: 10px; padding-bottom: 4px; }'
		)
		self._layout.addWidget(label)

	def _add_separator(self):
		line = QFrame()
		line.setFrameShape(QFrame.HLine)
		line.setFrameShadow(QFrame.Sunken)
		line.setStyleSheet('QFrame { color: #3e3e3e; }')
		self._layout.addWidget(line)

	# --- Display section ---

	def _build_display_section(self):
		self._add_section_header('Display')

		# Font size
		row = QHBoxLayout()
		row.addWidget(QLabel('Font size'))
		row.addStretch()
		self._font_size_spin = QSpinBox()
		self._font_size_spin.setRange(8, 48)
		self._font_size_spin.setSuffix(' pt')
		self._font_size_spin.setValue(self._get_font_size())
		self._font_size_spin.setFixedWidth(80)
		self._font_size_spin.valueChanged.connect(self._on_font_size_changed)
		row.addWidget(self._font_size_spin)
		self._layout.addLayout(row)

		# Theme
		row = QHBoxLayout()
		row.addWidget(QLabel('Theme'))
		row.addStretch()
		theme_label = QLabel('Dark (built-in)')
		theme_label.setStyleSheet('QLabel { color: #666; }')
		row.addWidget(theme_label)
		edit_theme_btn = QPushButton('Edit...')
		edit_theme_btn.setFixedWidth(60)
		edit_theme_btn.clicked.connect(self._on_edit_theme)
		row.addWidget(edit_theme_btn)
		self._layout.addLayout(row)

		self._add_separator()

	# --- File list section ---

	def _build_file_list_section(self):
		self._add_section_header('File List')

		pane_info = _get_pane_info(self._pane)

		self._hidden_files_cb = QCheckBox('Show hidden files')
		self._hidden_files_cb.setChecked(
			pane_info.get('show_hidden_files', False)
		)
		self._hidden_files_cb.toggled.connect(self._on_hidden_files_toggled)
		self._layout.addWidget(self._hidden_files_cb)

		self._parent_dir_cb = QCheckBox('Show ".." parent directory entry')
		self._parent_dir_cb.setChecked(
			pane_info.get('show_parent_dir_entry', False)
		)
		self._parent_dir_cb.toggled.connect(self._on_parent_dir_toggled)
		self._layout.addWidget(self._parent_dir_cb)

		self._add_separator()

	# --- Tools section ---

	def _build_tools_section(self):
		self._add_section_header('External Tools')
		settings = load_json('Core Settings.json', default={})

		# Editor
		editor_args = settings.get('editor', {}).get('args', [])
		row = QHBoxLayout()
		row.addWidget(QLabel('Editor'))
		self._editor_input = QLineEdit()
		self._editor_input.setPlaceholderText('Not configured')
		self._editor_input.setText(_get_tool_display_name(editor_args))
		self._editor_input.setReadOnly(True)
		row.addWidget(self._editor_input)
		browse_btn = QPushButton('Browse...')
		browse_btn.setFixedWidth(80)
		browse_btn.clicked.connect(self._on_browse_editor)
		row.addWidget(browse_btn)
		self._layout.addLayout(row)

		# Terminal
		terminal_args = settings.get('terminal', {}).get('args', [])
		row = QHBoxLayout()
		row.addWidget(QLabel('Terminal'))
		self._terminal_input = QLineEdit()
		self._terminal_input.setPlaceholderText('System default')
		self._terminal_input.setText(_get_tool_display_name(terminal_args))
		self._terminal_input.setReadOnly(True)
		row.addWidget(self._terminal_input)
		browse_btn = QPushButton('Browse...')
		browse_btn.setFixedWidth(80)
		browse_btn.clicked.connect(self._on_browse_terminal)
		row.addWidget(browse_btn)
		self._layout.addLayout(row)

		# Native file manager
		fm_args = settings.get('native_file_manager', {}).get('args', [])
		row = QHBoxLayout()
		row.addWidget(QLabel('File manager'))
		self._fm_input = QLineEdit()
		self._fm_input.setPlaceholderText('System default')
		self._fm_input.setText(_get_tool_display_name(fm_args))
		self._fm_input.setReadOnly(True)
		row.addWidget(self._fm_input)
		browse_btn = QPushButton('Browse...')
		browse_btn.setFixedWidth(80)
		browse_btn.clicked.connect(self._on_browse_file_manager)
		row.addWidget(browse_btn)
		self._layout.addLayout(row)

		self._add_separator()

	# --- Handlers ---

	def _on_edit_theme(self):
		# Close settings and open theme editor
		if self._pane in _active_settings:
			_deactivate_settings(self._pane)
		self._pane.run_command('edit_theme')

	def _on_hidden_files_toggled(self, _checked):
		self._pane.run_command('toggle_hidden_files')
		# Re-read actual state and sync checkbox (blocks signal to avoid loop)
		pane_info = _get_pane_info(self._pane)
		self._hidden_files_cb.blockSignals(True)
		self._hidden_files_cb.setChecked(
			pane_info.get('show_hidden_files', False)
		)
		self._hidden_files_cb.blockSignals(False)

	def _on_parent_dir_toggled(self, _checked):
		self._pane.run_command('toggle_parent_dir_entry')
		pane_info = _get_pane_info(self._pane)
		self._parent_dir_cb.blockSignals(True)
		self._parent_dir_cb.setChecked(
			pane_info.get('show_parent_dir_entry', False)
		)
		self._parent_dir_cb.blockSignals(False)

	def _get_font_size(self):
		user_settings = load_json('Settings.json', default={})
		return user_settings.get('font_size', _get_default_font_size())

	def _on_font_size_changed(self, value):
		self._pending_font_size = value
		_apply_font_size(value)
		self._save_timer.start()

	def _flush_font_size(self):
		if self._pending_font_size is not None:
			user_settings = load_json('Settings.json', default={})
			user_settings['font_size'] = self._pending_font_size
			save_json('Settings.json')
			self._pending_font_size = None

	def _on_browse_editor(self):
		path = self._browse_for_app('Select Editor')
		if path:
			self._editor_input.setText(_get_tool_display_name_from_path(path))
			self._save_tool_setting('editor', path, ['{file}'])

	def _on_browse_terminal(self):
		path = self._browse_for_app('Select Terminal')
		if path:
			self._terminal_input.setText(_get_tool_display_name_from_path(path))
			self._save_tool_setting('terminal', path, ['{curr_dir}'])

	def _on_browse_file_manager(self):
		path = self._browse_for_app('Select File Manager')
		if path:
			self._fm_input.setText(_get_tool_display_name_from_path(path))
			self._save_tool_setting('native_file_manager', path, ['{curr_dir}'])

	def _browse_for_app(self, caption):
		if PLATFORM == 'Mac':
			start_dir = '/Applications'
		elif PLATFORM == 'Windows':
			start_dir = os.environ.get('PROGRAMFILES', 'C:\\Program Files')
		else:
			start_dir = '/usr/bin'
		path, _ = QFileDialog.getOpenFileName(self, caption, start_dir)
		return path

	def _save_tool_setting(self, key, app_path, extra_args):
		settings = load_json('Core Settings.json', default={})
		if PLATFORM == 'Mac':
			args = ['/usr/bin/open', '-a', app_path] + extra_args
		else:
			args = [app_path] + extra_args
		settings[key] = {'args': args}
		save_json('Core Settings.json')
		show_status_message('%s updated.' % key.replace('_', ' ').title(), 3)


def _get_default_font_size():
	return 13 if PLATFORM == 'Mac' else 9


def _apply_font_size(size_pt):
	from PyQt5.QtWidgets import QApplication
	app = QApplication.instance()
	if app is None:
		return
	font = app.font()
	font.setPointSize(size_pt)
	app.setFont(font)


def _get_pane_info(pane):
	settings = load_json('Panes.json', default=[])
	default = {'show_hidden_files': False, 'show_parent_dir_entry': False}
	pane_index = pane.window.get_panes().index(pane)
	for _ in range(pane_index - len(settings) + 1):
		settings.append(default.copy())
	return settings[pane_index]


def _get_tool_display_name(args):
	if not args:
		return ''
	if PLATFORM == 'Mac' and len(args) >= 3 and args[1] == '-a':
		return _friendly_app_name(args[2])
	return args[0]


def _get_tool_display_name_from_path(path):
	return _friendly_app_name(path)


def _friendly_app_name(path):
	name = os.path.basename(path)
	if name.endswith('.app'):
		name = name[:-4]
	return name or path


# --- Commands and Listeners ---

_active_settings = {}
_settings_in_transition = set()


class OpenSettings(DirectoryPaneCommand):

	aliases = ('Settings', 'Preferences', 'Open settings')

	def __call__(self):
		if self.pane in _settings_in_transition:
			return
		if self.pane in _active_settings:
			_deactivate_settings(self.pane)
		else:
			# Close preview if active on this pane before opening settings
			try:
				from file_preview import _active_previews, _deactivate_preview
				if self.pane in _active_previews:
					_deactivate_preview(self.pane)
			except ImportError:
				pass
			_activate_settings(self.pane)

	def is_visible(self):
		return len(self.pane.window.get_panes()) >= 2


class CloseSettings(DirectoryPaneCommand):

	aliases = ('Close settings',)

	def __call__(self):
		if self.pane in _active_settings:
			_deactivate_settings(self.pane)

	def is_visible(self):
		return self.pane in _active_settings


class InitSettingsListener(DirectoryPaneListener):
	_font_applied = False

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		if not InitSettingsListener._font_applied:
			InitSettingsListener._font_applied = True
			user_settings = load_json('Settings.json', default={})
			font_size = user_settings.get('font_size')
			if font_size is not None:
				_apply_font_size(font_size)


class SettingsModeListener(DirectoryPaneListener):
	def on_command(self, command_name, args):
		if self.pane in _active_settings:
			if command_name in _SETTINGS_EXIT_COMMANDS:
				_deactivate_settings(self.pane)
			elif command_name in ('toggle_hidden_files',
								  'toggle_parent_dir_entry'):
				# External toggle (keyboard shortcut) -- sync checkboxes
				state = _active_settings.get(self.pane)
				if state:
					state['panel'].refresh()
		return None


def _activate_settings(pane):
	panes = pane.window.get_panes()
	if len(panes) < 2:
		return
	_settings_in_transition.add(pane)
	this_index = panes.index(pane)
	other_index = 1 - this_index
	other_pane = panes[other_index]
	target_widget = other_pane._widget

	@run_in_main_thread
	def _do_activate():
		splitter = target_widget.parentWidget()
		splitter_index = splitter.indexOf(target_widget)
		sizes = splitter.sizes()

		panel = SettingsPanel(pane)
		target_widget.hide()
		splitter.insertWidget(splitter_index, panel)
		new_sizes = list(sizes)
		new_sizes.insert(splitter_index, sizes[splitter_index])
		new_sizes[splitter_index + 1] = 0
		splitter.setSizes(new_sizes)

		_active_settings[pane] = {
			'panel': panel,
			'target_widget': target_widget,
			'splitter_sizes': sizes,
		}
		_settings_in_transition.discard(pane)

	_do_activate()


def _deactivate_settings(pane):
	state = _active_settings.pop(pane, None)
	if not state:
		return
	_settings_in_transition.add(pane)
	# Flush any pending font size save
	panel = state['panel']
	if panel._save_timer.isActive():
		panel._save_timer.stop()
		panel._flush_font_size()

	@run_in_main_thread
	def _do_deactivate():
		target_widget = state['target_widget']
		splitter = panel.parentWidget()
		sizes = state['splitter_sizes']
		panel.hide()
		target_widget.show()
		panel.setParent(None)
		panel.deleteLater()
		if splitter and sizes:
			splitter.setSizes(sizes)
		_settings_in_transition.discard(pane)

	_do_deactivate()
