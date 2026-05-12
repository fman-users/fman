"""Persistent thumbnail cache and metadata helpers for the gallery view."""

import hashlib
import os
from collections import OrderedDict

from PyQt5.QtCore import QObject, QRunnable, QSize, Qt, QThreadPool, pyqtSignal
from PyQt5.QtGui import QImageReader, QPixmap


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
	return '%.1f %s' % (size, _UNITS[-1])


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


# Bound the in-memory caches. 512 pixmaps at 256×256 RGBA8 ≈ 130 MB worst case;
# a typical gallery viewport holds 30-60 tiles, so this leaves comfortable
# headroom for scrolling without unbounded growth.
_MAX_PIXMAPS = 512
_MAX_RESOLUTIONS = 4096
_MAX_FAILED = 4096


def _lru_set(od, key, value, cap):
	"""Insert ``key -> value`` into ``od`` (an OrderedDict) with LRU eviction."""
	if key in od:
		od.move_to_end(key)
	od[key] = value
	while len(od) > cap:
		od.popitem(last=False)


class _GeneratorSignals(QObject):
	generated = pyqtSignal(str, object)  # (cache_key, QImage or None)
	disk_loaded = pyqtSignal(str, object)  # (cache_key, QPixmap or None)
	resolution_read = pyqtSignal(object, object)  # ((path, mtime_ns), QSize or None)


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
		# Decode-and-scale in one pass: JPEG IDCT stops at the right level
		# and PNG/TIFF use less RAM than a full-res decode + downscale.
		original = reader.size()
		if original.isValid() and not original.isEmpty():
			target = original.scaled(
				QSize(self._size_bucket, self._size_bucket),
				Qt.KeepAspectRatio,
			)
			reader.setScaledSize(target)
		image = reader.read()
		if image.isNull():
			self._signals.generated.emit(self._key, None)
			return
		self._signals.generated.emit(self._key, image)


class _DiskLoader(QRunnable):
	"""Load disk-cached QPixmap off the UI thread."""

	def __init__(self, key, disk_path, signals):
		super().__init__()
		self._key = key
		self._disk_path = disk_path
		self._signals = signals

	def run(self):
		pix = QPixmap(self._disk_path)
		if pix.isNull():
			self._signals.disk_loaded.emit(self._key, None)
		else:
			self._signals.disk_loaded.emit(self._key, pix)


class _ResolutionReader(QRunnable):
	"""Read image resolution off the UI thread."""

	def __init__(self, key, path, signals):
		super().__init__()
		self._key = key
		self._path = path
		self._signals = signals

	def run(self):
		size = QImageReader(self._path).size()
		if not size.isValid():
			self._signals.resolution_read.emit(self._key, None)
		else:
			self._signals.resolution_read.emit(self._key, size)


