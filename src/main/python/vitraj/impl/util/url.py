from vitraj.url import dirname

def get_existing_pardir(url, is_dir):
	# N.B.: If `url` is a directory, it is returned, even though it is not a
	# strict parent directory.
	for candidate in _iter_parents(url):
		try:
			if is_dir(candidate):
				return candidate
		except FileNotFoundError:
			pass

def is_pardir(pardir, subdir):
	# N.B.: Every directory is a "pardir" of itself.
	for dir_ in _iter_parents(subdir):
		if dir_ == pardir:
			return True
	return False

def _iter_parents(url):
	prev_url = None
	while url != prev_url:
		yield url
		prev_url = url
		url = dirname(url)