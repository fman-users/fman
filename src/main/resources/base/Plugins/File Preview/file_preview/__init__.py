from vitraj import DirectoryPaneCommand, DirectoryPaneListener
from vitraj.url import splitscheme, basename, as_human_readable
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QFont, QImage
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPlainTextEdit, \
	QStackedWidget, QScrollArea, QSizePolicy

import os

try:
	from PIL import Image as _PIL_Image
except ImportError:
	_PIL_Image = None

_TEXT_EXTENSIONS = {
	'.txt', '.py', '.js', '.ts', '.jsx', '.tsx', '.json', '.xml', '.html',
	'.htm', '.css', '.scss', '.less', '.md', '.markdown', '.yaml', '.yml',
	'.toml', '.cfg', '.ini', '.sh', '.bash', '.zsh', '.bat', '.cmd',
	'.ps1', '.log', '.csv', '.tsv', '.rst', '.java', '.c', '.h', '.cpp',
	'.hpp', '.cs', '.rs', '.go', '.rb', '.php', '.pl', '.lua', '.sql',
	'.r', '.m', '.swift', '.kt', '.scala', '.hs', '.ex', '.exs', '.erl',
	'.clj', '.lisp', '.vim', '.el', '.cmake', '.mk',
	'.gitignore', '.gitattributes', '.editorconfig',
	'.env', '.conf', '.properties', '.gradle', '.pom', '.sbt',
	'.cabal', '.lock', '.patch', '.diff',
}

_IMAGE_EXTENSIONS = {
	'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.ico', '.webp',
	'.tif', '.tiff',
}

_MAX_TEXT_SIZE = 1024 * 1024
_SNIFF_SIZE = 8192
_MAX_DIR_ENTRIES = 10000

def _format_size(size):
	if size < 1024:
		return '{:,} B'.format(size)
	elif size < 1024 * 1024:
		return '{:,.1f} KB'.format(size / 1024)
	elif size < 1024 * 1024 * 1024:
		return '{:,.1f} MB'.format(size / (1024 * 1024))
	else:
		return '{:,.1f} GB'.format(size / (1024 * 1024 * 1024))

def _looks_binary(sample):
	return b'\x00' in sample