class ThumbnailCache(QObject):
	"""Persistent thumbnail cache.

	Stores generated thumbnails under ``<cache_dir>/<bucket>/<sha1>.png`` so
	they survive across fman restarts. Resolution metadata for source images
	is cached in memory keyed by ``(path, mtime_ns)``.
	"""

	# Emits the absolute source path of the thumbnail that just became
	# available. The view uses this to repaint only the affected tile.
	thumbnail_ready = pyqtSignal(str)

	def __init__(self, cache_dir, parent=None):
		super().__init__(parent)
		self._cache_dir = cache_dir
		os.makedirs(self._cache_dir, exist_ok=True)
		for bucket in SIZE_BUCKETS:
			os.makedirs(os.path.join(self._cache_dir, str(bucket)), exist_ok=True)
		self._mem_pixmaps = OrderedDict()    # key -> QPixmap (LRU)
		self._stats = OrderedDict()          # path -> (mtime_ns, size_bytes)
		self._resolutions = OrderedDict()    # (path, mtime_ns) -> QSize
		# Keys whose generator emitted (key, None). Without this, paint
		# events would re-schedule generation forever for unreadable images.
		self._failed = OrderedDict()
		# In-flight work; presence implies pending. Stored values are the
		# context needed to finalize on the signal callback.
		self._generator_for = {}   # key -> (path, mtime_ns, bucket)
		self._disk_load_for = {}   # key -> path
		self._pending_resolutions = set()  # (path, mtime_ns)
		self._signals = _GeneratorSignals()
		self._signals.generated.connect(self._on_generated)
		self._signals.disk_loaded.connect(self._on_disk_loaded)
		self._signals.resolution_read.connect(self._on_resolution_read)
		self._pool = QThreadPool.globalInstance()

	# ------------------------------------------------------------------ public
	def get(self, absolute_path, requested_px):
		"""Return a ``QPixmap`` if in-memory cached, else schedule async disk load."""
		stat = self._stat(absolute_path)
		if stat is None:
			return None
		mtime_ns, _ = stat
		bucket = pick_size_bucket(requested_px)
		key = cache_key(absolute_path, mtime_ns, bucket)
		pix = self._mem_pixmaps.get(key)
		if pix is not None:
			self._mem_pixmaps.move_to_end(key)
			return pix
		if key in self._disk_load_for or key in self._failed:
			return None
		# Only schedule a disk load if the file actually exists — otherwise
		# request() handles generation. Stat is microseconds; the decode is
		# 200-500ms, which is what we moved to the worker thread.
		disk = self._disk_path(absolute_path, mtime_ns, bucket)
		if not os.path.exists(disk):
			return None
		self._disk_load_for[key] = absolute_path
		self._pool.start(_DiskLoader(key, disk, self._signals))
		return None

	def request(self, absolute_path, requested_px):
		"""Schedule async thumbnail generation. Emits ``thumbnail_ready``."""
		stat = self._stat(absolute_path)
		if stat is None:
			return
		mtime_ns, _ = stat
		bucket = pick_size_bucket(requested_px)
		key = cache_key(absolute_path, mtime_ns, bucket)
		if (
			key in self._mem_pixmaps
			or key in self._generator_for
			or key in self._disk_load_for
			or key in self._failed
		):
			return
		self._generator_for[key] = (absolute_path, mtime_ns, bucket)
		self._pool.start(_Generator(key, absolute_path, bucket, self._signals))

	def get_resolution(self, absolute_path):
		"""Return ``QSize(w, h)`` if cached, else schedule async read."""
		stat = self._stat(absolute_path)
		if stat is None:
			return None
		mtime_ns, _ = stat
		cache_k = (absolute_path, mtime_ns)
		cached = self._resolutions.get(cache_k)
		if cached is not None:
			self._resolutions.move_to_end(cache_k)
			return cached
		if cache_k not in self._pending_resolutions:
			self._pending_resolutions.add(cache_k)
			self._pool.start(_ResolutionReader(cache_k, absolute_path, self._signals))
		return None

	def get_size_bytes(self, absolute_path):
		"""Return the file size in bytes, or ``None`` if unreadable."""
		stat = self._stat(absolute_path)
		if stat is None:
			return None
		return stat[1]

	# ----------------------------------------------------------------- private
	def _stat(self, absolute_path):
		try:
			st = os.stat(absolute_path)
		except OSError:
			return None
		mtime_ns = st.st_mtime_ns
		cached = self._stats.get(absolute_path)
		if cached is not None and cached[0] == mtime_ns:
			self._stats.move_to_end(absolute_path)
			return cached
		entry = (mtime_ns, st.st_size)
		_lru_set(self._stats, absolute_path, entry, _MAX_RESOLUTIONS)
		return entry

	def _disk_path(self, absolute_path, mtime_ns, size_bucket):
		key = cache_key(absolute_path, mtime_ns, size_bucket)
		return os.path.join(self._cache_dir, str(size_bucket), key + '.png')

	def _on_generated(self, key, image):
		entry = self._generator_for.pop(key, None)
		if image is None or image.isNull():
			_lru_set(self._failed, key, True, _MAX_FAILED)
			return
		if entry is None:
			return
		path, mtime_ns, bucket = entry
		pix = QPixmap.fromImage(image)
		_lru_set(self._mem_pixmaps, key, pix, _MAX_PIXMAPS)
		try:
			image.save(self._disk_path(path, mtime_ns, bucket), 'PNG')
		except OSError:
			pass
		self.thumbnail_ready.emit(path)

	def _on_disk_loaded(self, key, pix):
		# A null pixmap here means the disk file existed but was unreadable
		# (corrupt PNG). Do NOT mark _failed — generation can still recover
		# and will overwrite the bad file. Caller's next request() handles it.
		path = self._disk_load_for.pop(key, None)
		if path is None or pix is None or pix.isNull():
			return
		_lru_set(self._mem_pixmaps, key, pix, _MAX_PIXMAPS)
		self.thumbnail_ready.emit(path)

	def _on_resolution_read(self, cache_k, size):
		self._pending_resolutions.discard(cache_k)
		if size is None or not size.isValid():
			return
		_lru_set(self._resolutions, cache_k, size, _MAX_RESOLUTIONS)
		path, _ = cache_k
		self.thumbnail_ready.emit(path)
