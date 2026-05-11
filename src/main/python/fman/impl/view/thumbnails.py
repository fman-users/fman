"""Persistent thumbnail cache and metadata helpers for the gallery view."""

_UNITS = ('B', 'KB', 'MB', 'GB', 'TB')


def format_human_size(num_bytes):
	"""Return a short human-readable file size, e.g. ``'4.2 MB'``."""
	size = float(num_bytes)
	for unit in _UNITS:
		if size < 1024 or unit == _UNITS[-1]:
			if unit == 'B':
				return '%d B' % int(size)
			return '%.1f %s' % (size, unit)
		size /= 1024
	# Unreachable, but keeps linters happy.
	return '%.1f %s' % (size, _UNITS[-1])
