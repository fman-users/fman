from build_impl import copy_framework, SETTINGS, copy_python_library, \
	upload_file, upload_installer_to_aws
from fbs import path
from fbs.cmdline import command
from fbs.freeze.mac import freeze_mac
from glob import glob
from os import remove
from os.path import join
from shutil import rmtree, move
from subprocess import run

import os

_UPDATES_DIR = 'updates/mac'

@command
def freeze():
	freeze_mac()
	rmtree(path('${core_plugin_in_freeze_dir}/bin/linux'))
	rmtree(path('${core_plugin_in_freeze_dir}/bin/windows'))
	# Open Sans is only used on Linux. Further, it fails to load on some users'
	# Windows systems (see fman issue #480). Remove it to avoid problems,
	# improve startup performance and decrease fman's download size.
	# (Also note that a more elegant solution would be to only place
	# Open Sans.ttf in src/main/resources/*linux*/Plugins/Core. But the current
	# implementation cannot handle multiple dirs .../resources/main,
	# .../resources/linux for one plugin.)
	remove(path('${core_plugin_in_freeze_dir}/Open Sans.ttf'))
	# Similarly for Roboto Bold.ttf. It is only used on Windows:
	remove(path('${core_plugin_in_freeze_dir}/Roboto Bold.ttf'))
	_strip_unused_from_bundle()
	copy_framework(
		path('lib/mac/Sparkle-1.22.0/Sparkle.framework'),
		path('${freeze_dir}/Contents/Frameworks/Sparkle.framework')
	)
	move(
		path('${core_plugin_in_freeze_dir}/bin/mac/7za'),
		path('${freeze_dir}/Contents/MacOS')
	)
	# Ad-hoc sign so macOS shows TCC permission dialogs for folder access.
	# Without this, unsigned apps are silently denied access to Downloads etc.
	run(['codesign', '--force', '--deep', '--sign', '-', path('${freeze_dir}')],
		check=True)

def _strip_unused_from_bundle():
	frameworks = path('${freeze_dir}/Contents/Frameworks')
	resources = path('${freeze_dir}/Contents/Resources')
	# boto3/botocore are build-system-only deps, not used at runtime (~40MB):
	for dir_name in ('boto3', 'botocore', 's3transfer'):
		for base in (frameworks, resources):
			dir_path = join(base, dir_name)
			if os.path.islink(dir_path):
				os.unlink(dir_path)
			elif os.path.isdir(dir_path):
				rmtree(dir_path)
	# Remove unused Qt frameworks (fman only uses Core, Gui, Widgets,
	# MacExtras, PrintSupport, Svg):
	qt_lib = join(frameworks, 'PyQt5', 'Qt5', 'lib')
	for unused_fw in (
		'QtQml', 'QtQmlModels', 'QtQuick', 'QtWebSockets'
	):
		fw_path = join(qt_lib, unused_fw + '.framework')
		if os.path.isdir(fw_path):
			rmtree(fw_path)
	# Remove unused Qt platform plugins:
	qt_plugins = join(frameworks, 'PyQt5', 'Qt5', 'plugins')
	for unused_plugin in (
		'platforms/libqwebgl.dylib', 'platforms/libqminimal.dylib',
		'platforms/libqoffscreen.dylib', 'bearer', 'generic',
		'platformthemes'
	):
		p = join(qt_plugins, unused_plugin)
		if os.path.isdir(p):
			rmtree(p)
		elif os.path.isfile(p):
			remove(p)

@command
def sign():
	app_dir = path('${freeze_dir}')
	sparkle_dir = join(app_dir, 'Contents/Frameworks/Sparkle.framework')
	# Sign inside-out to avoid notarization warnings about nested binaries:
	for binary_path in (
		join(sparkle_dir, 'Versions/A/Resources/Autoupdate.app'),
		sparkle_dir,
		app_dir
	):
		_run_codesign(
			'--deep', '--force', '--options', 'runtime',
			'--entitlements', path('src/sign/mac/entitlements.plist'),
			binary_path
		)
	zip_path = path('${freeze_dir}') + '.zip'
	_zip_mac(app_dir, zip_path)
	try:
		_notarize(zip_path)
	finally:
		if os.path.exists(zip_path):
			remove(zip_path)
	_staple(app_dir)

def _codesign_identity():
	identity = os.environ.get('MAC_CODESIGN_IDENTITY', '').strip()
	if not identity:
		raise RuntimeError(
			'MAC_CODESIGN_IDENTITY env var is required for signing. '
			'Set it to your Developer ID Application identity '
			"(e.g. 'Developer ID Application: Jane Doe (TEAMID)')."
		)
	return identity

def _run_codesign(*args):
	run([
		'codesign', '--verbose', '--timestamp',
		'-s', _codesign_identity(),
	] + list(args), check=True)

def _staple(file_path):
	run(['xcrun', 'stapler', 'staple', file_path], check=True)

def _notarize(file_path):
	"""Submit ``file_path`` (a .zip or .dmg) to Apple's notary service.

	Uses ``notarytool`` with a pre-configured keychain profile (set up by
	``xcrun notarytool store-credentials``) so the Apple ID password never
	appears on the command line. ``altool``'s notarization service was
	retired by Apple in November 2023.

	Env:
	    NOTARYTOOL_PROFILE: keychain profile name (required).
	    NOTARYTOOL_KEYCHAIN: keychain path; if unset, the default login
	        keychain is used (matches local-dev expectations).
	"""
	profile = _require_env('NOTARYTOOL_PROFILE')
	args = [
		'xcrun', 'notarytool', 'submit', file_path,
		'--keychain-profile', profile,
		'--wait',
	]
	keychain = os.environ.get('NOTARYTOOL_KEYCHAIN', '').strip()
	if keychain:
		args += ['--keychain', keychain]
	run(args, check=True)

def _require_env(name):
	value = os.environ.get(name, '').strip()
	if not value:
		raise RuntimeError(
			f'{name} env var is required for notarization.'
		)
	return value

@command
def sign_installer():
	dmg_path = path('target/vitraj.dmg')
	_run_codesign(dmg_path)
	_notarize(dmg_path)
	_staple(dmg_path)

@command
def upload():
	_zip_mac(
		path('${freeze_dir}'),
		path('target/autoupdate/%s.zip' % SETTINGS['version'])
	)
	upload_file(
		path('target/autoupdate/%s.zip' % SETTINGS['version']), _UPDATES_DIR
	)
	for patch_file in glob(path('target/autoupdate/*.delta')):
		upload_file(patch_file, _UPDATES_DIR)
	if SETTINGS['release']:
		upload_installer_to_aws('vitraj.dmg')

def _zip_mac(src_dir, dest_zip):
	run([
		'ditto', '-c', '-k', '--sequesterRsrc', '--keepParent',
		src_dir,
		dest_zip
	], check=True)
