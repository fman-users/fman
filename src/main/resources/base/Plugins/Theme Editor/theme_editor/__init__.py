"""
Theme Editor - visual theme customization for fman.

Extends the Settings plugin with a theme editor sub-panel. Opens from
the Settings panel or via Command Palette ("Edit theme").
Uses color pickers to style all themeable elements with live preview.
"""
from fman import DirectoryPaneCommand, DirectoryPaneListener, load_json, \
	save_json, show_status_message
from fman.impl.util.qt.thread import run_in_main_thread
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, \
	QScrollArea, QSizePolicy, QFrame, QPushButton, QColorDialog, \
	QApplication

# The themeable elements and their default colors (from styles.qss + palette)
_THEME_ELEMENTS = [
	{
		'group': 'Background',
		'items': [
			('window_bg', 'Window', '#2b2b2b'),
			('base_bg', 'File list', '#272822'),
			('header_bg_top', 'Column header (top)', '#363731'),
			('header_bg_bottom', 'Column header (bottom)', '#272822'),
			('status_bar_bg_top', 'Status bar (top)', '#5b5b5b'),
			('status_bar_bg_bottom', 'Status bar (bottom)', '#545454'),
			('location_bar_border', 'Location bar border', '#262626'),
		]
	},
	{
		'group': 'Text',
		'items': [
			('text_primary', 'Primary text', '#ffffff'),
			('text_secondary', 'File info / labels', '#8f908a'),
			('text_dirs', 'Directory names', '#ffffff'),
			('text_header', 'Column headers', '#8f908a'),
			('text_status', 'Status bar', '#ffffff'),
			('text_location', 'Location bar', '#9a9a9a'),
		]
	},
	{
		'group': 'Selection & Focus',
		'items': [
			('selected_color', 'Selected file text', '#f92672'),
			('cursor_bg', 'Cursor row', '#49483e'),
			('status_bar_border', 'Status bar top border', '#7d7d7d'),
		]
	},
	{
		'group': 'Input & Dialogs',
		'items': [
			('input_bg', 'Text input background', '#303030'),
			('input_border', 'Text input border', '#363731'),
			('input_text', 'Text input text', '#ffffff'),
			('quicksearch_bg', 'Quick search background', '#404040'),
			('quicksearch_input_bg', 'Quick search input', '#e6e6e6'),
			('quicksearch_input_text', 'Quick search input text', '#1d1d1d'),
			('quicksearch_selected', 'Quick search selected', '#575757'),
		]
	},
]

_DEFAULTS = {}
for _group in _THEME_ELEMENTS:
	for _key, _label, _default in _group['items']:
		_DEFAULTS[_key] = _default


def _load_custom_theme():
	return load_json('Custom Theme.json', default={})


def _save_custom_theme(theme):
	save_json('Custom Theme.json')


class ColorButton(QPushButton):
	"""A button that shows a color swatch and opens a color picker."""

	def __init__(self, key, color, on_changed, parent=None):
		super().__init__(parent)
		self._key = key
		self._color = QColor(color)
		self._on_changed = on_changed
		self.setFixedSize(QSize(32, 22))
		self.setCursor(Qt.PointingHandCursor)
		self._update_style()
		self.clicked.connect(self._pick_color)

	def set_color(self, color):
		self._color = QColor(color)
		self._update_style()

	def _update_style(self):
		self.setStyleSheet(
			'QPushButton { background-color: %s; border: 1px solid #666; '
			'border-radius: 2px; }'
			'QPushButton:hover { border-color: white; }'
			% self._color.name()
		)

	def _pick_color(self):
		color = QColorDialog.getColor(
			self._color, self, 'Choose color',
			QColorDialog.ShowAlphaChannel
		)
		if color.isValid():
			self._color = color
			self._update_style()
			self._on_changed(self._key, color.name())


