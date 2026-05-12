from getpass import getuser
from os import listdir, strerror
from os.path import join, basename, expanduser, dirname, realpath, relpath, \
	pardir, splitdrive

import errno
import os

def listdir_absolute(dir_path):
	return [join(dir_path, file_name) for file_name in listdir(dir_path)]

def get_user():
	try:
		return getuser()
	except Exception:
		return basename(expanduser('~'))

def is_below_dir(file_path, directory):
	if splitdrive(file_path)[0].lower() != splitdrive(directory)[0].lower():
		return False
	rel = relpath(realpath(dirname(file_path)), realpath(directory))
	return not (rel == pardir or rel.startswith(pardir + os.sep))

def parse_version(version_str):
	if version_str.endswith('-SNAPSHOT'):
		version_str = version_str[:-len('-SNAPSHOT')]
	return tuple(map(int, version_str.split('.')))

class MixinBase:

	_FIELDS = () # To be set by subclasses

	def _get_field_values(self):
		return tuple(getattr(self, field) for field in self._FIELDS)

class EqMixin(MixinBase):
	def __eq__(self, other):
		try:
			return self._get_field_values() == other._get_field_values()
		except AttributeError:
			return False
	def __ne__(self, other):
		return not self.__eq__(other)
	def __hash__(self):
		return hash(self._get_field_values())

class ReprMixin(MixinBase):
	def __repr__(self):
		return '%s(%s)' % (
			self.__class__.__name__,
			', '.join(
				'%s=%r' % (field, val)
				for (field, val) in zip(self._FIELDS, self._get_field_values())
			)
		)

class ConstructorMixin(MixinBase):
	def __init__(self, *args):
		super().__init__()
		for field, arg in zip(self._FIELDS, args):
			setattr(self, field, arg)

class Event:
	def __init__(self):
		self._callbacks = []
	def add_callback(self, callback):
		self._callbacks.append(callback)
	def remove_callback(self, callback):
		self._callbacks.remove(callback)
	def trigger(self, *args):
		for callback in self._callbacks:
			callback(*args)

# Copied from core.util:
def filenotfounderror(path):
	# The correct way of instantiating FileNotFoundError in a way that respects
	# the parent class (OSError)'s arguments:
	return FileNotFoundError(errno.ENOENT, strerror(errno.ENOENT), path)