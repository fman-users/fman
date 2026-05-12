from core.util import strformat_dict_values
from vitraj import load_json, show_alert, show_status_message, PLATFORM
from shutil import which
from subprocess import Popen, check_output

import os
import sys

def is_arch():
	try:
		return _get_os_release_name().startswith('Arch Linux')
	except FileNotFoundError:
		return False

def is_mac():
	return sys.platform == 'darwin'

def get_popen_kwargs_for_opening(files, with_):
	args = [with_] + files
	if PLATFORM == 'Mac':
		args = ['/usr/bin/open', '-a'] + args
	return {'args': args}

def open_terminal_in_directory(dir_path):
	settings = load_json('Core Settings.json', default={})
	app = settings.get('terminal', {})
	if app:
		_run_app_from_setting(app, dir_path)
	else:
		alternatives = [
			'x-terminal-emulator', # Debian-based
			'konsole',             # KDE
			'gnome-terminal'       # Gnome-based / Fedora
		]
		for alternative in alternatives:
			binary = which(alternative)
			if binary:
				app = {'args': [binary], 'cwd': '{curr_dir}'}
				_run_app_from_setting(app, dir_path)
				break
		else:
			show_alert(
				'Could not determine the Popen(...) arguments for opening the '
				'terminal. Please configure the "terminal" dictionary in '
				'"Core Settings.json" as explained '
				'<a href="https://fman.io/docs/terminal?s=f">here</a>.'
			)

def open_native_file_manager(dir_path):
	settings = load_json('Core Settings.json', default={})
	app = settings.get('native_file_manager', {})
	if app:
		_run_app_from_setting(app, dir_path)
	else:
		xdg_open = which('xdg-open')
		if xdg_open:
			app = {'args': [xdg_open, '{curr_dir}']}
			_run_app_from_setting(app, dir_path)
			if _is_ubuntu():
				try:
					fpl = \
						check_output(['dconf', 'read', _FOCUS_PREVENTION_LEVEL])
				except FileNotFoundError as dconf_not_installed:
					pass
				else:
					if fpl in (b'', b'1\n'):
						show_status_message(
							'Hint: If your OS\'s file manager opened in the '
							'background, click '
							'<a href="https://askubuntu.com/a/594301">here</a>.',
							timeout_secs=10
						)
		else:
			show_alert(
				'Could not determine the Popen(...) arguments for opening the '
				'native file manager. Please configure the '
				'"native_file_manager" dictionary in "Core Settings.json" '
				'similarly to what\'s explained '
				'<a href="https://fman.io/docs/terminal?s=f">here</a>.'
			)

def _is_ubuntu():
	try:
		return _get_os_release_name().startswith('Ubuntu')
	except FileNotFoundError:
		return False

def _run_app_from_setting(app, curr_dir):
	popen_kwargs = strformat_dict_values(app, {'curr_dir': curr_dir})
	Popen(**popen_kwargs)

def _is_gnome_based():
	curr_desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
	return curr_desktop in ('unity', 'gnome', 'x-cinnamon')

def _get_os_release_name():
	with open('/etc/os-release', 'r') as f:
		for line in f:
			line = line.rstrip()
			if line.startswith('NAME='):
				name = line[len('NAME='):]
				return name.strip('"')

_FOCUS_PREVENTION_LEVEL = \
	'/org/compiz/profiles/unity/plugins/core/focus-prevention-level'