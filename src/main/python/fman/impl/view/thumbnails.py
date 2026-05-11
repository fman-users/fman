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


import os
from PyQt5.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, Qt, QSize
from PyQt5.QtGui import QImageReader, QPixmap


class _GeneratorSignals(QObject):
	done = pyqtSignal(str, object)   # (cache_key, QImage or None)


class _Generator(QRunnable):
	def __init__(self, key, source_path, size_bucket, signals):
		super().__init__()
		self._key = key
		self._source_path = source_path
		self._size_bucket = size_bucket
		self._signals = signals

	def run(self):
		reader = QImageReader(self._source_path)
		reader.setAutoTransform(True)
		image = reader.read()
		if image.isNull():
			self._signals.done.emit(self._key, None)
			return
		scaled = image.scaled(
			QSize(self._size_bucket, self._size_bucket),
			Qt.KeepAspectRatio,
			Qt.SmoothTransformation
		)
		self._signals.done.emit(self._key, scaled)


class ThumbnailCache(QObject):
	"""Persistent thumbnail cache.

	Stores generated thumbnails under ``<cache_dir>/<bucket>/<sha1>.png`` so
	they survive across fman restarts. Resolution metadata for source images
	is cached in memory keyed by ``(path, mtime_ns)``.
	"""

	thumbnail_ready = pyqtSignal(str)   # absolute source path

	def __init__(self, cache_dir, parent=None):
		super().__init__(parent)
		self._cache_dir = cache_dir
		os.makedirs(self._cache_dir, exist_ok=True)
		for bucket in SIZE_BUCKETS:
			os.makedirs(os.path.join(self._cache_dir, str(bucket)), exist_ok=True)
		self._mem_pixmaps = {}           # key -> QPixmap
		self._resolutions = {}           # (path, mtime_ns) -> QSize
		self._pending = set()            # set of keys currently generating
		self._signals = _GeneratorSignals()
		self._signals.done.connect(self._on_generated)
		self._pool = QThreadPool.globalInstance()
		# Path -> cache_key, used so the view can find the key to lookup
		# when `thumbnail_ready` fires.
		self._key_for = {}

	# ------------------------------------------------------------------ public
	def get(self, absolute_path, requested_px):
		"""Return a ``QPixmap`` if the thumbnail is cached, else ``None``."""
		try:
			mtime_ns = os.stat(absolute_path).st_mtime_ns
		except OSError:
			return None
		bucket = pick_size_bucket(requested_px)
		key = cache_key(absolute_path, mtime_ns, bucket)
		if key in self._mem_pixmaps:
			return self._mem_pixmaps[key]
		disk = self._disk_path(absolute_path, mtime_ns, bucket)
		if os.path.exists(disk):
			pix = QPixmap(disk)
			if not pix.isNull():
				self._mem_pixmaps[key] = pix
				return pix
		return None

	def request(self, absolute_path, requested_px):
		"""Schedule async thumbnail generation. Emits ``thumbnail_ready``."""
		try:
			mtime_ns = os.stat(absolute_path).st_mtime_ns
		except OSError:
			return
		bucket = pick_size_bucket(requested_px)
		key = cache_key(absolute_path, mtime_ns, bucket)
		if key in self._mem_pixmaps or key in self._pending:
			return
		self._pending.add(key)
		self._key_for[key] = (absolute_path, mtime_ns, bucket)
		self._pool.start(_Generator(key, absolute_path, bucket, self._signals))

	def get_resolution(self, absolute_path):
		"""Return ``QSize(w, h)`` for an image, or ``None`` if unreadable."""
		try:
			mtime_ns = os.stat(absolute_path).st_mtime_ns
		except OSError:
			return None
		cache_k = (absolute_path, mtime_ns)
		if cache_k in self._resolutions:
			return self._resolutions[cache_k]
		size = QImageReader(absolute_path).size()
		if not size.isValid():
			return None
		self._resolutions[cache_k] = size
		return size

	# ----------------------------------------------------------------- private
	def _disk_path(self, absolute_path, mtime_ns, size_bucket):
		key = cache_key(absolute_path, mtime_ns, size_bucket)
		return os.path.join(self._cache_dir, str(size_bucket), key + '.png')

	def _on_generated(self, key, image):
		self._pending.discard(key)
		if image is None or image.isNull():
			return
		path, mtime_ns, bucket = self._key_for.pop(key, (None, None, None))
		if path is None:
			return
		pix = QPixmap.fromImage(image)
		self._mem_pixmaps[key] = pix
		try:
			image.save(self._disk_path(path, mtime_ns, bucket), 'PNG')
		except OSError:
			pass
		self.thumbnail_ready.emit(path)
