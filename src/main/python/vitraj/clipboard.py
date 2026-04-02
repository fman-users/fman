from fbs_runtime.platform import is_linux, is_windows, is_gnome_based, \
	is_kde_based
from vitraj.impl.util.qt import as_qurl, from_qurl
from vitraj.impl.util.qt.thread import run_in_main_thread
from PyQt5.QtCore import QMimeData
from PyQt5.QtWidgets import QApplication

import struct

_CFSTR_PREFERREDDROPEFFECT = 'Preferred DropEffect'
_CF_PREFERREDDROPEFFECT = \
	'application/x-qt-windows-mime;value="%s"' % _CFSTR_PREFERREDDROPEFFECT
_DROPEFFECT_MOVE = struct.pack('i', 2)

@run_in_main_thread
def clear():
	_clipboard().clear()

@run_in_main_thread
def set_text(text):
	_clipboard().setText(text)

@run_in_main_thread
def get_text():
	return _clipboard().text()

@run_in_main_thread
def copy_files(file_urls):
	if is_linux():
		extra_data = _get_extra_copy_cut_data_linux(file_urls, 'copy')
	else:
		extra_data = {}
	_place_on_clipboard(file_urls, extra_data)

@run_in_main_thread
def cut_files(file_urls):
	if is_windows():
		extra_data = {
			# Make pasting work in Explorer:
			_CFSTR_PREFERREDDROPEFFECT: _DROPEFFECT_MOVE,
			# Make pasting work in Qt:
			_CF_PREFERREDDROPEFFECT: _DROPEFFECT_MOVE
		}
	elif is_linux():
		extra_data = _get_extra_copy_cut_data_linux(file_urls, 'cut')
	else:
		raise NotImplementedError('Cutting files is not supported on this OS.')
	_place_on_clipboard(file_urls, extra_data)

@run_in_main_thread
def get_files():
	result = []
	for qurl in _clipboard().mimeData().urls():
		try:
			result.append(from_qurl(qurl))
		except ValueError:
			# On at least Windows 10, we sometimes get plain text (not file
			# URLs) on the text/uri-list clipboard. Ignore this:
			pass
	return result

@run_in_main_thread
def files_were_cut():
	if is_windows():
		data = _clipboard().mimeData().data(_CF_PREFERREDDROPEFFECT)
		return data == _DROPEFFECT_MOVE
	elif is_linux():
		mime_type = _get_linux_copy_cut_mime_type()
		if mime_type:
			return _clipboard().mimeData().data(mime_type)[:4] == b'cut\n'
	return False

def _clipboard():
	return QApplication.instance().clipboard()

def _place_on_clipboard(file_urls, extra_data):
	urls = [as_qurl(url) for url in file_urls]
	new_clipboard_data = QMimeData()
	new_clipboard_data.setUrls(urls)
	# We overwrite the "URLs" part of the clipboard, but we do want to keep the
	# text. This for instance allows for the following use case:
	#  1) Copy a file name
	#  2) Ctrl+C another file
	#  3) Ctrl+V to paste (=duplicate) the file
	#  4) Ctrl+V in the dialog to paste the file name we copied in 1).
	new_clipboard_data.setText(get_text())
	for key, value in extra_data.items():
		new_clipboard_data.setData(key, value)
	_clipboard().setMimeData(new_clipboard_data)

def _get_extra_copy_cut_data_linux(file_urls, copy_or_cut):
	result = {}
	mime_type = _get_linux_copy_cut_mime_type()
	if mime_type:
		result[mime_type] = '\n'.join([copy_or_cut] + file_urls).encode('utf-8')
	return result

def _get_linux_copy_cut_mime_type():
	if is_gnome_based():
		return 'x-special/gnome-copied-files'
	if is_kde_based():
		return 'application/x-kde-cutselection'