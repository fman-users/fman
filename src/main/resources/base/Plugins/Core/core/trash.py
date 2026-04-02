from errno import EINVAL
from vitraj import PLATFORM
from os import strerror

if PLATFORM == 'Mac':
	from osxtrash import move_to_trash
else:
	def move_to_trash(*files):
		send2trash = _import_send2trash()
		for file in files:
			try:
				send2trash(file)
			except OSError as e:
				if PLATFORM == 'Windows':
					if e.errno == EINVAL and e.winerror == _DE_INVALIDFILES:
						message = strerror(EINVAL) + ' (file may be in use)'
						raise OSError(EINVAL, message)
				raise

def _import_send2trash():
	# We import send2trash as late as possible. Here's why: On Ubuntu
	# (/Gnome), send2trash uses GIO - if it is available and initialized.
	# Whether that happens is determined at *import time*. Importing
	# send2trash at the last possible moment, ensures that it picks up GIO.
	from send2trash import send2trash as result
	if PLATFORM == 'Linux':
		try:
			from gi.repository import GObject
		except ImportError:
			pass
		else:
			# Fix for elementary OS / Pantheon:
			if not hasattr(GObject, 'GError'):
				from send2trash.plat_other import send2trash as result
	return result

# Windows constant:
_DE_INVALIDFILES = 0x7C