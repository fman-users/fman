from os.path import dirname, join
import sys
sys.path.append(join(dirname(__file__), *'src/build/python'.split('/')))

from build_impl import git, record_release_on_server, upload_core_to_github, \
	git_has_changes
from build_impl.aws import create_cloudfront_invalidation
from fbs import path, activate_profile, SETTINGS
from fbs.builtin_commands import clean
from fbs.cmdline import command
from fbs_runtime.platform import is_windows, is_mac, is_linux, is_ubuntu, \
	is_fedora, is_arch_linux, linux_distribution
from os.path import dirname

import fbs.cmdline
import re

if is_windows():
	from build_impl.windows import freeze, upload
	from fbs.builtin_commands import sign, installer, sign_installer
elif is_mac():
	from build_impl.mac import freeze, sign, sign_installer, upload
	from fbs.builtin_commands import installer
elif is_linux():
	from fbs.builtin_commands import installer
	if is_ubuntu() or linux_distribution() == 'Debian GNU/Linux':
		from build_impl.ubuntu import freeze, upload
	elif is_arch_linux():
		from build_impl.arch import freeze, upload
		from fbs.builtin_commands import sign_installer
	elif is_fedora():
		from build_impl.fedora import freeze, upload
		from fbs.builtin_commands import sign_installer
	else:
		raise NotImplementedError(linux_distribution())

@command
def publish():
	if is_windows():
		freeze()
		sign()
		installer()
		sign_installer()
		upload()
	elif is_mac():
		freeze()
		sign()
		installer()
		sign_installer()
		upload()
	elif is_linux():
		if is_ubuntu():
			freeze()
			installer()
			upload()
		elif is_arch_linux():
			freeze()
			installer()
			sign_installer()
			upload()
		elif is_fedora():
			freeze()
			installer()
			sign_installer()
			upload()
		else:
			raise NotImplementedError()
	else:
		raise ValueError('Unknown operating system.')

@command
def release():
	if git_has_changes():
		print('There are uncommitted changes. Aborting.')
		return
	clean()
	activate_profile('release')
	version = SETTINGS['version']
	if version.endswith(snapshot_suffix):
		release_version = version[:-len(snapshot_suffix)]
		print('Releasing version %s' % release_version)
		next_version = _prompt_for_next_version(release_version)
		revision_before = git('rev-parse', 'HEAD').rstrip()
		settings_path = path('src/build/settings/base.json')
		_commit_version(
			settings_path, release_version,
			'Set version number for release ' + release_version
		)
		try:
			SETTINGS['version'] = release_version
			publish()
			release_tag = 'v' + release_version
			git('tag', release_tag)
			try:
				_commit_version(
					settings_path, next_version + snapshot_suffix,
					'Bump version for next development iteration'
				)
				git('push', '-u', 'origin', 'master')
				try:
					git('push', 'origin', release_tag)
					try:
						git('checkout', release_tag)
						print(
							'\nDone. Run\n\n'
							'    git pull\n'
							'    git checkout %s\n'
							'    python build.py release\n'
							'    git checkout master\n\n'
							'on the other OSs now, then come back here and do:'
							'\n\n'
							'    python build.py post_release\n'
							% release_tag
						)
					except:
						git('push', '--delete', 'origin', release_tag)
						raise
				except:
					git('revert', '--no-edit', revision_before + '..HEAD' )
					git('push', '-u', 'origin', 'master')
					revision_before = git('rev-parse', 'HEAD').rstrip()
					raise
			except:
				git('tag', '-d', release_tag)
				raise
		except:
			git('reset', revision_before)
			_replace_in_json(settings_path, 'version', version)
			raise
	else:
		publish()

snapshot_suffix = '-SNAPSHOT'

@command
def post_release():
	activate_profile('release')
	version = SETTINGS['version']
	assert not version.endswith(snapshot_suffix)
	cloudfront_items_to_invalidate = []
	for item in ('vitraj.dmg', 'vitraj.deb', 'vitraj.pkg.tar.xz', 'vitraj.rpm'):
		cloudfront_items_to_invalidate.append(item)
		cloudfront_items_to_invalidate.append('%s/%s' % (version, item))
	# We also used to have top-level vitrajSetup.exe, which was the online
	# installer. However, due to incompatibilities with later Windows 10
	# versions, the Windows online installer was discontinued in October 2020.
	# For this reason, we now only have {version}/vitrajSetup.exe.
	cloudfront_items_to_invalidate.append('%s/vitrajSetup.exe' % version)
	create_cloudfront_invalidation(cloudfront_items_to_invalidate)
	record_release_on_server()
	upload_core_to_github()
	git('checkout', 'master')

def _prompt_for_next_version(release_version):
	next_version = _get_suggested_next_version(release_version)
	return input('Next version (default: %s): ' % next_version) or next_version

def _get_suggested_next_version(version):
	version_parts = version.split('.')
	next_patch = str(int(version_parts[-1]) + 1)
	return '.'.join(version_parts[:-1]) + '.' + next_patch

def _commit_version(settings_path, version, commit_message):
	_replace_in_json(settings_path, 'version', version)
	git('add', settings_path)
	git('commit', '-m', commit_message)

def _replace_in_json(json_path, key, value):
	with open(json_path, 'r') as f:
		old_lines = f.readlines()
	new_lines = []
	found = False
	for line in old_lines:
		new_line = _replace_re_group('\t"%s": "([^"]*)"' % key, line, value)
		if new_line:
			found = True
		else:
			new_line = line
		new_lines.append(new_line)
	if not found:
		raise ValueError('Could not find "%s" mapping in %s' % (key, json_path))
	with open(json_path, 'w') as f:
		f.write(''.join(new_lines))

def _replace_re_group(pattern, string, group_replacement):
	match = re.match(pattern, string)
	if match:
		return string[:match.start(1)] + \
			   group_replacement + \
			   string[match.end(1):]

if __name__ == '__main__':
	project_dir = dirname(__file__)
	fbs.cmdline.main(project_dir)