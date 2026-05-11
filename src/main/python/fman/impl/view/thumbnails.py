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


import hashlib

# Thumbnails are generated at one of these pixel sizes; tiles downscale
# the nearest-larger bucket at paint time. This keeps the on-disk cache
# bounded regardless of where the user puts the tile-size slider.
SIZE_BUCKETS = (128, 256, 512)


def cache_key(absolute_path, mtime_ns, size_bucket):
	"""Return the SHA1 hex key used to store a thumbnail on disk."""
	payload = '%s|%d|%d' % (absolute_path, mtime_ns, size_bucket)
	return hashlib.sha1(payload.encode('utf-8')).hexdigest()


def pick_size_bucket(requested_px):
	"""Return the smallest cache bucket >= ``requested_px``.

	If ``requested_px`` is larger than the biggest bucket, return the biggest.
	"""
	for bucket in SIZE_BUCKETS:
		if requested_px <= bucket:
			return bucket
	return SIZE_BUCKETS[-1]
