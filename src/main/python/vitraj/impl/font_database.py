from vitraj.impl.util.qt.thread import run_in_main_thread
from PyQt5.QtGui import QFontDatabase

class FontError(RuntimeError):
	pass

class FontDatabase:
	def __init__(self):
		self._font_ids = {}
	@run_in_main_thread
	def load(self, font_file):
		font_id = QFontDatabase.addApplicationFont(font_file)
		if font_id == -1:
			raise FontError('Font %r could not be loaded.' % font_file)
		self._font_ids[font_file] = font_id
	@run_in_main_thread
	def unload(self, font_file):
		result = \
			QFontDatabase.removeApplicationFont(self._font_ids.pop(font_file))
		if not result:
			raise FontError('Could not unload font %r.' % font_file)