from fman import DirectoryPaneCommand, DirectoryPaneListener
from fman.url import splitscheme, basename
from fman.impl.util.qt.thread import run_in_main_thread
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

	# Registry of extension -> handler for plugin extensibility.
	# Handlers are called as handler(self, path) where self is PreviewWidget.
	_preview_handlers = {}

	@classmethod
	def register_handler(cls, ext, handler):
		cls._preview_handlers[ext] = handler

	def __init__(self, parent=None):
		super().__init__(parent)
		self._current_pixmap = None
		self._init_ui()

	def _init_ui(self):
		self.setMinimumWidth(0)
		self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
		layout = QVBoxLayout()
		layout.setContentsMargins(0, 0, 0, 0)
		layout.setSpacing(0)

		self._header = QLabel()
		self._header.setWordWrap(True)
		self._header.setStyleSheet(
			'QLabel { padding: 4px 8px; font-weight: bold; }'
		)
		layout.addWidget(self._header)

		self._stack = QStackedWidget()

		# Page 0: Text preview
		self._text_view = QPlainTextEdit()
		self._text_view.setReadOnly(True)
		self._text_view.setLineWrapMode(QPlainTextEdit.NoWrap)
		font = QFont()
		font.setStyleHint(QFont.Monospace)
		font.setFamily(font.defaultFamily())
		font.setPointSize(12)
		self._text_view.setFont(font)
		self._stack.addWidget(self._text_view)

		# Page 1: Image preview with info bar
		image_page = QWidget()
		image_layout = QVBoxLayout()
		image_layout.setContentsMargins(0, 0, 0, 0)
		image_layout.setSpacing(0)
		self._image_info = QLabel()
		self._image_info.setStyleSheet(
			'QLabel { padding: 2px 8px; color: gray; font-size: 11px; }'
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

		# Page 2: Fallback message
		self._fallback = QLabel()
		self._fallback.setAlignment(Qt.AlignCenter)
		self._fallback.setWordWrap(True)
		self._fallback.setStyleSheet('QLabel { color: gray; padding: 20px; }')
		self._stack.addWidget(self._fallback)

		layout.addWidget(self._stack)
		self.setLayout(layout)

	def show_preview(self, file_url):
		if file_url is None:
			self._show_message('No file selected')
			return
		name = basename(file_url)
		self._header.setText(name)
		scheme, path = splitscheme(file_url)
		if scheme != 'file://':
			self._show_message('Preview not available for %s' % scheme)
			return
		if os.path.isdir(path):
			self._show_directory_info(path)
			return
		ext = os.path.splitext(name)[1].lower()
		# Check registered handlers first (PDF, etc.)
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

	def clear(self):
		self._header.setText('')
		self._text_view.clear()
		self._image_label.clear()
		self._image_info.setText('')
		self._current_pixmap = None
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
				rgba = img.convert('RGBA')
				data = rgba.tobytes('raw', 'RGBA')
			# data is a bytes object that outlives the with block
			qimg = QImage(data, w, h, QImage.Format_RGBA8888).copy()
			pixmap = QPixmap.fromImage(qimg)
			if pixmap.isNull():
				self._show_message('Cannot load image')
				return
			size = os.path.getsize(path)
			self._image_info.setText(
				'%d x %d px  |  %s' % (w, h, _format_size(size))
			)
			self._current_pixmap = pixmap
			self._scale_image()
			self._stack.setCurrentIndex(1)
		except Exception as e:
			self._show_message('Cannot load image: %s' % e)

	def _show_image(self, path, ext=None):
		pixmap = QPixmap(path)
		if pixmap.isNull():
			self._show_message('Cannot load image')
			return
		w, h = pixmap.width(), pixmap.height()
		if ext == '.svg':
			self._image_info.setText('SVG canvas: %d x %d' % (w, h))
		else:
			try:
				size = os.path.getsize(path)
			except OSError:
				size = 0
			self._image_info.setText(
				'%d x %d px  |  %s' % (w, h, _format_size(size))
			)
		self._current_pixmap = pixmap
		self._scale_image()
		self._stack.setCurrentIndex(1)

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
		try:
			entries = os.listdir(path)
		except OSError as e:
			self._show_message('Cannot read directory: %s' % e)
			return
		num_files = 0
		num_dirs = 0
		total_size = 0
		for i, entry in enumerate(entries):
			if i >= _MAX_DIR_ENTRIES:
				break
			entry_path = os.path.join(path, entry)
			try:
				if os.path.isdir(entry_path):
					num_dirs += 1
				else:
					num_files += 1
					total_size += os.path.getsize(entry_path)
			except OSError:
				num_files += 1
		lines = ['Directory\n']
		count_str = '{:,} files, {:,} folders'.format(num_files, num_dirs)
		if len(entries) > _MAX_DIR_ENTRIES:
			count_str += ' (first {:,} entries)'.format(_MAX_DIR_ENTRIES)
		lines.append(count_str)
		if total_size > 0:
			lines.append('Size (files only): %s' % _format_size(total_size))
		self._show_message('\n'.join(lines))

	def _show_message(self, text):
		self._current_pixmap = None
		self._fallback.setText(text)
		self._stack.setCurrentIndex(2)


# --- Commands and Listeners ---

_active_previews = {}
_preview_in_transition = set()


class TogglePreview(DirectoryPaneCommand):

	aliases = ('Toggle preview', 'Preview file', 'View file')

	def __call__(self):
		if self.pane in _preview_in_transition:
			return
		if self.pane in _active_previews:
			_deactivate_preview(self.pane)
		else:
			_activate_preview(self.pane)
	def is_visible(self):
		return len(self.pane.window.get_panes()) >= 2


class ExitPreview(DirectoryPaneCommand):

	aliases = ('Exit preview', 'Close preview')

	def __call__(self):
		if self.pane in _active_previews:
			_deactivate_preview(self.pane)
	def is_visible(self):
		return self.pane in _active_previews


class PreviewModeListener(DirectoryPaneListener):
	def on_path_changed(self):
		if self.pane in _active_previews:
			file_url = self.pane.get_file_under_cursor()
			state = _active_previews[self.pane]
			state['preview_widget'].show_preview(file_url)
	def on_command(self, command_name, args):
		if self.pane in _active_previews:
			if command_name in ('switch_panes', 'go_to'):
				_deactivate_preview(self.pane)
		return None


def _activate_preview(pane):
	panes = pane.window.get_panes()
	if len(panes) < 2:
		return
	_preview_in_transition.add(pane)
	this_index = panes.index(pane)
	other_index = 1 - this_index
	other_pane = panes[other_index]
	target_widget = other_pane._widget
	file_view = pane._widget._file_view
	file_url = pane.get_file_under_cursor()

	@run_in_main_thread
	def _do_activate():
		splitter = target_widget.parentWidget()
		splitter_index = splitter.indexOf(target_widget)
		sizes = splitter.sizes()

		preview = PreviewWidget()
		target_widget.hide()
		splitter.insertWidget(splitter_index, preview)
		new_sizes = list(sizes)
		new_sizes.insert(splitter_index, sizes[splitter_index])
		new_sizes[splitter_index + 1] = 0
		splitter.setSizes(new_sizes)

		def on_cursor_changed(current, _previous):
			try:
				url = file_view.model().url(current)
			except (ValueError, RuntimeError):
				url = None
			preview.show_preview(url)

		file_view.selectionModel().currentRowChanged.connect(on_cursor_changed)

		_active_previews[pane] = {
			'preview_widget': preview,
			'target_widget': target_widget,
			'splitter_sizes': sizes,
			'on_cursor_changed': on_cursor_changed,
			'file_view': file_view,
		}
		_preview_in_transition.discard(pane)

		preview.show_preview(file_url)

	_do_activate()


def _deactivate_preview(pane):
	state = _active_previews.pop(pane, None)
	if not state:
		return
	_preview_in_transition.add(pane)

	@run_in_main_thread
	def _do_deactivate():
		file_view = state['file_view']
		try:
			file_view.selectionModel().currentRowChanged.disconnect(
				state['on_cursor_changed']
			)
		except (TypeError, RuntimeError):
			pass
		target_widget = state['target_widget']
		preview = state['preview_widget']
		splitter = preview.parentWidget()
		sizes = state['splitter_sizes']
		preview.hide()
		target_widget.show()
		preview.setParent(None)
		preview.deleteLater()
		if splitter and sizes:
			splitter.setSizes(sizes)
		_preview_in_transition.discard(pane)

	_do_deactivate()
