import sys

def main():
	from vitraj.impl.application_context import get_application_context
	appctxt = get_application_context()
	exit_code = appctxt.run()
	sys.exit(exit_code)

def profile_main():
	# Import late to only incur the .0n sec time cost when necessary:
	import cProfile
	from fbs_runtime.application_context import is_frozen
	filename = 'fman.profile' if is_frozen() else None
	cProfile.run('main()', sort='cumtime', filename=filename)

if __name__ == '__main__':
	if len(sys.argv) > 1 and sys.argv[1] == '--profile':
		sys.argv.pop(1)
		profile_main()
	else:
		main()