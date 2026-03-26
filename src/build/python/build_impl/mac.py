from build_impl import copy_framework, SETTINGS, copy_python_library, \
	upload_file, upload_installer_to_aws
from fbs import path
from fbs.cmdline import command
from fbs.freeze.mac import freeze_mac
from glob import glob
from os import remove
from os.path import basename, join
from shutil import rmtree, move
from subprocess import run, PIPE, CalledProcessError, SubprocessError
from time import sleep

import json
import os
import plistlib
import requests

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
	copy_python_library('osxtrash', path('${core_plugin_in_freeze_dir}'))
	import osxtrash
	so_name = basename(osxtrash.__file__)
	# Move the .so to Frameworks (where PyInstaller 6.x sets sys._MEIPASS),
	# so it's both importable and codesigned:
	move(
		path('${core_plugin_in_freeze_dir}/' + so_name),
		path('${freeze_dir}/Contents/Frameworks')
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
	# Avoid some Notarization warnings by signing not just the app_dir, but some
	# sub-directories as well:
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
	_notarize(zip_path)
	_staple(app_dir)

def _run_codesign(*args):
	run([
		'codesign', '--verbose',
		'-s', 'Developer ID Application: Michael Herrmann',
	] + list(args), check=True)

def _staple(file_path):
	run(['xcrun', 'stapler', 'staple', file_path], check=True)

def _notarize(file_path, query_interval_secs=10):
	response = _run_altool([
		'--notarize-app', '-t', 'osx', '-f', file_path,
		'--primary-bundle-id', SETTINGS['mac_bundle_identifier']
	])
	request_uuid = response['notarization-upload']['RequestUUID']
	while True:
		sleep(query_interval_secs)
		try:
			response = _run_altool(['--notarization-info', request_uuid])
		except CalledProcessError as e:
			stdout = e.stdout.decode('utf-8')
			if 'Could not find the RequestUUID' not in stdout:
				raise
		else:
			status = response['notarization-info']['Status']
			if status != 'in progress':
				break
		print('Waiting for notarization to complete...')
	log_url = response['notarization-info']['LogFileURL']
	log_response = requests.get(log_url)
	log_response.raise_for_status()
	log_json = log_response.json()
	issues = log_json.get('issues', [])
	if issues:
		print('Notarization encountered some issues:')
		print(json.dumps(issues, indent=4, sort_keys=True))
	if status != 'success':
		raise RuntimeError('Unexpected notarization status: %r' % status)

def _run_altool(args):
	all_args = [
		'xcrun', 'altool', '--output-format', 'xml',
		'-u', SETTINGS['apple_developer_user'],
		'-p', SETTINGS['apple_developer_app_pw']
	] + args
	process = run(all_args, stdout=PIPE, stderr=PIPE, check=True)
	return plistlib.loads(process.stdout)

@command
def sign_installer():
	dmg_path = path('target/fman.dmg')
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
		upload_installer_to_aws('fman.dmg')

def _zip_mac(src_dir, dest_zip):
	run([
		'ditto', '-c', '-k', '--sequesterRsrc', '--keepParent',
		src_dir,
		dest_zip
	], check=True)