class ThemePreview(QFrame):
	"""A mini preview showing how theme colors look together."""

	def __init__(self, parent=None):
		super().__init__(parent)
		self.setFrameShape(QFrame.Box)
		self.setFixedHeight(140)
		self._colors = dict(_DEFAULTS)
		self._build_ui()

	def _build_ui(self):
		self._layout = QVBoxLayout()
		self._layout.setContentsMargins(0, 0, 0, 0)
		self._layout.setSpacing(0)

		# Location bar
		self._loc_bar = QLabel('/Users/demo/Documents')
		self._loc_bar.setFixedHeight(22)
		self._layout.addWidget(self._loc_bar)

		# Header row
		self._header = QLabel('  Name                         Size       Modified')
		self._header.setFixedHeight(20)
		self._layout.addWidget(self._header)

		# File rows
		self._rows_widget = QWidget()
		rows_layout = QVBoxLayout()
		rows_layout.setContentsMargins(0, 0, 0, 0)
		rows_layout.setSpacing(0)

		self._row_labels = []
		row_data = [
			('  Documents/', True, False, False),
			('  Downloads/', True, False, False),
			('  notes.txt', False, True, False),
			('  photo.jpg', False, False, True),
			('  README.md', False, False, False),
		]
		for text, is_dir, is_selected, is_cursor in row_data:
			label = QLabel(text)
			label.setFixedHeight(18)
			self._row_labels.append((label, is_dir, is_selected, is_cursor))
			rows_layout.addWidget(label)

		self._rows_widget.setLayout(rows_layout)
		self._layout.addWidget(self._rows_widget)

		# Status bar
		self._status = QLabel('  5 items  |  Ready.')
		self._status.setFixedHeight(20)
		self._layout.addWidget(self._status)

		self.setLayout(self._layout)

	def update_colors(self, colors):
		self._colors = colors
		c = colors

		# Location bar
		self._loc_bar.setStyleSheet(
			'QLabel { background-color: %s; color: %s; padding-left: 4px; '
			'font-size: 10px; border-bottom: 1px solid %s; }' % (
				c.get('window_bg', _DEFAULTS['window_bg']),
				c.get('text_location', _DEFAULTS['text_location']),
				c.get('location_bar_border', _DEFAULTS['location_bar_border']),
			)
		)

		# Header
		self._header.setStyleSheet(
			'QLabel { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,'
			'stop:0 %s, stop:1 %s); color: %s; font-size: 9px; }' % (
				c.get('header_bg_top', _DEFAULTS['header_bg_top']),
				c.get('header_bg_bottom', _DEFAULTS['header_bg_bottom']),
				c.get('text_header', _DEFAULTS['text_header']),
			)
		)

		# Rows
		base_bg = c.get('base_bg', _DEFAULTS['base_bg'])
		cursor_bg = c.get('cursor_bg', _DEFAULTS['cursor_bg'])
		text_dirs = c.get('text_dirs', _DEFAULTS['text_dirs'])
		text_secondary = c.get('text_secondary', _DEFAULTS['text_secondary'])
		selected_color = c.get('selected_color', _DEFAULTS['selected_color'])

		self._rows_widget.setStyleSheet(
			'QWidget { background-color: %s; }' % base_bg
		)

		for label, is_dir, is_selected, is_cursor in self._row_labels:
			bg = cursor_bg if is_cursor else base_bg
			if is_selected:
				fg = selected_color
			elif is_dir:
				fg = text_dirs
			else:
				fg = text_secondary
			label.setStyleSheet(
				'QLabel { background-color: %s; color: %s; '
				'font-size: 10px; padding-left: 4px; }' % (bg, fg)
			)

		# Status bar
		self._status.setStyleSheet(
			'QLabel { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,'
			'stop:0 %s, stop:1 %s); color: %s; font-size: 9px; '
			'border-top: 1px solid %s; }' % (
				c.get('status_bar_bg_top', _DEFAULTS['status_bar_bg_top']),
				c.get('status_bar_bg_bottom', _DEFAULTS['status_bar_bg_bottom']),
				c.get('text_status', _DEFAULTS['text_status']),
				c.get('status_bar_border', _DEFAULTS['status_bar_border']),
			)
		)

		self.setStyleSheet(
			'ThemePreview { border: 1px solid #555; background-color: %s; }'
			% base_bg
		)


