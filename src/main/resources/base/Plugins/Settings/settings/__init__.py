from vitraj import DirectoryPaneCommand, DirectoryPaneListener, load_json, \
	save_json, show_status_message, PLATFORM
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, \
	QScrollArea, QSizePolicy, QFrame, QPushButton, QCheckBox, \
	QSpinBox, QLineEdit, QFileDialog

import os


_SETTINGS_SYNC_COMMANDS = frozenset(('toggle_hidden_files',
									  'toggle_parent_dir_entry'))
_CORE_SETTINGS_JSON = 'Core Settings.json'
_SETTINGS_JSON = 'Settings.json'
_PANES_JSON = 'Panes.json'

_TOOLS = [
	('editor', 'Editor', 'Not configured', ['{file}']),
	('terminal', 'Terminal', 'System default', ['{curr_dir}']),
	('native_file_manager', 'File manager', 'System default', ['{curr_dir}']),
]


def _set_checkbox_silent(cb, value):
	cb.blockSignals(True)
	cb.setChecked(value)
	cb.blockSignals(False)


class SettingsPanel(QWidget):

	def __init__(self, pane, parent=None):
		super().__init__(parent)
		self._pane = pane
		self._save_timer = QTimer(self)
		self._save_timer.setSingleShot(True)
		self._save_timer.setInterval(500)
		self._save_timer.timeout.connect(self._flush_font_size)
		self._pending_font_size = None
		self._tool_inputs = {}
		self._init_ui()

	def _init_ui(self):
		self.setMinimumWidth(0)
		self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

		outer = QVBoxLayout()
		outer.setContentsMargins(0, 0, 0, 0)
		outer.setSpacing(0)

		header = QLabel('Settings')
		header.setStyleSheet(
			'QLabel { padding: 8px 12px; font-weight: bold; font-size: 14px; '
			'color: white; }'
		)
		outer.addWidget(header)

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
		_set_checkbox_silent(
			self._hidden_files_cb,
			pane_info.get('show_hidden_files', False)
		)
		_set_checkbox_silent(
			self._parent_dir_cb,
			pane_info.get('show_parent_dir_entry', False)
		)

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

	def _build_display_section(self):
		self._add_section_header('Display')

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

	def _build_tools_section(self):
		self._add_section_header('External Tools')
		settings = load_json(_CORE_SETTINGS_JSON, default={})

		for key, label, placeholder, _extra_args in _TOOLS:
			args = settings.get(key, {}).get('args', [])
			row = QHBoxLayout()
			row.addWidget(QLabel(label))
			inp = QLineEdit()
			inp.setPlaceholderText(placeholder)
			inp.setText(_get_tool_display_name(args))
			inp.setReadOnly(True)
			row.addWidget(inp)
			browse_btn = QPushButton('Browse...')
			browse_btn.setFixedWidth(80)
			browse_btn.clicked.connect(
				lambda _checked=False, k=key: self._on_browse_tool(k)
			)
			row.addWidget(browse_btn)
			self._layout.addLayout(row)
			self._tool_inputs[key] = inp

		self._add_separator()

	# --- Handlers ---

	def _on_edit_theme(self):
		_close_settings(self._pane)
		self._pane.run_command('edit_theme')

	def _on_hidden_files_toggled(self, _checked):
		self._pane.run_command('toggle_hidden_files')
		pane_info = _get_pane_info(self._pane)
		_set_checkbox_silent(
			self._hidden_files_cb,
			pane_info.get('show_hidden_files', False)
		)

	def _on_parent_dir_toggled(self, _checked):
		self._pane.run_command('toggle_parent_dir_entry')
		pane_info = _get_pane_info(self._pane)
		_set_checkbox_silent(
			self._parent_dir_cb,
			pane_info.get('show_parent_dir_entry', False)
		)

	def _get_font_size(self):
		user_settings = load_json(_SETTINGS_JSON, default={})
		return user_settings.get('font_size', _get_default_font_size())

	def _on_font_size_changed(self, value):
		self._pending_font_size = value
		_apply_font_size(value)
		self._save_timer.start()

	def _flush_font_size(self):
		if self._pending_font_size is not None:
			user_settings = load_json(_SETTINGS_JSON, default={})
			user_settings['font_size'] = self._pending_font_size
			save_json(_SETTINGS_JSON)
			self._pending_font_size = None

	def _on_browse_tool(self, key):
		tool_def = next(t for t in _TOOLS if t[0] == key)
		_, label, _, extra_args = tool_def
		path = self._browse_for_app('Select %s' % label)
		if path:
			self._tool_inputs[key].setText(_friendly_app_name(path))
			self._save_tool_setting(key, path, extra_args)

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
		settings = load_json(_CORE_SETTINGS_JSON, default={})
		if PLATFORM == 'Mac':
			args = ['/usr/bin/open', '-a', app_path] + extra_args
		else:
			args = [app_path] + extra_args
		settings[key] = {'args': args}
		save_json(_CORE_SETTINGS_JSON)
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
	settings = load_json(_PANES_JSON, default=[])
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


def _friendly_app_name(path):
	name = os.path.basename(path)
	if name.endswith('.app'):
		name = name[:-4]
	return name or path


# --- Commands and Listeners ---

_PANEL_ID = 'settings'


class OpenSettings(DirectoryPaneCommand):

	aliases = ('Settings', 'Preferences', 'Open settings')

	def __call__(self):
		w = self.pane.window
		if w.is_panel_active(self.pane, _PANEL_ID):
			_close_settings(self.pane)
		else:
			panel = SettingsPanel(self.pane)
			w.activate_panel(self.pane, panel, _PANEL_ID)

	def is_visible(self):
		return len(self.pane.window.get_panes()) >= 2


class CloseSettings(DirectoryPaneCommand):

	aliases = ('Close settings',)

	def __call__(self):
		_close_settings(self.pane)

	def is_visible(self):
		return self.pane.window.is_panel_active(self.pane, _PANEL_ID)


class InitSettingsListener(DirectoryPaneListener):
	_applied = False

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		if not InitSettingsListener._applied:
			InitSettingsListener._applied = True
			user_settings = load_json(_SETTINGS_JSON, default={})
			font_size = user_settings.get('font_size')
			if font_size is not None:
				_apply_font_size(font_size)


class SettingsSyncListener(DirectoryPaneListener):
	def on_command(self, command_name, args):
		if command_name in _SETTINGS_SYNC_COMMANDS:
			active = self.pane.window.get_active_panel(self.pane)
			if active and active[0] == _PANEL_ID:
				active[1].refresh()
		return None


def _close_settings(pane):
	active = pane.window.get_active_panel(pane)
	if active and active[0] == _PANEL_ID:
		panel = active[1]
		if panel._save_timer.isActive():
			panel._save_timer.stop()
			panel._flush_font_size()
		pane.window.deactivate_panel(pane)
