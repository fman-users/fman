from build_impl import copy_python_library, upload_to_s3
from fbs import path, SETTINGS
from fbs.cmdline import command
from fbs.freeze.windows import freeze_windows
from os import remove
from os.path import join, dirname
from shutil import copy, rmtree

@command
def freeze():
	freeze_windows()
	_copy_winpty_files()
	rmtree(path('${core_plugin_in_freeze_dir}/bin/mac'))
	rmtree(path('${core_plugin_in_freeze_dir}/bin/linux'))
	# Open Sans is only used on Linux. Further, it fails to load on some users'
	# Windows systems (see fman issue #480). Remove it to avoid problems,
	# improve startup performance and decrease fman's download size.
	# (Also note that a more elegant solution would be to only place
	# Open Sans.ttf in src/main/resources/*linux*/Plugins/Core. But the current
	# implementation cannot handle multiple dirs .../resources/main,
	# .../resources/linux for one plugin.)
	remove(path('${core_plugin_in_freeze_dir}/Open Sans.ttf'))
	copy_python_library('send2trash', path('${core_plugin_in_freeze_dir}'))

def _copy_winpty_files():
	import winpty
	winpty_dir = dirname(winpty.__file__)
	copy(join(winpty_dir, 'winpty-agent.exe'), path('${freeze_dir}'))

@command
def upload():
	if SETTINGS['release']:
		src_path = path('target/vitrajSetup.exe')
		dest_path = SETTINGS['version'] + '/vitrajSetup.exe'
		upload_to_s3(src_path, dest_path)
		print('\nDone. Please upload vitrajSetup.exe to update.vitraj.io now.')