class ThemeEditorPanel(QWidget):
	"""The main theme editor panel with color pickers and live preview."""

	def __init__(self, pane, parent=None):
		super().__init__(parent)
		self._pane = pane
		self._colors = dict(_DEFAULTS)
		custom = _load_custom_theme()
		self._colors.update(custom)
		self._init_ui()

	def _init_ui(self):
		self.setMinimumWidth(0)
		self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

		outer = QVBoxLayout()
		outer.setContentsMargins(0, 0, 0, 0)
		outer.setSpacing(0)

		# Header with back button
		header_row = QHBoxLayout()
		header_row.setContentsMargins(8, 6, 8, 6)
		back_btn = QPushButton('\u2190 Back')
		back_btn.setFixedWidth(60)
		back_btn.setStyleSheet(
			'QPushButton { color: #a6e22e; background: transparent; '
			'border: none; font-size: 11px; text-align: left; }'
			'QPushButton:hover { color: white; }'
		)
		back_btn.clicked.connect(self._go_back)
		header_row.addWidget(back_btn)
		title = QLabel('Theme Editor')
		title.setStyleSheet(
			'QLabel { font-weight: bold; font-size: 14px; color: white; }'
		)
		header_row.addWidget(title)
		header_row.addStretch()
		outer.addLayout(header_row)

		# Preview
		self._preview = ThemePreview()
		self._preview.update_colors(self._colors)
		outer.addWidget(self._preview)

		# Scrollable color pickers
		scroll = QScrollArea()
		scroll.setWidgetResizable(True)
		scroll.setFrameShape(QFrame.NoFrame)
		scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

		content = QWidget()
		self._grid_layout = QVBoxLayout()
		self._grid_layout.setContentsMargins(8, 4, 8, 8)
		self._grid_layout.setSpacing(4)

		self._color_buttons = {}

		for group in _THEME_ELEMENTS:
			group_label = QLabel(group['group'])
			group_label.setStyleSheet(
				'QLabel { color: #a6e22e; font-weight: bold; font-size: 11px; '
				'padding-top: 8px; padding-bottom: 2px; }'
			)
			self._grid_layout.addWidget(group_label)

			for key, label, default in group['items']:
				row = QHBoxLayout()
				row.setSpacing(8)

				lbl = QLabel(label)
				lbl.setStyleSheet('QLabel { font-size: 11px; }')
				row.addWidget(lbl)
				row.addStretch()

				color_val = self._colors.get(key, default)
				btn = ColorButton(key, color_val, self._on_color_changed)
				self._color_buttons[key] = btn
				row.addWidget(btn)

				self._grid_layout.addLayout(row)

		# Action buttons
		self._grid_layout.addSpacing(12)
		btn_row = QHBoxLayout()

		apply_btn = QPushButton('Apply to App')
		apply_btn.setStyleSheet(
			'QPushButton { background-color: #a6e22e; color: #272822; '
			'font-weight: bold; padding: 6px 12px; border: none; '
			'border-radius: 3px; }'
			'QPushButton:hover { background-color: #b8f330; }'
		)
		apply_btn.clicked.connect(self._apply_theme)
		btn_row.addWidget(apply_btn)

		reset_btn = QPushButton('Reset to Default')
		reset_btn.setStyleSheet(
			'QPushButton { padding: 6px 12px; border: 1px solid #666; '
			'border-radius: 3px; }'
			'QPushButton:hover { border-color: white; }'
		)
		reset_btn.clicked.connect(self._reset_theme)
		btn_row.addWidget(reset_btn)

		self._grid_layout.addLayout(btn_row)
		self._grid_layout.addStretch()

		content.setLayout(self._grid_layout)
		scroll.setWidget(content)
		outer.addWidget(scroll)
		self.setLayout(outer)

	def _on_color_changed(self, key, hex_color):
		self._colors[key] = hex_color
		self._preview.update_colors(self._colors)

	def _apply_theme(self):
		# Save custom colors (only those that differ from defaults)
		custom = {}
		for key, val in self._colors.items():
			if val != _DEFAULTS.get(key):
				custom[key] = val

		theme_data = _load_custom_theme()
		theme_data.clear()
		theme_data.update(custom)
		_save_custom_theme(theme_data)

		_apply_theme_to_app(self._colors)
		show_status_message('Theme applied.', 3)

	def _reset_theme(self):
		self._colors = dict(_DEFAULTS)
		for key, btn in self._color_buttons.items():
			btn.set_color(_DEFAULTS[key])
		self._preview.update_colors(self._colors)

		theme_data = _load_custom_theme()
		theme_data.clear()
		_save_custom_theme(theme_data)

		_apply_theme_to_app(self._colors)
		show_status_message('Theme reset to default.', 3)

	def _go_back(self):
		# Close theme editor and reopen settings
		if self._pane in _active_theme_editors:
			_deactivate_theme_editor(self._pane)
			self._pane.run_command('open_settings')


