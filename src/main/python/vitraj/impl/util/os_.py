from fbs_runtime.platform import is_windows, is_mac, is_linux

import platform

def name():
	if is_windows():
		return 'Windows'
	if is_mac():
		return 'macOS'
	if is_linux():
		return 'Linux'
	raise RuntimeError('Unknown operating system.')

def version():
	if is_windows():
		uname = platform.uname()
		return '%s (%s)' % (uname.release, uname.version)
	if is_mac():
		return platform.mac_ver()[0]
	if is_linux():
		from distro import linux_distribution
		return linux_distribution(False)[1]
	raise RuntimeError('Unknown operating system.')

def distribution():
	if is_linux():
		from distro import linux_distribution
		return linux_distribution()[0]
	return ''