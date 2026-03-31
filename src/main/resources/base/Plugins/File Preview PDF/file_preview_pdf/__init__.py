"""
File Preview PDF - adds PDF rendering to the File Preview plugin.

Requires: PyMuPDF (pip install PyMuPDF)
Requires: File Preview plugin (must be loaded first)
"""
from fman.url import splitscheme, basename
from PyQt5.QtGui import QPixmap, QImage

import os

try:
	import fitz as _fitz
except ImportError:
	_fitz = None

try:
	from file_preview import PreviewWidget, _format_size
except ImportError:
	PreviewWidget = None


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
		mat = _fitz.Matrix(150 / 72, 150 / 72)
		pix = page.get_pixmap(matrix=mat)
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


# Monkey-patch PreviewWidget to add PDF support
if PreviewWidget is not None:
	PreviewWidget._show_pdf = _show_pdf

	_original_show_preview = PreviewWidget.show_preview

	def _show_preview_with_pdf(self, file_url):
		if file_url is not None:
			name = basename(file_url)
			ext = os.path.splitext(name)[1].lower()
			if ext == '.pdf':
				self._header.setText(name)
				scheme, path = splitscheme(file_url)
				if scheme == 'file://' and not os.path.isdir(path):
					self._show_pdf(path)
					return
		_original_show_preview(self, file_url)

	PreviewWidget.show_preview = _show_preview_with_pdf