class PreviewWidget(QWidget):

	_preview_handlers = {}

	@classmethod
	def register_handler(cls, ext, handler):
		cls._preview_handlers[ext] = handler

	def __init__(self, parent=None):
		super().__init__(parent)
		self._current_pixmap = None
		self._last_url = None
		self._init_ui()

	def _init_ui(self):
		self.setMinimumWidth(0)
		self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
		layout = QVBoxLayout()
		layout.setContentsMargins(0, 0, 0, 0)
		layout.setSpacing(0)

		self._header = QLabel()
		self._header.setObjectName('preview-header')
		self._header.setWordWrap(True)
		self._header.setStyleSheet(
			'QLabel { padding: 4px 8px; font-weight: bold; }'
		)
		layout.addWidget(self._header)

		self._stack = QStackedWidget()

		self._text_view = QPlainTextEdit()
		self._text_view.setReadOnly(True)
		self._text_view.setLineWrapMode(QPlainTextEdit.NoWrap)
		font = QFont()
		font.setStyleHint(QFont.Monospace)
		font.setFamily(font.defaultFamily())
		font.setPointSize(12)
		self._text_view.setFont(font)
		self._stack.addWidget(self._text_view)

		image_page = QWidget()
		image_layout = QVBoxLayout()
		image_layout.setContentsMargins(0, 0, 0, 0)
		image_layout.setSpacing(0)
		self._image_info = QLabel()
		self._image_info.setStyleSheet(
			'QLabel { padding: 2px 8px; font-size: 11px; }'
		)
		image_layout.addWidget(self._image_info)
		self._image_scroll = QScrollArea()
		self._image_scroll.setWidgetResizable(True)
		self._image_scroll.setAlignment(Qt.AlignCenter)
		self._image_label = QLabel()
		self._image_label.setAlignment(Qt.AlignCenter)
		self._image_label.setSizePolicy(
			QSizePolicy.Ignored, QSizePolicy.Ignored
		)
		self._image_scroll.setWidget(self._image_label)
		image_layout.addWidget(self._image_scroll)
		image_page.setLayout(image_layout)
		self._stack.addWidget(image_page)

		self._fallback = QLabel()
		self._fallback.setAlignment(Qt.AlignCenter)
		self._fallback.setWordWrap(True)
		self._fallback.setStyleSheet('QLabel { padding: 20px; }')
		self._stack.addWidget(self._fallback)

		layout.addWidget(self._stack)
		self.setLayout(layout)

	def show_preview(self, file_url):
		if file_url == self._last_url:
			return
		self._last_url = file_url
		if file_url is None:
			self._show_message('No file selected')
			return
		name = basename(file_url)
		self._header.setText(name)
		scheme, _ = splitscheme(file_url)
		if scheme != 'file://':
			self._show_message('Preview not available for %s' % scheme)
			return
		path = as_human_readable(file_url)
		if os.path.isdir(path):
			self._show_directory_info(path)
			return
		ext = os.path.splitext(name)[1].lower()
		handler = self._preview_handlers.get(ext)
		if handler:
			handler(self, path)
			return
		if ext in _IMAGE_EXTENSIONS:
			self._show_image(path, ext)
		elif ext == '.avif':
			self._show_pillow_image(path)
		elif ext in _TEXT_EXTENSIONS:
			self._show_text(path)
		else:
			self._show_by_sniffing(path)

	def show_image_pixmap(self, pixmap, info_text):
		"""Public API for handler plugins to display a pixmap with info."""
		self._current_pixmap = pixmap
		self._image_info.setText(info_text)
		self._scale_image()
		self._stack.setCurrentIndex(1)

	def clear(self):
		self._header.setText('')
		self._text_view.clear()
		self._image_label.clear()
		self._image_info.setText('')
		self._current_pixmap = None
		self._last_url = None
		self._fallback.setText('')
		self._stack.setCurrentIndex(2)

	def resizeEvent(self, event):
		super().resizeEvent(event)
		if self._current_pixmap and self._stack.currentIndex() == 1:
			self._scale_image()

	def _show_text(self, path):
		try:
			size = os.path.getsize(path)
			with open(path, 'r', encoding='utf-8', errors='replace') as f:
				content = f.read(_MAX_TEXT_SIZE)
			if size > _MAX_TEXT_SIZE:
				content += '\n\n[... truncated at 1 MB ...]'
			self._text_view.setPlainText(content)
			self._stack.setCurrentIndex(0)
		except (OSError, UnicodeDecodeError) as e:
			self._show_message('Cannot read file: %s' % e)

	def _show_pillow_image(self, path):
		if _PIL_Image is None:
			self._show_message('AVIF preview requires Pillow.\n\npip install Pillow')
			return
		try:
			with _PIL_Image.open(path) as img:
				w, h = img.width, img.height
				file_size = os.fstat(img.fp.fileno()).st_size
				rgba = img.convert('RGBA')
				data = rgba.tobytes('raw', 'RGBA')
			qimg = QImage(data, w, h, QImage.Format_RGBA8888).copy()
			pixmap = QPixmap.fromImage(qimg)
			if pixmap.isNull():
				self._show_message('Cannot load image')
				return
			self.show_image_pixmap(
				pixmap, '%d x %d px  |  %s' % (w, h, _format_size(file_size))
			)
		except Exception as e:
			self._show_message('Cannot load image: %s' % e)

	def _show_image(self, path, ext=None):
		pixmap = QPixmap(path)
		if pixmap.isNull():
			self._show_message('Cannot load image')
			return
		w, h = pixmap.width(), pixmap.height()
		if ext == '.svg':
			info = 'SVG canvas: %d x %d' % (w, h)
		else:
			try:
				size = os.path.getsize(path)
			except OSError:
				size = 0
			info = '%d x %d px  |  %s' % (w, h, _format_size(size))
		self.show_image_pixmap(pixmap, info)

	def _scale_image(self):
		if not self._current_pixmap:
			return
		available = self._image_scroll.size()
		scaled = self._current_pixmap.scaled(
			available, Qt.KeepAspectRatio, Qt.SmoothTransformation
		)
		self._image_label.setPixmap(scaled)

	def _show_by_sniffing(self, path):
		try:
			with open(path, 'rb') as f:
				sample = f.read(_SNIFF_SIZE)
				try:
					file_size = os.fstat(f.fileno()).st_size
				except OSError:
					file_size = 0
		except OSError as e:
			self._show_message('Cannot read file: %s' % e)
			return
		if not sample:
			self._show_text(path)
			return
		if _looks_binary(sample):
			self._show_message(
				'Binary file\n\n%s\n%s' % (
					os.path.basename(path), _format_size(file_size)
				)
			)
			return
		try:
			sample.decode('utf-8')
			self._show_text(path)
		except UnicodeDecodeError:
			self._show_message(
				'Binary file\n\n%s\n%s' % (
					os.path.basename(path), _format_size(file_size)
				)
			)

	def _show_directory_info(self, path):
		num_files = 0
		num_dirs = 0
		total_size = 0
		truncated = False
		try:
			with os.scandir(path) as it:
				for i, entry in enumerate(it):
					if i >= _MAX_DIR_ENTRIES:
						truncated = True
						break
					try:
						if entry.is_dir(follow_symlinks=False):
							num_dirs += 1
						else:
							num_files += 1
							total_size += entry.stat().st_size
					except OSError:
						num_files += 1
		except OSError as e:
			self._show_message('Cannot read directory: %s' % e)
			return
		lines = ['Directory\n']
		count_str = '{:,} files, {:,} folders'.format(num_files, num_dirs)
		if truncated:
			count_str += ' (first {:,} entries)'.format(_MAX_DIR_ENTRIES)
		lines.append(count_str)
		if total_size > 0:
			lines.append('Size (files only): %s' % _format_size(total_size))
		self._show_message('\n'.join(lines))

	def _show_message(self, text):
		self._current_pixmap = None
		self._fallback.setText(text)
		self._stack.setCurrentIndex(2)


