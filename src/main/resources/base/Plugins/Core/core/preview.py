from fman.url import splitscheme, basename
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QFont, QImage
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPlainTextEdit, \
	QStackedWidget, QScrollArea, QSizePolicy

import os

try:
	import fitz as _fitz
except ImportError:
	_fitz = None

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

def _format_size(size):
	if size < 1024:
		return '{:,} B'.format(size)
	elif size < 1024 * 1024:
		return '{:,.1f} KB'.format(size / 1024)
	elif size < 1024 * 1024 * 1024:
		return '{:,.1f} MB'.format(size / (1024 * 1024))
	else:
		return '{:,.1f} GB'.format(size / (1024 * 1024 * 1024))

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

		if ext in _IMAGE_EXTENSIONS:
			self._show_image(path, ext)
		elif ext == '.avif':
			self._show_pillow_image(path)
		elif ext == '.pdf':
			self._show_pdf(path)
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
			img = _PIL_Image.open(path)
			img = img.convert('RGBA')
			data = img.tobytes('raw', 'RGBA')
			qimg = QImage(data, img.width, img.height, QImage.Format_RGBA8888)
			pixmap = QPixmap.fromImage(qimg)
			if pixmap.isNull():
				self._show_message('Cannot load image')
				return
			size = os.path.getsize(path)
			self._image_info.setText(
				'%d x %d px  |  %s' % (img.width, img.height, _format_size(size))
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
			size = os.path.getsize(path)
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

	def _show_pdf(self, path):
		if _fitz is None:
			self._show_message('PDF preview requires PyMuPDF.\n\npip install PyMuPDF')
			return
		try:
			doc = _fitz.open(path)
			if len(doc) == 0:
				self._show_message('Empty PDF')
				doc.close()
				return
			page = doc[0]
			# Render at 150 DPI for good quality
			mat = _fitz.Matrix(150 / 72, 150 / 72)
			pix = page.get_pixmap(matrix=mat)
			# Convert to QImage then QPixmap
			if pix.alpha:
				fmt = QImage.Format_RGBA8888
			else:
				fmt = QImage.Format_RGB888
			qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
			pixmap = QPixmap.fromImage(qimg)
			num_pages = len(doc)
			page_info = '%d pages' % num_pages if num_pages > 1 else '1 page'
			self._header.setText('%s (%s)' % (self._header.text(), page_info))
			size = os.path.getsize(path)
			self._image_info.setText(
				'%s  |  %d x %d px' % (_format_size(size), pix.width, pix.height)
			)
			doc.close()
			self._current_pixmap = pixmap
			self._scale_image()
			self._stack.setCurrentIndex(1)
		except Exception as e:
			self._show_message('Cannot render PDF: %s' % e)

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

	def _show_directory_info(self, path):
		try:
			entries = os.listdir(path)
		except OSError as e:
			self._show_message('Cannot read directory: %s' % e)
			return
		num_files = 0
		num_dirs = 0
		total_size = 0
		for entry in entries:
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
		lines.append('{:,} files, {:,} folders'.format(num_files, num_dirs))
		if total_size > 0:
			lines.append('Size (files only): %s' % _format_size(total_size))
		self._show_message('\n'.join(lines))

	def _show_message(self, text):
		self._current_pixmap = None
		self._fallback.setText(text)
		self._stack.setCurrentIndex(2)
