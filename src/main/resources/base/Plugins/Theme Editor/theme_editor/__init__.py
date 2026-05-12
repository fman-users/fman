"""
Theme Editor - visual theme customization for fman.

Extends the Settings plugin with a theme editor sub-panel. Opens from
the Settings panel or via Command Palette ("Edit theme").
Uses color pickers to style all themeable elements with live preview.
Supports saving named themes and export/import as .fman-theme files.
"""
from vitraj import DirectoryPaneCommand, DirectoryPaneListener, load_json, \
	save_json, show_status_message, show_alert, show_prompt, YES, NO
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, \
	QScrollArea, QSizePolicy, QFrame, QPushButton, QColorDialog, \
	QComboBox, QFileDialog, QApplication

import json
import os

# The themeable elements and their default colors (from styles.qss + palette)
_THEME_ELEMENTS = [
	{
		'group': 'Background',
		'items': [
			('window_bg', 'Window', '#2b2b2b'),
			('base_bg', 'File list', '#272822'),
			('alternate_bg', 'File list (alternate row)', '#272822'),
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

_BUILTIN_THEMES = {
	'Blue': {
		'window_bg': '#000033', 'base_bg': '#000033', 'alternate_bg': '#000033',
		'header_bg_top': '#0000e6', 'header_bg_bottom': '#000066',
		'status_bar_bg_top': '#000066', 'status_bar_bg_bottom': '#0000e6',
		'status_bar_border': '#8080e6', 'location_bar_border': '#000033',
		'text_primary': '#ffff00', 'text_secondary': '#808080',
		'text_dirs': '#ffffff', 'text_header': '#00ffff',
		'text_status': '#ffffff', 'text_location': '#ffd000',
		'selected_color': '#f92672', 'cursor_bg': '#00ffff',
		'input_bg': '#000066', 'input_border': '#000066', 'input_text': '#ffffff',
		'quicksearch_bg': '#000066', 'quicksearch_input_bg': '#006fff',
		'quicksearch_input_text': '#000066', 'quicksearch_selected': '#0000e6',
	},
	'Default Alt': {
		'window_bg': '#272822', 'base_bg': '#272822', 'alternate_bg': '#293024',
		'header_bg_top': '#363731', 'header_bg_bottom': '#272822',
		'status_bar_bg_top': '#5b5b5b', 'status_bar_bg_bottom': '#545454',
		'status_bar_border': '#7d7d7d', 'location_bar_border': '#262626',
		'text_primary': '#ffffff', 'text_secondary': '#75715e',
		'text_dirs': '#ffffff', 'text_header': '#8f908a',
		'text_status': '#ffffff', 'text_location': '#9a9a9a',
		'selected_color': '#f92672', 'cursor_bg': '#49483e',
		'input_bg': '#303030', 'input_border': '#363731', 'input_text': '#ffffff',
		'quicksearch_bg': '#404040', 'quicksearch_input_bg': '#e6e6e6',
		'quicksearch_input_text': '#1d1d1d', 'quicksearch_selected': '#575757',
	},
	'Dracula': {
		'window_bg': '#282a36', 'base_bg': '#282a36', 'alternate_bg': '#282a36',
		'header_bg_top': '#282a36', 'header_bg_bottom': '#282a36',
		'status_bar_bg_top': '#44475a', 'status_bar_bg_bottom': '#44475a',
		'status_bar_border': '#6272a4', 'location_bar_border': '#282a36',
		'text_primary': '#f8f8f2', 'text_secondary': '#50fa7b',
		'text_dirs': '#f8f8f2', 'text_header': '#bd93f9',
		'text_status': '#8be9fd', 'text_location': '#8be9fd',
		'selected_color': '#bd93f9', 'cursor_bg': '#44475a',
		'input_bg': '#44475a', 'input_border': '#44475a', 'input_text': '#f8f8f2',
		'quicksearch_bg': '#282a36', 'quicksearch_input_bg': '#44475a',
		'quicksearch_input_text': '#f8f8f2', 'quicksearch_selected': '#44475a',
	},
	'Dracula Alt': {
		'window_bg': '#282a36', 'base_bg': '#282a36', 'alternate_bg': '#302c40',
		'header_bg_top': '#282a36', 'header_bg_bottom': '#282a36',
		'status_bar_bg_top': '#44475a', 'status_bar_bg_bottom': '#44475a',
		'status_bar_border': '#6272a4', 'location_bar_border': '#282a36',
		'text_primary': '#f8f8f2', 'text_secondary': '#50fa7b',
		'text_dirs': '#f8f8f2', 'text_header': '#bd93f9',
		'text_status': '#8be9fd', 'text_location': '#8be9fd',
		'selected_color': '#bd93f9', 'cursor_bg': '#44475a',
		'input_bg': '#44475a', 'input_border': '#44475a', 'input_text': '#f8f8f2',
		'quicksearch_bg': '#282a36', 'quicksearch_input_bg': '#44475a',
		'quicksearch_input_text': '#f8f8f2', 'quicksearch_selected': '#44475a',
	},
	'Forest': {
		'window_bg': '#1f1f1f', 'base_bg': '#1f1f1f', 'alternate_bg': '#1f1f1f',
		'status_bar_bg_top': '#2f4f32', 'status_bar_bg_bottom': '#2f4f32',
		'status_bar_border': '#4e684e',
		'text_dirs': '#d4d7d6', 'text_secondary': '#395f3c',
		'selected_color': '#bde091', 'cursor_bg': '#363636',
		'quicksearch_bg': '#2f4f32',
	},
	'High Contrast Light': {
		'window_bg': '#cccccc', 'base_bg': '#ffffff', 'alternate_bg': '#efefef',
		'header_bg_top': '#eeeeee', 'header_bg_bottom': '#eeeeee',
		'status_bar_bg_top': '#ffffff', 'status_bar_bg_bottom': '#ffffff',
		'status_bar_border': '#000000', 'location_bar_border': '#000000',
		'text_primary': '#000000', 'text_secondary': '#000000',
		'text_dirs': '#000000', 'text_header': '#000000',
		'text_status': '#000000', 'text_location': '#000000',
		'selected_color': '#000000', 'cursor_bg': '#000000',
		'input_bg': '#bbbbbb', 'input_border': '#bbbbbb', 'input_text': '#000000',
		'quicksearch_bg': '#888888', 'quicksearch_input_bg': '#ffffff',
		'quicksearch_input_text': '#000000', 'quicksearch_selected': '#dddddd',
	},
	'NC 03': {
		'window_bg': '#47a8e0', 'base_bg': '#1981fa', 'alternate_bg': '#1981fa',
		'header_bg_top': '#00c0ff', 'header_bg_bottom': '#47a8e0',
		'status_bar_bg_top': '#47a8e0', 'status_bar_bg_bottom': '#47a8e0',
		'status_bar_border': '#006fff', 'location_bar_border': '#1981fa',
		'text_primary': '#00fef2', 'text_secondary': '#00fff9',
		'text_dirs': '#00fffc', 'text_header': '#00ffff',
		'text_status': '#00fffc', 'text_location': '#1981fa',
		'selected_color': '#e7c000', 'cursor_bg': '#252efd',
		'input_bg': '#00b1ff', 'input_border': '#009de2', 'input_text': '#00fffc',
		'quicksearch_bg': '#00b1ff', 'quicksearch_input_bg': '#006fff',
		'quicksearch_input_text': '#00fffc', 'quicksearch_selected': '#006fff',
	},
	'Nord': {
		'window_bg': '#434C5E', 'base_bg': '#2E3440', 'alternate_bg': '#2E3440',
		'header_bg_top': '#2E3440', 'header_bg_bottom': '#2E3440',
		'status_bar_bg_top': '#434C5E', 'status_bar_bg_bottom': '#434C5E',
		'status_bar_border': '#434C5E', 'location_bar_border': '#2E3440',
		'text_primary': '#D8DEE9', 'text_secondary': '#8FBCBB',
		'text_dirs': '#D8DEE9', 'text_header': '#EBCB8B',
		'text_status': '#88C0D0', 'text_location': '#88C0D0',
		'selected_color': '#BF616A', 'cursor_bg': '#4C566A',
		'input_bg': '#434C5E', 'input_border': '#434C5E', 'input_text': '#D8DEE9',
		'quicksearch_bg': '#2E3440', 'quicksearch_input_bg': '#434C5E',
		'quicksearch_input_text': '#D8DEE9', 'quicksearch_selected': '#434C5E',
	},
	'White': {
		'window_bg': '#f6f8fa', 'base_bg': '#ffffff', 'alternate_bg': '#ffffff',
		'header_bg_top': '#f6f8fa', 'header_bg_bottom': '#f6f8fa',
		'status_bar_bg_top': '#ffffff', 'status_bar_bg_bottom': '#ffffff',
		'status_bar_border': '#f6f8fa', 'location_bar_border': '#f6f8fa',
		'text_primary': '#000000', 'text_secondary': '#000000',
		'text_dirs': '#000000', 'text_header': '#000000',
		'text_status': '#000000', 'text_location': '#000000',
		'selected_color': '#000000', 'cursor_bg': '#f6f8fa',
		'input_bg': '#ffffff', 'input_border': '#f6f8fa', 'input_text': '#000000',
		'quicksearch_bg': '#ffffff', 'quicksearch_input_bg': '#ffffff',
		'quicksearch_input_text': '#000000', 'quicksearch_selected': '#f6f8fa',
	},
}

_THEME_FILE_FILTER = 'fman Theme (*.fman-theme);;JSON (*.json);;All Files (*)'

_CUSTOM_THEME_JSON = 'Custom Theme.json'
_SAVED_THEMES_JSON = 'Saved Themes.json'


def _load_custom_theme():
	return load_json(_CUSTOM_THEME_JSON, default={})


def _save_custom_theme():
	save_json(_CUSTOM_THEME_JSON)


def _load_saved_themes():
	return load_json(_SAVED_THEMES_JSON, default={})


def _save_saved_themes():
	save_json(_SAVED_THEMES_JSON)


def _get_non_default_colors(colors):
	return {k: v for k, v in colors.items() if v != _DEFAULTS.get(k)}


class ColorButton(QPushButton):

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
		self._header = QLabel(
			'  Name                         Size       Modified'
		)
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
		c = colors

		self._loc_bar.setStyleSheet(
			'QLabel { background-color: %s; color: %s; padding-left: 4px; '
			'font-size: 10px; border-bottom: 1px solid %s; }' % (
				c.get('window_bg', _DEFAULTS['window_bg']),
				c.get('text_location', _DEFAULTS['text_location']),
				c.get('location_bar_border', _DEFAULTS['location_bar_border']),
			)
		)

		self._header.setStyleSheet(
			'QLabel { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,'
			'stop:0 %s, stop:1 %s); color: %s; font-size: 9px; }' % (
				c.get('header_bg_top', _DEFAULTS['header_bg_top']),
				c.get('header_bg_bottom', _DEFAULTS['header_bg_bottom']),
				c.get('text_header', _DEFAULTS['text_header']),
			)
		)

		base_bg = c.get('base_bg', _DEFAULTS['base_bg'])
		alt_bg = c.get('alternate_bg', _DEFAULTS['alternate_bg'])
		cursor_bg = c.get('cursor_bg', _DEFAULTS['cursor_bg'])
		text_dirs = c.get('text_dirs', _DEFAULTS['text_dirs'])
		text_secondary = c.get('text_secondary', _DEFAULTS['text_secondary'])
		selected_color = c.get('selected_color', _DEFAULTS['selected_color'])

		self._rows_widget.setStyleSheet(
			'QWidget { background-color: %s; }' % base_bg
		)

		for i, (label, is_dir, is_selected, is_cursor) in enumerate(
			self._row_labels
		):
			if is_cursor:
				bg = cursor_bg
			elif i % 2:
				bg = alt_bg
			else:
				bg = base_bg
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
		self._section_headers = []
		self._back_btn = None
		self._apply_btn = None
		self._init_ui()

	def _init_ui(self):
		self.setMinimumWidth(0)
		self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
		self.setAttribute(Qt.WA_StyledBackground, True)

		outer = QVBoxLayout()
		outer.setContentsMargins(0, 0, 0, 0)
		outer.setSpacing(0)

		header_row = QHBoxLayout()
		header_row.setContentsMargins(8, 6, 8, 6)
		self._back_btn = QPushButton('\u2190 Back')
		self._back_btn.setFixedWidth(60)
		accent = self._colors.get('selected_color', _DEFAULTS['selected_color'])
		self._back_btn.setStyleSheet(
			'QPushButton { color: %s; background: transparent; '
			'border: none; font-size: 11px; text-align: left; }'
			'QPushButton:hover { color: white; }' % accent
		)
		self._back_btn.clicked.connect(self._go_back)
		header_row.addWidget(self._back_btn)
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

		# Scrollable content
		scroll = QScrollArea()
		scroll.setWidgetResizable(True)
		scroll.setFrameShape(QFrame.NoFrame)
		scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
		scroll.setAttribute(Qt.WA_StyledBackground, True)

		content = QWidget()
		content.setAttribute(Qt.WA_StyledBackground, True)
		self._grid_layout = QVBoxLayout()
		self._grid_layout.setContentsMargins(8, 4, 8, 8)
		self._grid_layout.setSpacing(4)

		# --- Saved themes selector ---
		self._add_section_header('Saved Themes')
		theme_row = QHBoxLayout()
		theme_row.setSpacing(4)
		self._theme_combo = QComboBox()
		self._theme_combo.setMinimumWidth(100)
		self._refresh_theme_list()
		self._theme_combo.currentIndexChanged.connect(self._on_theme_selected)
		theme_row.addWidget(self._theme_combo)
		save_btn = QPushButton('Save')
		save_btn.setFixedWidth(44)
		save_btn.clicked.connect(self._on_save_theme)
		theme_row.addWidget(save_btn)
		del_btn = QPushButton('Del')
		del_btn.setFixedWidth(34)
		del_btn.clicked.connect(self._on_delete_theme)
		theme_row.addWidget(del_btn)
		self._grid_layout.addLayout(theme_row)

		# Import / Export row
		io_row = QHBoxLayout()
		io_row.setSpacing(4)
		import_btn = QPushButton('Import...')
		import_btn.clicked.connect(self._on_import_theme)
		io_row.addWidget(import_btn)
		export_btn = QPushButton('Export...')
		export_btn.clicked.connect(self._on_export_theme)
		io_row.addWidget(export_btn)
		self._grid_layout.addLayout(io_row)

		# --- Color pickers ---
		self._color_buttons = {}

		for group in _THEME_ELEMENTS:
			self._add_section_header(group['group'])

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

		self._apply_btn = QPushButton('Apply to App')
		self._apply_btn.setStyleSheet(
			'QPushButton { background-color: %s; color: %s; '
			'font-weight: bold; padding: 6px 12px; border: none; '
			'border-radius: 3px; }'
			'QPushButton:hover { opacity: 0.8; }'
			% (accent, self._colors.get('base_bg', _DEFAULTS['base_bg']))
		)
		self._apply_btn.clicked.connect(self._apply_theme)
		btn_row.addWidget(self._apply_btn)

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

	def _add_section_header(self, title):
		label = QLabel(title)
		accent = self._colors.get('selected_color', _DEFAULTS['selected_color'])
		label.setStyleSheet(
			'QLabel { color: %s; font-weight: bold; font-size: 11px; '
			'padding-top: 8px; padding-bottom: 2px; }' % accent
		)
		self._section_headers.append(label)
		self._grid_layout.addWidget(label)

	# --- Color picker handlers ---

	def _on_color_changed(self, key, hex_color):
		self._colors[key] = hex_color
		self._preview.update_colors(self._colors)

	def _load_colors_into_ui(self, colors):
		self._colors = dict(_DEFAULTS)
		self._colors.update(colors)
		for key, btn in self._color_buttons.items():
			btn.set_color(self._colors.get(key, _DEFAULTS.get(key, '#000')))
		self._preview.update_colors(self._colors)
		self._update_accent_colors()

	def _update_accent_colors(self):
		accent = self._colors.get('selected_color', _DEFAULTS['selected_color'])
		base = self._colors.get('base_bg', _DEFAULTS['base_bg'])
		self._back_btn.setStyleSheet(
			'QPushButton { color: %s; background: transparent; '
			'border: none; font-size: 11px; text-align: left; }'
			'QPushButton:hover { color: white; }' % accent
		)
		self._apply_btn.setStyleSheet(
			'QPushButton { background-color: %s; color: %s; '
			'font-weight: bold; padding: 6px 12px; border: none; '
			'border-radius: 3px; }'
			'QPushButton:hover { opacity: 0.8; }' % (accent, base)
		)
		for lbl in self._section_headers:
			lbl.setStyleSheet(
				'QLabel { color: %s; font-weight: bold; font-size: 11px; '
				'padding-top: 8px; padding-bottom: 2px; }' % accent
			)

	# --- Apply / Reset ---

	def _apply_theme(self):
		custom = _get_non_default_colors(self._colors)
		theme_data = _load_custom_theme()
		theme_data.clear()
		theme_data.update(custom)
		_save_custom_theme()

		_apply_theme_to_app(self._colors)
		show_status_message('Theme applied.', 3)

	def _reset_theme(self):
		self._load_colors_into_ui({})

		theme_data = _load_custom_theme()
		theme_data.clear()
		_save_custom_theme()

		_apply_theme_to_app(self._colors)
		show_status_message('Theme reset to default.', 3)

	# --- Saved themes ---

	def _refresh_theme_list(self):
		self._theme_combo.blockSignals(True)
		self._theme_combo.clear()
		self._theme_combo.addItem('(current)')
		saved = _load_saved_themes()
		for name in sorted(saved.keys()):
			self._theme_combo.addItem(name)
		if _BUILTIN_THEMES:
			self._theme_combo.insertSeparator(self._theme_combo.count())
			for name in sorted(_BUILTIN_THEMES.keys()):
				self._theme_combo.addItem(name)
		self._theme_combo.setCurrentIndex(0)
		self._theme_combo.blockSignals(False)

	def _on_theme_selected(self, index):
		if index <= 0:
			return
		name = self._theme_combo.currentText()
		saved = _load_saved_themes()
		theme_colors = saved.get(name) or _BUILTIN_THEMES.get(name, {})
		self._load_colors_into_ui(theme_colors)

	def _on_save_theme(self):
		current_name = self._theme_combo.currentText()
		default_name = '' if current_name == '(current)' else current_name
		result = show_prompt('Theme name:', default_name)
		if not result:
			return
		name, ok = result
		if not ok or not name.strip():
			return
		name = name.strip()

		custom = _get_non_default_colors(self._colors)
		saved = _load_saved_themes()
		saved[name] = custom
		_save_saved_themes()

		self._refresh_theme_list()
		# Select the newly saved theme
		idx = self._theme_combo.findText(name)
		if idx >= 0:
			self._theme_combo.setCurrentIndex(idx)
		show_status_message('Theme "%s" saved.' % name, 3)

	def _on_delete_theme(self):
		name = self._theme_combo.currentText()
		if name == '(current)':
			return
		choice = show_alert(
			'Delete theme "%s"?' % name, YES | NO, NO
		)
		if not (choice & YES):
			return
		saved = _load_saved_themes()
		saved.pop(name, None)
		_save_saved_themes()
		self._refresh_theme_list()
		show_status_message('Theme "%s" deleted.' % name, 3)

	# --- Import / Export ---

	def _on_export_theme(self):
		custom = _get_non_default_colors(self._colors)
		current_name = self._theme_combo.currentText()
		suggested_name = 'my-theme' if current_name == '(current)' else current_name
		suggested_path = os.path.join(
			os.path.expanduser('~'), suggested_name + '.fman-theme'
		)

		path, _ = QFileDialog.getSaveFileName(
			self, 'Export Theme', suggested_path, _THEME_FILE_FILTER
		)
		if not path:
			return

		export_data = {
			'fman_theme': 1,
			'name': current_name if current_name != '(current)' else '',
			'colors': custom,
		}
		try:
			with open(path, 'w', encoding='utf-8') as f:
				json.dump(export_data, f, indent=2, sort_keys=True)
			show_status_message('Theme exported to %s' % os.path.basename(path), 3)
		except OSError as e:
			show_alert('Could not export theme: %s' % e)

	def _on_import_theme(self):
		path, _ = QFileDialog.getOpenFileName(
			self, 'Import Theme', os.path.expanduser('~'), _THEME_FILE_FILTER
		)
		if not path:
			return

		try:
			with open(path, 'r', encoding='utf-8') as f:
				data = json.load(f)
		except (OSError, json.JSONDecodeError) as e:
			show_alert('Could not read theme file: %s' % e)
			return

		# Accept both raw color dicts and wrapped format
		if isinstance(data, dict) and 'colors' in data:
			colors = data['colors']
			name = data.get('name', '')
		elif isinstance(data, dict):
			colors = data
			name = ''
		else:
			show_alert('Invalid theme file format.')
			return

		# Validate: all values should be color strings
		valid_keys = set(_DEFAULTS.keys())
		cleaned = {}
		for k, v in colors.items():
			if k in valid_keys and isinstance(v, str) and QColor(v).isValid():
				cleaned[k] = v

		if not cleaned:
			show_alert('No valid color values found in theme file.')
			return

		self._load_colors_into_ui(cleaned)

		# Offer to save
		if not name:
			base = os.path.basename(path)
			name = os.path.splitext(base)[0]

		result = show_prompt('Save imported theme as:', name)
		if result:
			save_name, ok = result
			if ok and save_name.strip():
				saved = _load_saved_themes()
				saved[save_name.strip()] = cleaned
				_save_saved_themes()
				self._refresh_theme_list()
				idx = self._theme_combo.findText(save_name.strip())
				if idx >= 0:
					self._theme_combo.setCurrentIndex(idx)

		show_status_message('Theme imported.', 3)

	# --- Navigation ---

	def _go_back(self):
		w = self._pane.window
		if w.is_panel_active(self._pane, _PANEL_ID):
			w.deactivate_panel(self._pane)
			self._pane.run_command('open_settings')


def _apply_theme_to_app(colors):
	"""Apply the custom color scheme to the running application."""
	app = QApplication.instance()
	if app is None:
		return

	c = colors

	# Update QPalette
	palette = app.palette()
	palette.setColor(
		QPalette.Window,
		QColor(c.get('window_bg', _DEFAULTS['window_bg']))
	)
	palette.setColor(
		QPalette.WindowText,
		QColor(c.get('text_primary', _DEFAULTS['text_primary']))
	)
	palette.setColor(
		QPalette.Base,
		QColor(c.get('base_bg', _DEFAULTS['base_bg']))
	)
	palette.setColor(
		QPalette.Text,
		QColor(c.get('text_primary', _DEFAULTS['text_primary']))
	)
	palette.setColor(
		QPalette.ButtonText,
		QColor(c.get('text_primary', _DEFAULTS['text_primary']))
	)
	palette.setColor(
		QPalette.BrightText,
		QColor(c.get('selected_color', _DEFAULTS['selected_color']))
	)
	palette.setColor(
		QPalette.Button,
		QColor(c.get('window_bg', _DEFAULTS['window_bg']))
	)
	palette.setColor(
		QPalette.Highlight,
		QColor(c.get('cursor_bg', _DEFAULTS['cursor_bg']))
	)
	palette.setColor(
		QPalette.HighlightedText,
		QColor(c.get('text_primary', _DEFAULTS['text_primary']))
	)
	app.setPalette(palette)

	# Build and apply QSS overrides
	qss = _build_override_qss(c)
	current = app.styleSheet()
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

	# Update quicksearch item CSS in the theme engine
	try:
		from vitraj import _get_app_ctxt
		theme = _get_app_ctxt().theme
		text_primary = c.get('text_primary', _DEFAULTS['text_primary'])
		text_secondary = c.get('text_secondary', _DEFAULTS['text_secondary'])
		selected = c.get('selected_color', _DEFAULTS['selected_color'])
		qs_css = (
			'.quicksearch-item-title { color: %s; }\n'
			'.quicksearch-item-title-highlight { color: %s; }\n'
			'.quicksearch-item-hint { color: %s; }\n'
			'.quicksearch-item-description { color: %s; }\n'
			% (text_secondary, selected, text_primary, text_secondary)
		)
		from vitraj.impl.util.css import parse_css
		rules = parse_css(qs_css.encode())
		theme._css_rules['__custom_theme__'] = rules
		theme._quicksearch_item_css = theme._get_quicksearch_item_css()
	except Exception:
		pass


def _build_override_qss(c):
	"""Build QSS rules from custom theme colors."""
	rules = []

	rules.append(
		'* { background: %s; }'
		% c.get('window_bg', _DEFAULTS['window_bg'])
	)

	rules.append(
		'QTableView, QMessageBox, QDialog, QListView, QPlainTextEdit '
		'{ background-color: %s; alternate-background-color: %s; }'
		% (c.get('base_bg', _DEFAULTS['base_bg']),
		   c.get('alternate_bg', _DEFAULTS['alternate_bg']))
	)
	rules.append(
		'QPlainTextEdit { color: %s; }'
		% c.get('text_primary', _DEFAULTS['text_primary'])
	)
	rules.append(
		'#preview-header { color: %s; }'
		% c.get('text_primary', _DEFAULTS['text_primary'])
	)

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

	rules.append(
		'QLabel, QRadioButton, QCheckBox { color: %s; }'
		% c.get('text_secondary', _DEFAULTS['text_secondary'])
	)

	rules.append(
		'QLineEdit { color: %s; background-color: %s; '
		'border: 1px solid %s; }'
		% (c.get('input_text', _DEFAULTS['input_text']),
		   c.get('input_bg', _DEFAULTS['input_bg']),
		   c.get('input_border', _DEFAULTS['input_border']))
	)

	rules.append(
		'LocationBar:read-only { border-bottom: 1px solid %s; color: %s; }'
		% (c.get('location_bar_border', _DEFAULTS['location_bar_border']),
		   c.get('text_location', _DEFAULTS['text_location']))
	)

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

	text_primary = c.get('text_primary', _DEFAULTS['text_primary'])
	rules.append(
		'QPushButton { color: %s; }' % text_primary
	)
	rules.append(
		'QMessageBox { color: %s; }' % text_primary
	)
	rules.append(
		'QMessageBox QLabel { color: %s; }' % text_primary
	)
	rules.append(
		'QDialog { color: %s; }' % text_primary
	)

	rules.append(
		'Overlay { background-color: %s; border: 1px solid %s; color: %s; }'
		% (c.get('base_bg', _DEFAULTS['base_bg']),
		   c.get('input_border', _DEFAULTS['input_border']),
		   text_primary)
	)
	rules.append(
		'FilterBar { background-color: %s; border: 1px solid %s; }'
		% (c.get('base_bg', _DEFAULTS['base_bg']),
		   c.get('input_border', _DEFAULTS['input_border']))
	)

	return '\n'.join(rules)


_PANEL_ID = 'theme_editor'


class EditTheme(DirectoryPaneCommand):

	aliases = ('Edit theme', 'Theme editor', 'Customize theme')

	def __call__(self):
		w = self.pane.window
		if w.is_panel_active(self.pane, _PANEL_ID):
			w.deactivate_panel(self.pane)
		else:
			pane = self.pane
			w.activate_panel(pane, lambda: ThemeEditorPanel(pane), _PANEL_ID)

	def is_visible(self):
		return len(self.pane.window.get_panes()) >= 2


class CloseThemeEditor(DirectoryPaneCommand):

	aliases = ('Close theme editor',)

	def __call__(self):
		w = self.pane.window
		if w.is_panel_active(self.pane, _PANEL_ID):
			w.deactivate_panel(self.pane)

	def is_visible(self):
		return self.pane.window.is_panel_active(self.pane, _PANEL_ID)


class InitThemeListener(DirectoryPaneListener):
	_applied = False

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		if not InitThemeListener._applied:
			InitThemeListener._applied = True
			from PyQt5.QtCore import QTimer
			QTimer.singleShot(500, lambda: _apply_saved_custom_theme(0))


def _apply_saved_custom_theme(attempt):
	try:
		from alternative_colors import delayed_init_started
		if not delayed_init_started and attempt < 5:
			from PyQt5.QtCore import QTimer
			QTimer.singleShot(300, lambda: _apply_saved_custom_theme(attempt + 1))
			return
	except ImportError:
		pass
	custom = _load_custom_theme()
	non_default = _get_non_default_colors(
		dict(_DEFAULTS, **custom)
	) if custom else {}
	if non_default:
		colors = dict(_DEFAULTS)
		colors.update(custom)
		_apply_theme_to_app(colors)