def _apply_theme_to_app(colors):
	"""Apply the custom color scheme to the running application."""
	app = QApplication.instance()
	if app is None:
		return

	c = colors

	# Update QPalette
	palette = app.palette()
	palette.setColor(QPalette.Window, QColor(c.get('window_bg', _DEFAULTS['window_bg'])))
	palette.setColor(QPalette.WindowText, QColor(c.get('text_primary', _DEFAULTS['text_primary'])))
	palette.setColor(QPalette.Base, QColor(c.get('base_bg', _DEFAULTS['base_bg'])))
	palette.setColor(QPalette.Text, QColor(c.get('text_primary', _DEFAULTS['text_primary'])))
	palette.setColor(QPalette.ButtonText, QColor('#b6b3ab'))
	app.setPalette(palette)

	# Build and apply QSS overrides
	qss = _build_override_qss(c)
	# We need to append to the existing stylesheet, not replace it
	current = app.styleSheet()
	# Remove any previous custom theme block
	marker = '/* CUSTOM_THEME_START */'
	end_marker = '/* CUSTOM_THEME_END */'
	if marker in current:
		before = current[:current.index(marker)]
		after_end = current.find(end_marker)
		if after_end >= 0:
			after = current[after_end + len(end_marker):]
		else:
			after = ''
		current = before + after

	new_sheet = current + '\n' + marker + '\n' + qss + '\n' + end_marker
	app.setStyleSheet(new_sheet)


def _build_override_qss(c):
	"""Build QSS rules from custom theme colors."""
	rules = []

	# Table / file list
	rules.append(
		'QTableView, QDialog, QListView { background-color: %s; }'
		% c.get('base_bg', _DEFAULTS['base_bg'])
	)

	# Header
	rules.append(
		'QHeaderView, QHeaderView::section { '
		'background: qlineargradient(x1:0,y1:0,x2:0,y2:1,'
		'stop:0 %s, stop:1 %s); }'
		% (c.get('header_bg_top', _DEFAULTS['header_bg_top']),
		   c.get('header_bg_bottom', _DEFAULTS['header_bg_bottom']))
	)
	rules.append(
		'QHeaderView::section { color: %s; }'
		% c.get('text_header', _DEFAULTS['text_header'])
	)

	# File items
	rules.append(
		'QTableView::item { color: %s; }'
		% c.get('text_secondary', _DEFAULTS['text_secondary'])
	)
	rules.append(
		'QTableView::item:has-children { color: %s; }'
		% c.get('text_dirs', _DEFAULTS['text_dirs'])
	)
	rules.append(
		'QTableView::item:selected { color: %s; background-color: %s; }'
		% (c.get('selected_color', _DEFAULTS['selected_color']),
		   c.get('base_bg', _DEFAULTS['base_bg']))
	)
	rules.append(
		'QTableView::item:focus { background-color: %s; }'
		% c.get('cursor_bg', _DEFAULTS['cursor_bg'])
	)

	# Labels
	rules.append(
		'QLabel, QRadioButton, QCheckBox { color: %s; }'
		% c.get('text_secondary', _DEFAULTS['text_secondary'])
	)

	# Input fields
	rules.append(
		'QLineEdit { color: %s; background-color: %s; '
		'border: 1px solid %s; }'
		% (c.get('input_text', _DEFAULTS['input_text']),
		   c.get('input_bg', _DEFAULTS['input_bg']),
		   c.get('input_border', _DEFAULTS['input_border']))
	)

	# Location bar
	rules.append(
		'LocationBar:read-only { border-bottom: 1px solid %s; color: %s; }'
		% (c.get('location_bar_border', _DEFAULTS['location_bar_border']),
		   c.get('text_location', _DEFAULTS['text_location']))
	)

	# Status bar
	rules.append(
		'QStatusBar { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,'
		'stop:0 %s, stop:1 %s); border-top: 1px solid %s; }'
		% (c.get('status_bar_bg_top', _DEFAULTS['status_bar_bg_top']),
		   c.get('status_bar_bg_bottom', _DEFAULTS['status_bar_bg_bottom']),
		   c.get('status_bar_border', _DEFAULTS['status_bar_border']))
	)
	rules.append(
		'QStatusBar, QStatusBar QLabel { color: %s; }'
		% c.get('text_status', _DEFAULTS['text_status'])
	)

	# Quick search
	rules.append(
		'Quicksearch { background-color: %s; }'
		% c.get('quicksearch_bg', _DEFAULTS['quicksearch_bg'])
	)
	rules.append(
		'Quicksearch QLineEdit { color: %s; background-color: %s; }'
		% (c.get('quicksearch_input_text', _DEFAULTS['quicksearch_input_text']),
		   c.get('quicksearch_input_bg', _DEFAULTS['quicksearch_input_bg']))
	)
	rules.append(
		'Quicksearch QListView { background-color: %s; }'
		% c.get('quicksearch_bg', _DEFAULTS['quicksearch_bg'])
	)
	rules.append(
		'Quicksearch QListView::item:selected { background-color: %s; }'
		% c.get('quicksearch_selected', _DEFAULTS['quicksearch_selected'])
	)

	return '\n'.join(rules)


