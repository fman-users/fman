from PyQt5.QtMacExtras import QMacPasteboardMime

class MacClipboardFix(QMacPasteboardMime):
	"""
	Work around QTBUG-61562 on Mac, which can be reproduced as follows:

		from PyQt5.QtWidgets import QApplication
		app = QApplication([])
		app.clipboard().setText('Hello')

	Now paste into Excel or Pycharm. The text that gets pasted is not just
	'Hello' but '\uFEFFHello'.
	"""
	def __init__(self):
		super().__init__(QMacPasteboardMime.MIME_CLIP)
	def convertorName(self):
		return 'UnicodeTextUtf8Default'
	def flavorFor(self, mime):
		if mime == 'text/plain':
			return 'public.utf8-plain-text'
		parts = mime.split('charset=', 1)
		if len(parts) > 1:
			charset = parts[1].split(';', 1)[0]
			if charset == 'system':
				return 'public.utf8-plain-text'
			if charset in ('iso-106464-ucs-2', 'utf16'):
				return 'public.utf16-plain-text'
		return None
	def canConvert(self, mime, flav):
		return mime.startswith('text/plain') and \
			flav in ('public.utf8-plain-text', 'public.utf16-plain-text')
	def mimeFor(self, flavor):
		if flavor == 'public.utf8-plain-text':
			return 'text/plain'
		if flavor == 'public.utf16-plain-text':
			return 'text/plain;charset=utf16'
		return None
	def convertFromMime(self, mime, data, flavor):
		if flavor == 'public.utf8-plain-text':
			return [data.encode('utf-8')]
		if flavor == 'public.utf16-plain-text':
			return [data.encode('utf-16')]
		return []
	def convertToMime(self, mime, data, flavor):
		if len(data) > 1:
			raise ValueError('Cannot handle multiple data members')
		data, = data
		if flavor == 'public.utf8-plain-text':
			return data.decode('utf-8')
		if flavor == 'public.utf16-plain-text':
			return data.decode('utf-16')
		raise ValueError('Unhandled MIME type: ' + mime)