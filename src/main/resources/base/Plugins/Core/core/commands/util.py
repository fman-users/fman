from getpass import getuser
from os.path import expanduser
from PyQt5.QtCore import QFileInfo

import os

def get_program_files():
	return os.environ.get('PROGRAMW6432', r'C:\Program Files')

def get_program_files_x86():
	return os.environ.get('PROGRAMFILES', r'C:\Program Files (x86)')

def get_user():
	try:
		return getuser()
	except Exception:
		return os.path.basename(expanduser('~'))

def is_hidden(file_path):
	if os.path.basename(file_path).startswith('.'):
		return True
	return QFileInfo(file_path).isHidden()