from fman.url import splitscheme, basename
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPlainTextEdit, \
	QStackedWidget, QScrollArea, QSizePolicy

import os

_TEXT_EXTENSIONS = {
	'.txt', '.py', '.js', '.ts', '.jsx', '.tsx', '.json', '.xml', '.html',
	'.htm', '.css', '.scss', '.less', '.md', '.markdown', '.yaml', '.yml',
	'.toml', '.cfg', '.ini', '.sh', '.bash', '.zsh', '.bat', '.cmd',
	'.ps1', '.log', '.csv', '.tsv', '.rst', '.java', '.c', '.h', '.cpp',
	'.hpp', '.cs', '.rs', '.go', '.rb', '.php', '.pl', '.lua', '.sql',
	'.r', '.m', '.swift', '.kt', '.scala', '.hs', '.ex', '.exs', '.erl',
	'.clj', '.lisp', '.vim', '.el', '.cmake', '.makefile', '.mk',
	'.dockerfile', '.gitignore', '.gitattributes', '.editorconfig',
	'.env', '.conf', '.properties', '.gradle', '.pom', '.sbt',
	'.cabal', '.lock', '.patch', '.diff',
}

_IMAGE_EXTENSIONS = {
	'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.ico', '.webp',
	'.tif', '.tiff',
}

_MAX_TEXT_SIZE = 1024 * 1024  # 1 MB
_SNIFF_SIZE = 8192

class PreviewWidget(QWidget):
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

		# Page 1: Image preview
		self._image_scroll = QScrollArea()
		self._image_scroll.setWidgetResizable(True)
		self._image_scroll.setAlignment(Qt.AlignCenter)
		self._image_label = QLabel()
		self._image_label.setAlignment(Qt.AlignCenter)
		self._image_label.setSizePolicy(
			QSizePolicy.Ignored, QSizePolicy.Ignored
		)
		self._image_scroll.setWidget(self._image_label)
		self._stack.addWidget(self._image_scroll)

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
			self._show_message('Directory')
			return

		ext = os.path.splitext(name)[1].lower()

		if ext in _IMAGE_EXTENSIONS:
			self._show_image(path)
		elif ext in _TEXT_EXTENSIONS:
			self._show_text(path)
		else:
			self._show_by_sniffing(path)

	def clear(self):
		self._header.setText('')
		self._text_view.clear()
		self._image_label.clear()
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

	def _show_image(self, path):
		pixmap = QPixmap(path)
		if pixmap.isNull():
			self._show_message('Cannot load image')
			return
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
		except OSError as e:
			self._show_message('Cannot read file: %s' % e)
			return

		if not sample:
			self._show_text(path)
			return

		try:
			sample.decode('utf-8')
			self._show_text(path)
		except UnicodeDecodeError:
			size = os.path.getsize(path)
			self._show_message(
				'Binary file\n\n%s\n%s bytes' % (
					os.path.basename(path),
					'{:,}'.format(size)
				)
			)

	def _show_message(self, text):
		self._current_pixmap = None
		self._fallback.setText(text)
		self._stack.setCurrentIndex(2)