# --- Commands and panel management ---

_active_theme_editors = {}
_theme_editor_in_transition = set()


class EditTheme(DirectoryPaneCommand):

	aliases = ('Edit theme', 'Theme editor', 'Customize theme')

	def __call__(self):
		if self.pane in _theme_editor_in_transition:
			return
		if self.pane in _active_theme_editors:
			_deactivate_theme_editor(self.pane)
		else:
			# Close settings panel if open
			try:
				from settings import _active_settings, _deactivate_settings
				if self.pane in _active_settings:
					_deactivate_settings(self.pane)
			except ImportError:
				pass
			# Close preview if open
			try:
				from file_preview import _active_previews, _deactivate_preview
				if self.pane in _active_previews:
					_deactivate_preview(self.pane)
			except ImportError:
				pass
			_activate_theme_editor(self.pane)

	def is_visible(self):
		return len(self.pane.window.get_panes()) >= 2


class CloseThemeEditor(DirectoryPaneCommand):

	aliases = ('Close theme editor',)

	def __call__(self):
		if self.pane in _active_theme_editors:
			_deactivate_theme_editor(self.pane)

	def is_visible(self):
		return self.pane in _active_theme_editors


class InitThemeListener(DirectoryPaneListener):
	"""Apply saved custom theme on startup."""
	_applied = False

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		if not InitThemeListener._applied:
			InitThemeListener._applied = True
			custom = _load_custom_theme()
			if custom:
				colors = dict(_DEFAULTS)
				colors.update(custom)
				_apply_theme_to_app(colors)


class ThemeEditorModeListener(DirectoryPaneListener):
	def on_command(self, command_name, args):
		if self.pane in _active_theme_editors:
			if command_name in ('switch_panes', 'go_to'):
				_deactivate_theme_editor(self.pane)
		return None


def _activate_theme_editor(pane):
	panes = pane.window.get_panes()
	if len(panes) < 2:
		return
	_theme_editor_in_transition.add(pane)
	this_index = panes.index(pane)
	other_index = 1 - this_index
	other_pane = panes[other_index]
	target_widget = other_pane._widget

	@run_in_main_thread
	def _do_activate():
		splitter = target_widget.parentWidget()
		splitter_index = splitter.indexOf(target_widget)
		sizes = splitter.sizes()

		panel = ThemeEditorPanel(pane)
		target_widget.hide()
		splitter.insertWidget(splitter_index, panel)
		new_sizes = list(sizes)
		new_sizes.insert(splitter_index, sizes[splitter_index])
		new_sizes[splitter_index + 1] = 0
		splitter.setSizes(new_sizes)

		_active_theme_editors[pane] = {
			'panel': panel,
			'target_widget': target_widget,
			'splitter_sizes': sizes,
		}
		_theme_editor_in_transition.discard(pane)

	_do_activate()


def _deactivate_theme_editor(pane):
	state = _active_theme_editors.pop(pane, None)
	if not state:
		return
	_theme_editor_in_transition.add(pane)

	@run_in_main_thread
	def _do_deactivate():
		target_widget = state['target_widget']
		panel = state['panel']
		splitter = panel.parentWidget()
		sizes = state['splitter_sizes']
		panel.hide()
		target_widget.show()
		panel.setParent(None)
		panel.deleteLater()
		if splitter and sizes:
			splitter.setSizes(sizes)
		_theme_editor_in_transition.discard(pane)

	_do_deactivate()