_PANEL_ID = 'preview'
# Per-pane cursor tracking state (kept separately from PanelManager)
_cursor_connections = {}


class TogglePreview(DirectoryPaneCommand):

	aliases = ('Toggle preview', 'Preview file', 'View file')

	def __call__(self):
		w = self.pane.window
		if w.is_panel_active(self.pane, _PANEL_ID):
			_close_preview(self.pane)
		else:
			_open_preview(self.pane)

	def is_visible(self):
		return len(self.pane.window.get_panes()) >= 2


class ExitPreview(DirectoryPaneCommand):

	aliases = ('Exit preview', 'Close preview')

	def __call__(self):
		_close_preview(self.pane)

	def is_visible(self):
		return self.pane.window.is_panel_active(self.pane, _PANEL_ID)


class PreviewModeListener(DirectoryPaneListener):
	def on_path_changed(self):
		w = self.pane.window
		active = w.get_active_panel(self.pane)
		if active and active[0] == _PANEL_ID:
			file_url = self.pane.get_file_under_cursor()
			active[1].show_preview(file_url)


def _open_preview(pane):
	file_view = pane._widget._file_view
	file_url = pane.get_file_under_cursor()

	def factory():
		preview = PreviewWidget()

		def on_cursor_changed(current, _previous):
			try:
				url = file_view.model().url(current)
			except (ValueError, RuntimeError):
				url = None
			preview.show_preview(url)

		# Connect signal on the main thread (inside factory)
		file_view.selectionModel().currentRowChanged.connect(on_cursor_changed)
		_cursor_connections[pane] = {
			'callback': on_cursor_changed,
			'file_view': file_view,
		}
		preview.show_preview(file_url)
		return preview

	pane.window.activate_panel(pane, factory, _PANEL_ID)


def _close_preview(pane):
	# Disconnect cursor tracking before panel is destroyed
	conn = _cursor_connections.pop(pane, None)
	if conn:
		try:
			conn['file_view'].selectionModel().currentRowChanged.disconnect(
				conn['callback']
			)
		except (TypeError, RuntimeError):
			pass
	pane.window.deactivate_panel(pane)
